#!/usr/bin/env python3
from pathlib import Path
import csv, json, re, hashlib, sys, collections

repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
r2 = repo / "reports/article_experiments/nh_r2_objective_preserving_pruning/results"
r3 = repo / "reports/article_experiments/nh_r3_end_to_end_resource_benchmark"
out = r3 / "results"
out.mkdir(parents=True, exist_ok=True)

def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

dec = read_csv(r2/"decision_records.csv")
safe = [r for r in dec if r.get("policy") == "SAFE_PRUNING"]
if len(safe) != 28800:
    raise SystemExit(f"expected 28800 SAFE_PRUNING decision rows, got {len(safe)}")

def archetype(qid):
    m = re.search(r"-Q\d+-(.+)$", qid or "")
    label = m.group(1) if m else (qid or "")
    for p in ("ATOM","PAIR","REPEAT","DIST","INAD","RPT","DST","MIX"):
        if label == p or label.startswith(p+"_"):
            return p
    return "OTHER"

atom_templates = ["AW_ATOM_SALES","AW_ATOM_COST","AW_ATOM_MARGIN"]
def bind(row):
    a = archetype(row.get("query_id",""))
    ev = row.get("evidence_atoms","") or row.get("query_id","")
    if a in ("ATOM","REPEAT","RPT"):
        idx = int(hashlib.sha256(ev.encode()).hexdigest()[:8],16) % 3
        tid = atom_templates[idx]
    elif a == "PAIR":
        tid = "AW_PAIR_SALES_COST"
    elif a == "MIX":
        tid = "AW_MIX_ACCESSORIES_SALES_COST"
    elif a in ("DIST","DST"):
        tid = "AW_DISTRACTOR_ACCESSORIES_SALES"
    elif a == "INAD":
        tid = "AW_BAD_GRAIN_YEAR"
    else:
        raise SystemExit(f"unmapped archetype {a} for {row.get('query_id')}")
    return a, tid

fields = [
    "session_id","split","topology","pattern","candidate_index","query_id",
    "class","reason","operational_action","proof_status","evidence_atoms",
    "archetype","warehouse_id","backend_adapter","template_id",
    "query_template_path","parameter_binding","binding_status"
]
full=[]
for r in safe:
    a, tid = bind(r)
    full.append({
        **{k:r.get(k,"") for k in fields if k in r},
        "session_id":r.get("session_id",""),
        "split":r.get("split",""),
        "topology":r.get("topology",""),
        "pattern":r.get("pattern",""),
        "candidate_index":r.get("candidate_index",""),
        "query_id":r.get("query_id",""),
        "class":r.get("class",""),
        "reason":r.get("reason",""),
        "operational_action":r.get("operational_action",""),
        "proof_status":r.get("proof_status",""),
        "evidence_atoms":r.get("evidence_atoms",""),
        "archetype":a,
        "warehouse_id":"adventureworks_sql_direct",
        "backend_adapter":"adventureworks_direct",
        "template_id":tid,
        "query_template_path":f"templates/mdx/{tid}.mdx",
        "parameter_binding":json.dumps({"product_category":"Bikes" if tid not in ("AW_DISTRACTOR_ACCESSORIES_SALES","AW_MIX_ACCESSORIES_SALES_COST") else "Accessories","territory_group":"Europe","calendar_year":2013}, sort_keys=True, separators=(",",":")),
        "binding_status":"PLANNED_NOT_EXECUTED"
    })

def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)

write_csv(out/"full_sequence_binding.csv", full)
pruned=[r for r in full if r["operational_action"]=="PRUNE"]
inad=[r for r in full if r["class"]=="INADMISSIBLE"]
write_csv(out/"safe_pruned_counterfactual_binding.csv", pruned)
write_csv(out/"inadmissible_control_binding.csv", inad)

# deterministic session selections
by_stratum=collections.defaultdict(list)
for r in full:
    by_stratum[(r["split"],r["topology"],r["pattern"])].append(r["session_id"])
sessions={k:sorted(set(v)) for k,v in by_stratum.items()}

sel_fields=["split","topology","pattern","session_id","selection_role"]
def selection(split, n=None, role=""):
    rows=[]
    for (sp,t,p), ss in sorted(sessions.items()):
        if sp != split: continue
        chosen=ss if n is None else ss[:n]
        for s in chosen:
            rows.append({"split":sp,"topology":t,"pattern":p,"session_id":s,"selection_role":role})
    return rows

for name, rows in [
    ("pilot_dev_sessions.csv", selection("dev",1,"INSTRUMENTATION_PILOT")),
    ("calibration_val_sessions.csv", selection("val",2,"CALIBRATION_NO_EFFECT_TUNING")),
    ("confirmatory_test_sessions.csv", selection("test",None,"CONFIRMATORY_PRIMARY")),
    ("confirmatory_test_quota_fallback_120.csv", selection("test",6,"RESOURCE_CONSTRAINED_FALLBACK"))
]:
    with (out/name).open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=sel_fields); w.writeheader(); w.writerows(rows)

summary={
    "full_sequence_rows":len(full),
    "safe_pruned_rows":len(pruned),
    "inadmissible_rows":len(inad),
    "unique_sessions":len(set(r["session_id"] for r in full)),
    "archetype_counts":dict(sorted(collections.Counter(r["archetype"] for r in full).items())),
    "template_counts":dict(sorted(collections.Counter(r["template_id"] for r in full).items())),
    "pilot_dev_sessions":len(selection("dev",1)),
    "calibration_val_sessions":len(selection("val",2)),
    "confirmatory_test_sessions":len(selection("test",None)),
    "quota_fallback_test_sessions":len(selection("test",6)),
    "binding_kind":"deterministic_workload_embedding_v1",
    "claim_status":"PLANNED_NOT_EXECUTED"
}
(out/"binding_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")

# content hash of binding outputs, path-stable and timestamp-free
targets=[
 "full_sequence_binding.csv","safe_pruned_counterfactual_binding.csv","inadmissible_control_binding.csv",
 "pilot_dev_sessions.csv","calibration_val_sessions.csv","confirmatory_test_sessions.csv",
 "confirmatory_test_quota_fallback_120.csv","binding_summary.json"
]
h=hashlib.sha256()
for name in targets:
    p=out/name
    h.update(name.encode()+b"\0"+p.read_bytes()+b"\0")
digest=h.hexdigest()
(out/"BINDING_PLAN_SHA256.txt").write_text(digest+"  deterministic_binding_plan_v1\n",encoding="utf-8")
print(json.dumps(summary,indent=2,sort_keys=True))
print("binding_plan_sha256="+digest)
