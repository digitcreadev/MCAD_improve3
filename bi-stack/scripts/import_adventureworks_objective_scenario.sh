#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
BASE_URL="${MCAD_PROXY_BASE_URL:-http://127.0.0.1:9000}"
OBJECTIVE_FILE="$ROOT/bi-stack/objectives/objective_adventureworks_sales_margin_territory_month.json"
SCENARIO_FILE="$ROOT/bi-stack/direct-scenarios/adventureworks_sales_margin_territory_q1_q6.json"

printf '=== MCAD V9.5.2a AdventureWorks objective/scenario import ===\n'
printf 'repo_root=%s\n' "$ROOT"
printf 'base_url=%s\n' "$BASE_URL"

for f in "$OBJECTIVE_FILE" "$SCENARIO_FILE"; do
  if [[ ! -f "$f" ]]; then
    echo "[FAIL] Missing file: $f" >&2
    exit 1
  fi
done

python3 - <<'PY' "$BASE_URL" "$OBJECTIVE_FILE" "$SCENARIO_FILE"
import json, sys, time, urllib.request, urllib.error
base, objective_path, scenario_path = sys.argv[1:4]

def request_json(method, path, payload=None, attempts=1):
    url = base.rstrip('/') + path
    data = None
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
    last = None
    for _ in range(attempts):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode('utf-8', errors='replace')
                body = json.loads(raw or '{}') if raw.strip() else {}
                return r.status, body
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode('utf-8', errors='replace')
            try:
                body = json.loads(raw or '{}') if raw.strip() else {}
            except Exception:
                body = {'_raw_text': raw}
            body['_http_status'] = exc.code
            body['_url'] = url
            return exc.code, body
        except Exception as exc:
            last = exc
            time.sleep(1)
    raise RuntimeError(f'{method} {url} failed: {last}')

def assert_ok(label, status, data):
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if status >= 400 or not (isinstance(data, dict) and data.get('ok')):
        raise SystemExit(f'[FAIL] {label} failed: HTTP {status}; detail={json.dumps(data, ensure_ascii=False)[:2000]}')

for i in range(30):
    try:
        status, data = request_json('GET', '/health')
        if status == 200 and isinstance(data, dict) and data.get('ok'):
            break
    except Exception:
        pass
    time.sleep(1)
else:
    raise SystemExit('[FAIL] mcad-proxy did not become ready')

objective = json.load(open(objective_path, encoding='utf-8'))
scenario = json.load(open(scenario_path, encoding='utf-8'))

print('\n--- validate objective ---')
status, data = request_json('POST', '/mcad/objectives/validate', objective)
assert_ok('objective validation', status, data)

print('\n--- import objective ---')
status, data = request_json('POST', '/mcad/objectives/import', objective)
assert_ok('objective import', status, data)

print('\n--- validate scenario ---')
status, data = request_json('POST', '/bi/scenarios/validate', scenario)
assert_ok('scenario validation', status, data)

print('\n--- import scenario ---')
status, data = request_json('POST', '/bi/scenarios/import', scenario)
assert_ok('scenario import', status, data)

print('\n--- create AdventureWorks session smoke test ---')
status, data = request_json('POST', '/mcad/session/new', {
    'objective_id': objective['id'],
    'dw_id': 'adventureworks_sql_direct',
})
assert_ok('AdventureWorks session creation', status, data)

print('\n[OK] AdventureWorks objective/scenario pack imported and session creation works')
PY
