#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, sys, importlib.util

repo=Path(sys.argv[1] if len(sys.argv)>1 else ".").resolve()
r3=repo/"reports/article_experiments/nh_r3_end_to_end_resource_benchmark"
expected_binding="a97a525e3766ca5aaadf8de3a8ccb200ea682cdfdbfd4eca71abc03834903dff"
ok=True

def check(name, cond, detail=""):
    global ok
    print(f"{name}={'PASS' if cond else 'FAIL'}{(' '+detail) if detail else ''}")
    if not cond: ok=False

binding=(r3/"results/BINDING_PLAN_SHA256.txt").read_text().split()[0]
check("binding_digest_unchanged", binding==expected_binding, binding)

cfg=json.loads((r3/"config/r3_protocol.json").read_text())
metrics=cfg["measurement"]["primary_metrics"]
check("new_completion_metric_present","time_to_analytical_objective_completion_ms" in metrics)
check("old_completion_metric_absent","time_to_objective_ms" not in metrics)
ref=cfg.get("semantic_refinement_a2") or {}
check("binding_change_false", ref.get("binding_change") is False)
check("dax_not_claimed", ref.get("universal_language_support_claim") is False)

for rel in [
    "docs/FORMAL_REFINEMENT_A2.md",
    "docs/CANONICAL_QUERY_PROFILE_CONTRACT.md",
    "docs/EVIDENCE_REALIZABILITY_CONTRACT.md",
    "docs/RELATED_WORK_POSITIONING_A2.md",
]:
    check("doc_"+Path(rel).stem, (r3/rel).is_file())

# Load query_plan directly to avoid importing the full backend app.
qp_path=repo/"backend/mcad/query_plan.py"
spec=importlib.util.spec_from_file_location("mcad_query_plan_a2_verify", qp_path)
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
sql="SELECT SUM(store_sales) AS sales FROM sales WHERE year = 1998 GROUP BY month"
sql_qp=mod.parse_sql_analytic(sql)
required={"measures","group_by","slicers","analytics","aggregators","language","window_start","window_end"}
check("sql_cqp_required_fields", required.issubset(sql_qp.keys()), str(sorted(required-set(sql_qp.keys()))))
check("sql_cqp_language", sql_qp.get("language")=="sql")

# Static MDX parser contract: direct import as sibling package is intentionally avoided.
mdx_src=(repo/"backend/mcad/mdx_parser.py").read_text()
for token in ["'measures': measures","'group_by': group_by","'slicers': slicers","'analytics': analytics","'language': 'mdx'"]:
    check("mdx_cqp_token_"+hashlib.sha256(token.encode()).hexdigest()[:8], token in mdx_src)

query_plan_src=qp_path.read_text()
check("extract_query_plan_sql", "if lang == 'sql'" in query_plan_src)
check("extract_query_plan_mdx", "if lang == 'mdx'" in query_plan_src)
check("unsupported_languages_rejected", "Unsupported analytical language" in query_plan_src)
check("no_dax_implementation_claim", "lang == 'dax'" not in query_plan_src.lower())

formal=(repo/"backend/mcad/formal_sat.py").read_text()
check("nvac_probe_present","nvac_probe" in formal and "_sat_check_nvac_ok" in formal)
check("nvac_part_of_overall_gate","sat = all(checks.values())" in formal)

ckg=(repo/"backend/ckg/ckg_updater.py").read_text()
for token in ["HAS_CONSTRAINT","REQUIRES_NV","requirement_sets","classify_constraint_states","state = \"partial\"","state = \"total\""]:
    check("ckg_contract_"+hashlib.sha256(token.encode()).hexdigest()[:8], token in ckg)

direct=(repo/"bi-stack/mcad-proxy/execution/adapters/adventureworks_direct_adapter.py").read_text()
xmla=(repo/"bi-stack/mcad-proxy/execution/adapters/xmla_mondrian_adapter.py").read_text()
check("direct_accepts_mdx", 'qtype in {"mdx", "mdx_or_sql"}' in direct)
check("direct_maps_mdx_to_sql","_mdx_to_sql" in direct)
check("xmla_mdx_path",'logical_query_language": "mdx"' in xmla or "query_language=\"mdx\"" in xmla)

print("NO_BACKEND_EXECUTION_PERFORMED=true")
print("R3_A2_SEMANTIC_REFINEMENT_VERIFY="+("PASS" if ok else "FAIL"))
raise SystemExit(0 if ok else 1)
