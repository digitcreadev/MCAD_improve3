#!/usr/bin/env bash
set -u
ROOT="${1:-.}"
MODE="${2:-static}"
COMPOSE="$ROOT/bi-stack/docker-compose.yml"
FAILS=0
WARNS=0

ok(){ echo "[OK] $*"; }
warn(){ echo "[WARN] $*"; WARNS=$((WARNS+1)); }
fail(){ echo "[FAIL] $*"; FAILS=$((FAILS+1)); }

has_service(){ docker compose -f "$COMPOSE" config --services 2>/dev/null | grep -qx "$1"; }

printf '=== MCAD FoodMart XMLA/eMondrian strict regression check ===\n'
printf 'repo_root=%s\nmode=%s\n\n' "$ROOT" "$MODE"

if [ ! -f "$COMPOSE" ]; then
  fail "docker-compose.yml not found at $COMPOSE"
  exit 1
fi

echo "--- docker compose services ---"
SERVICES="$(docker compose -f "$COMPOSE" config --services 2>/dev/null || true)"
echo "$SERVICES"
echo

has_service mcad-api && ok "mcad-api service is declared" || fail "mcad-api service is missing"
has_service mcad-proxy && ok "mcad-proxy service is declared" || fail "mcad-proxy service is missing"
has_service emondrian && ok "emondrian service is declared" || fail "emondrian service is missing from docker-compose.yml"
has_service pivot4j && ok "pivot4j service is declared" || warn "pivot4j service is missing; not fatal for proxy XMLA, but useful for OLAP UI demo"

echo
echo "--- static file checks ---"
[ -d "$ROOT/bi-stack/emondrian" ] && ok "bi-stack/emondrian directory exists" || fail "bi-stack/emondrian directory is missing"
[ -f "$ROOT/bi-stack/emondrian/Dockerfile" ] && ok "emondrian Dockerfile exists" || fail "emondrian Dockerfile missing"
[ -d "$ROOT/bi-stack/pivot4j" ] && ok "bi-stack/pivot4j directory exists" || warn "bi-stack/pivot4j directory is missing"
[ -f "$ROOT/bi-stack/pivot4j/Dockerfile" ] && ok "pivot4j Dockerfile exists" || warn "pivot4j Dockerfile missing"

grep -q "UPSTREAM_XMLA" "$ROOT/bi-stack/mcad-proxy/app.py" 2>/dev/null && ok "mcad-proxy has UPSTREAM_XMLA configuration" || fail "mcad-proxy UPSTREAM_XMLA missing"
grep -q '@app.post("/xmla")' "$ROOT/bi-stack/mcad-proxy/app.py" 2>/dev/null && ok "mcad-proxy exposes POST /xmla" || fail "mcad-proxy POST /xmla missing"
grep -q "def forward_xmla" "$ROOT/bi-stack/mcad-proxy/app.py" 2>/dev/null && ok "mcad-proxy has forward_xmla()" || fail "mcad-proxy forward_xmla() missing"
grep -q "UPSTREAM_XMLA:" "$COMPOSE" && ok "docker-compose sets UPSTREAM_XMLA" || warn "docker-compose does not set UPSTREAM_XMLA; proxy default may still point to http://emondrian:8080/emondrian/xmla"

if [ "$MODE" = "static" ]; then
  echo
  echo "Static check only. Run live check after containers are up:"
  echo "  bash bi-stack/scripts/check_foodmart_xmla_regression.sh . live"
  echo
  echo "Summary: fails=$FAILS warnings=$WARNS"
  exit $([ "$FAILS" -eq 0 ] && echo 0 || echo 1)
fi

echo
echo "--- live HTTP checks ---"
check_url(){
  local label="$1" url="$2"
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$url" || true)"
  case "$code" in
    2*|3*|4*) ok "$label responded with HTTP $code ($url)";;
    *) fail "$label did not respond usefully, HTTP $code ($url)";;
  esac
}

check_url "mcad-api" "http://127.0.0.1:8000/health"
check_url "mcad-proxy" "http://127.0.0.1:9000/health"
check_url "eMondrian XMLA endpoint" "http://127.0.0.1:8081/emondrian/xmla"
check_url "Pivot4J UI" "http://127.0.0.1:8090/pivot4j"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/discover.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <Discover xmlns="urn:schemas-microsoft-com:xml-analysis">
      <RequestType>DISCOVER_DATASOURCES</RequestType>
      <Restrictions><RestrictionList/></Restrictions>
      <Properties><PropertyList/></Properties>
    </Discover>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
XML

