#!/usr/bin/env python3
from pathlib import Path
import csv, json, hashlib, sys
repo=Path(sys.argv[1] if len(sys.argv)>1 else ".").resolve()
r3=repo/"reports/article_experiments/nh_r3_end_to_end_resource_benchmark"
out=r3/"results"
summary=json.loads((out/"binding_summary.json").read_text())
expected={"full_sequence_rows":28800,"safe_pruned_rows":19496,"inadmissible_rows":2880,"unique_sessions":1200,
          "pilot_dev_sessions":20,"calibration_val_sessions":40,"confirmatory_test_sessions":300,"quota_fallback_test_sessions":120}
ok=True
for k,v in expected.items():
    got=summary.get(k)
    print(f"{k}={got} expected={v}")
    if got!=v: ok=False
# Verify all planned paths exist
with (out/"full_sequence_binding.csv").open(newline="",encoding="utf-8") as f:
    rows=list(csv.DictReader(f))
missing=[r["query_template_path"] for r in rows if not (r3/r["query_template_path"]).is_file()]
print("missing_template_bindings="+str(len(missing)))
if missing: ok=False
# Recompute deterministic binding hash
targets=["full_sequence_binding.csv","safe_pruned_counterfactual_binding.csv","inadmissible_control_binding.csv",
         "pilot_dev_sessions.csv","calibration_val_sessions.csv","confirmatory_test_sessions.csv",
         "confirmatory_test_quota_fallback_120.csv","binding_summary.json"]
h=hashlib.sha256()
for name in targets:
    p=out/name; h.update(name.encode()+b"\0"+p.read_bytes()+b"\0")
actual=h.hexdigest()
decl=(out/"BINDING_PLAN_SHA256.txt").read_text().split()[0]
print("binding_plan_declared="+decl)
print("binding_plan_actual="+actual)
if actual!=decl: ok=False
print("R3_BINDING_VERIFY="+("PASS" if ok else "FAIL"))
raise SystemExit(0 if ok else 1)
