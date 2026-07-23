#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
MODE="${2:-static}"
cd "$ROOT"
FAILS=0
WARNS=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

ok(){ echo "[OK] $*"; }
warn(){ echo "[WARN] $*"; WARNS=$((WARNS+1)); }
fail(){ echo "[FAIL] $*"; FAILS=$((FAILS+1)); }

is_real_fault_file(){
  local f="$1"
  grep -Eiq '<(soap:|SOAP-ENV:|SOAPENV:)?Fault\b|<faultcode\b|<faultstring\b|<Exception\b|<Error\b' "$f"
}
contains_valid_xmla_response(){
  local f="$1" kind="$2"
  if [[ "$kind" == "discover" ]]; then
    grep -q "DiscoverResponse" "$f"
  else
    grep -q "ExecuteResponse" "$f"
  fi
}

post_xmla(){
  local label="$1"
  local url="$2"
  local request_file="$3"
  local expected_kind="$4"
  local safe_label="${label// /_}"
  local out="$TMP/${safe_label}.xml"
  local code
  code=$(curl -sS -m 60 -o "$out" -w '%{http_code}' -H 'Content-Type: text/xml; charset=utf-8' --data-binary "@$request_file" "$url" || true)
  if [[ "$code" != "200" ]]; then
    warn "$label returned HTTP $code"
    sed -n '1,18p' "$out" | sed 's/^/  /' || true
    return 0
  fi
  if is_real_fault_file "$out"; then
    warn "$label returned HTTP 200 but contains a real SOAP/XMLA fault"
    sed -n '1,22p' "$out" | sed 's/^/  /' || true
    return 0
  fi
  if contains_valid_xmla_response "$out" "$expected_kind"; then
    ok "$label returned HTTP 200 and valid XMLA ${expected_kind} response"
    return 0
  fi
  warn "$label returned HTTP 200 but no expected XMLA ${expected_kind} response marker was found"
  sed -n '1,18p' "$out" | sed 's/^/  /' || true
}

cat > "$TMP/discover.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <Discover xmlns="urn:schemas-microsoft-com:xml-analysis">
      <RequestType>DISCOVER_DATASOURCES</RequestType>
      <Restrictions><RestrictionList/></Restrictions>
      <Properties><PropertyList/></Properties>
    </Discover>
  </soap:Body>
</soap:Envelope>
XML
cat > "$TMP/q1.xml" <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <Execute xmlns="urn:schemas-microsoft-com:xml-analysis">
      <Command>
        <Statement>SELECT {[Measures].[Store Sales]} ON COLUMNS, [Time].[Month].Members ON ROWS FROM [Sales] WHERE ([Product].[Product Category].[Beer and Wine], [Store].[Store State].[WA])</Statement>
      </Command>
      <Properties>
        <PropertyList>
          <Catalog>FoodMart</Catalog>
          <Format>Multidimensional</Format>
          <AxisFormat>TupleFormat</AxisFormat>
          <Content>Data</Content>
        </PropertyList>
      </Properties>
    </Execute>
  </soap:Body>
</soap:Envelope>
XML

echo "=== MCAD FoodMart XMLA/eMondrian regression check ==="
echo "repo_root=$ROOT"
echo "mode=$MODE"
echo
echo "--- docker compose services ---"
SERVICES="$(docker compose -f bi-stack/docker-compose.yml config --services 2>/dev/null || true)"
echo "$SERVICES"
echo
grep -q '^mcad-api$' <<<"$SERVICES" && ok "mcad-api service is declared" || fail "mcad-api service is missing"
grep -q '^mcad-proxy$' <<<"$SERVICES" && ok "mcad-proxy service is declared" || fail "mcad-proxy service is missing"
grep -Eq '^(emondrian|emondrian-foodmart)$' <<<"$SERVICES" && ok "FoodMart eMondrian service is declared" || fail "FoodMart eMondrian service is missing from docker-compose.yml"
grep -q '^pivot4j$' <<<"$SERVICES" && ok "pivot4j service is declared" || warn "pivot4j service is missing; useful for OLAP UI demo"