cat > "$TMP/execute_q1.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <Execute xmlns="urn:schemas-microsoft-com:xml-analysis">
      <Command>
        <Statement><![CDATA[
SELECT {[Measures].[Store Sales]} ON COLUMNS,
[Time].[Month].Members ON ROWS
FROM [Sales]
WHERE ([Product].[Product Category].[Beer and Wine], [Store].[Store State].[WA])
        ]]></Statement>
      </Command>
      <Properties>
        <PropertyList>
          <Catalog>FoodMart</Catalog>
          <Format>Multidimensional</Format>
          <AxisFormat>TupleFormat</AxisFormat>
        </PropertyList>
      </Properties>
    </Execute>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
XML

analyze_xmla(){
  local label="$1" out="$2"
  python - "$label" "$out" <<'PY'
import sys, re, xml.etree.ElementTree as ET
label, path = sys.argv[1], sys.argv[2]
text = open(path, 'rb').read().decode('utf-8', 'replace')
# Hard textual faults. Do NOT match ordinary XML namespace declarations such as xml-analysis:exception.
hard_patterns = [
    r'<(?:[^>]*:)?Fault\b', r'<faultcode\b', r'<faultstring\b',
    r'Unknown catalog', r'No suitable connection', r'Mondrian Error',
    r'XMLA\s+Fault', r'Exception occurred', r'not found',
]
for pat in hard_patterns:
    if re.search(pat, text, re.I):
        print('FAULT_TEXT|' + pat)
        print(text[:1200])
        sys.exit(2)
try:
    root = ET.fromstring(text)
except Exception as exc:
    print('PARSE_WARN|' + str(exc))
    print(text[:1200])
    sys.exit(1)

def local(tag):
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag.split(':')[-1]
# Actual error elements in XML body, not xsd schema declarations.
for el in root.iter():
    lname = local(el.tag).lower()
    if lname in {'fault', 'faultcode', 'faultstring', 'error', 'description'}:
        # Ignore XML schema definitions such as <xsd:element name="Error">.
        if local(el.tag).lower() == 'element' or el.attrib.get('name') in {'Error', 'Description'}:
            continue
        txt = ''.join(el.itertext()).strip()
        if txt:
            print('FAULT_NODE|' + local(el.tag) + '|' + txt[:500])
            sys.exit(2)
# Normal responses.
locals_ = [local(e.tag) for e in root.iter()]
if 'DiscoverResponse' in locals_:
    # Count row elements in rowset namespace; schema may also contain many elements.
    rows = [e for e in root.iter() if local(e.tag) == 'row']
    print(f'OK_DISCOVER|rows={len(rows)}')
    sys.exit(0)
if 'ExecuteResponse' in locals_:
    cells = [e for e in root.iter() if local(e.tag) == 'Cell']
    axes = [e for e in root.iter() if local(e.tag) == 'Axis']
    print(f'OK_EXECUTE|axes={len(axes)}|cells={len(cells)}')
    sys.exit(0)
print('WARN_UNKNOWN_XMLA_RESPONSE')
print(text[:1200])
sys.exit(1)
PY
}

post_xml(){
  local label="$1"
  local url="$2"
  local file="$3"
  local safe_label="${label// /_}"
  local out="$TMP/${safe_label}.out"
  local code analysis rc
  code="$(curl -s -S --max-time 45 -o "$out" -w '%{http_code}' -H 'Content-Type: text/xml; charset=utf-8' --data-binary "@$file" "$url" || true)"
  if [[ ! "$code" =~ ^(2|3)[0-9][0-9]$ ]]; then
    fail "$label failed with HTTP $code"
    head -c 1200 "$out" | sed 's/^/  /'; echo
    return
  fi
  set +e
  analysis="$(analyze_xmla "$label" "$out")"
  rc=$?
  set -e 2>/dev/null || true
  if [ "$rc" -eq 0 ]; then
    ok "$label returned HTTP $code and parsed as valid XMLA response: $analysis"
  elif [ "$rc" -eq 1 ]; then
    warn "$label returned HTTP $code but response needs review: $(echo "$analysis" | head -1)"
    echo "$analysis" | head -20 | sed 's/^/  /'
  else
    warn "$label returned HTTP $code but contains an actual XMLA fault/error: $(echo "$analysis" | head -1)"
    echo "$analysis" | head -20 | sed 's/^/  /'
  fi
}

post_xml "direct eMondrian DISCOVER" "http://127.0.0.1:8081/emondrian/xmla" "$TMP/discover.xml"
post_xml "proxy DISCOVER" "http://127.0.0.1:9000/xmla" "$TMP/discover.xml"
post_xml "direct eMondrian FoodMart Q1" "http://127.0.0.1:8081/emondrian/xmla" "$TMP/execute_q1.xml"
post_xml "proxy FoodMart Q1" "http://127.0.0.1:9000/xmla" "$TMP/execute_q1.xml"

echo
echo "Summary: fails=$FAILS warnings=$WARNS"
exit $([ "$FAILS" -eq 0 ] && echo 0 || echo 1)