echo
echo "--- static file checks ---"
[[ -d bi-stack/emondrian ]] && ok "bi-stack/emondrian directory exists" || fail "bi-stack/emondrian directory missing"
[[ -f bi-stack/emondrian/Dockerfile ]] && ok "emondrian Dockerfile exists" || fail "emondrian Dockerfile missing"
[[ -d bi-stack/pivot4j ]] && ok "bi-stack/pivot4j directory exists" || warn "bi-stack/pivot4j directory missing"
[[ -f bi-stack/pivot4j/Dockerfile ]] && ok "pivot4j Dockerfile exists" || warn "pivot4j Dockerfile missing"
grep -q 'UPSTREAM_XMLA' bi-stack/mcad-proxy/app.py && ok "mcad-proxy has UPSTREAM_XMLA configuration" || fail "mcad-proxy missing UPSTREAM_XMLA"
grep -q '@app.post("/xmla")' bi-stack/mcad-proxy/app.py && ok "mcad-proxy exposes POST /xmla" || fail "mcad-proxy missing POST /xmla"
grep -q 'get_gateway().execute' bi-stack/mcad-proxy/app.py && ok "/bi/execute is wired to the hybrid execution gateway" || fail "/bi/execute still appears to bypass the gateway"
grep -q 'UPSTREAM_XMLA' bi-stack/docker-compose.yml && ok "docker-compose sets UPSTREAM_XMLA" || warn "docker-compose does not set UPSTREAM_XMLA"
grep -q 'foodmart_sql_direct' bi-stack/mcad-proxy/datawarehouses.yaml && ok "FoodMart Direct BI option is registered" || fail "foodmart_sql_direct is missing from DW registry"

if [[ "$MODE" != "live" ]]; then
  echo
  echo "Static check only. Run live check after containers are up:"
  echo "  bash bi-stack/scripts/check_foodmart_xmla_regression.sh . live"
  echo
  echo "Summary: fails=$FAILS warnings=$WARNS"
  exit 0
fi

echo
echo "--- live HTTP checks ---"
for spec in \
  "mcad-api|http://127.0.0.1:8000/health|200" \
  "mcad-proxy|http://127.0.0.1:9000/health|200" \
  "eMondrian XMLA endpoint|http://127.0.0.1:8081/emondrian/xmla|405" \
  "Pivot4J UI|http://127.0.0.1:8090/pivot4j|302"; do
  IFS='|' read -r label url expected <<<"$spec"
  code=$(curl -sS -m 12 -o /dev/null -w '%{http_code}' "$url" || true)
  if [[ "$code" == "$expected" ]]; then ok "$label responded with HTTP $code ($url)"; else warn "$label responded with HTTP $code, expected $expected ($url)"; fi
done

post_xmla "direct eMondrian DISCOVER" "http://127.0.0.1:8081/emondrian/xmla" "$TMP/discover.xml" discover
post_xmla "proxy DISCOVER" "http://127.0.0.1:9000/xmla" "$TMP/discover.xml" discover
post_xmla "direct eMondrian FoodMart Q1" "http://127.0.0.1:8081/emondrian/xmla" "$TMP/q1.xml" execute
proxy_q1_response="$TMP/proxy_foodmart_q1.response.xml"
proxy_q1_code=$(curl -sS -m 60 -o "$proxy_q1_response" -w "%{http_code}" \
  -H "Content-Type: text/xml" \
  --data-binary @"$TMP/q1.xml" \
  "http://127.0.0.1:9000/xmla" || true)

if [[ "$proxy_q1_code" == "200" ]] && grep -Eq "ExecuteResponse|<ExecuteResponse" "$proxy_q1_response"; then
  ok "proxy FoodMart Q1 returned HTTP 200 and valid XMLA execute response"
elif [[ "$proxy_q1_code" == "200" ]] && grep -q "MCAD BLOCK" "$proxy_q1_response"; then
  ok "proxy FoodMart Q1 reached MCAD gateway and was blocked by session policy"
else
  warn "proxy FoodMart Q1 returned HTTP $proxy_q1_code but did not contain ExecuteResponse or MCAD BLOCK"
  sed -n '1,40p' "$proxy_q1_response" || true
fi

echo
echo "Summary: fails=$FAILS warnings=$WARNS"
exit 0
