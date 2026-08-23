#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, hashlib, importlib.util, json, sys
from pathlib import Path

R3_REL=Path("reports/article_experiments/nh_r3_end_to_end_resource_benchmark")
EXPECTED_CONTRACT_SHA="0d0c173cc088dcb741883b8e8897da248797c4c66ce3c78471dc36ad536f1444"
EXPECTED_SCHEDULE_SHA="4aede87cb911e5ce9baf0f372c011eb6435a6fd1f3411529577ccdbfe5ab6b70"
EXPECTED_PLAN_SHA="76d44e02ae57edd5caa570833e02f65bbabaf361c8e7da6c3c089f6cf065a551"
EXPECTED_BINDING="a97a525e3766ca5aaadf8de3a8ccb200ea682cdfdbfd4eca71abc03834903dff"
EXPECTED_SEED="b66d344968cfa632afc25025b772c49eb8d03bc60ec631c26db703740e730462"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_module(path: Path):
    spec=importlib.util.spec_from_file_location("r3_c1_validation_plan_static", path)
    if spec is None or spec.loader is None: raise RuntimeError("cannot load plan module")
    mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; spec.loader.exec_module(mod); return mod

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repo",default="."); args=ap.parse_args()
    repo=Path(args.repo).resolve(); r3=repo/R3_REL
    contract=r3/"config/r3_c1_validation_stage_contract.json"
    schedule=r3/"config/r3_c1_arm_order_schedule.csv"
    plan_path=r3/"implementation/r3_c1_validation_plan.py"
    if sha(contract)!=EXPECTED_CONTRACT_SHA: raise SystemExit("contract hash mismatch")
    if sha(schedule)!=EXPECTED_SCHEDULE_SHA: raise SystemExit("schedule hash mismatch")
    if sha(plan_path)!=EXPECTED_PLAN_SHA: raise SystemExit("plan hash mismatch")
    d=json.loads(contract.read_text(encoding="utf-8"))
    assert d["stage"]=="R3-C_VALIDATION_CALIBRATION"
    assert d["frozen_scientific_authorities"]["binding_plan_sha256"]==EXPECTED_BINDING
    assert d["validation_cohort"]["semantic_sessions"]==40
    assert d["validation_cohort"]["frozen_candidate_rows"]==960
    assert d["arm_order_randomization"]["seed_sha256"]==EXPECTED_SEED
    assert d["arm_order_randomization"]["schedule_sha256"]==EXPECTED_SCHEDULE_SHA
    assert d["static_plan"]["sha256"]==EXPECTED_PLAN_SHA
    assert d["static_plan"]["arm_runs"]==120 and d["static_plan"]["candidate_actions"]==2880
    assert d["scientific_reuse"]["effect_size_tuning_allowed"] is False
    assert d["scientific_reuse"]["scientific_redesign_allowed"] is False
    assert d["scientific_reuse"]["binding_change_allowed"] is False
    assert d["scientific_reuse"]["live_gate_may_relabel_frozen_action"] is False
    assert d["authorization"]["measurement_authorized"] is False
    assert d["authorization"]["backend_query_authorized"] is False
    assert d["authorization"]["docker_or_service_mutation_authorized"] is False
    assert d["authorization"]["confirmatory_claim_authorized"] is False

    source=plan_path.read_text(encoding="utf-8")
    tree=ast.parse(source)
    defined={n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    if "frozen_gate_rule" in defined or "frozen_full_execute_rule" in defined:
        raise SystemExit("frozen scientific rules were reimplemented")
    forbidden=("requests", "urllib", "socket", "docker", "/bi/r3/measurement", "run_pilot(", "subprocess")
    lower=source.lower()
    for token in forbidden:
        if token.lower() in lower: raise SystemExit(f"forbidden static-plan token: {token}")
    if "frozen.frozen_gate_rule" not in source or "frozen.frozen_full_execute_rule" not in source:
        raise SystemExit("frozen runner scientific-rule reuse missing")

    mod=load_module(plan_path); p=mod.build_plan(repo)
    assert p["semantic_sessions"]==40
    assert len(p["arm_runs"])==120
    assert len(p["candidate_actions"])==2880
    assert p["gated_arm_runs"]==80 and p["ungated_arm_runs"]==40
    assert p["gate_evaluations_planned"]==1920
    assert p["mcad_api_restarts_planned"]==120 and p["fresh_mcad_sessions_planned"]==80
    assert len(p["unique_templates_lexicographic"])==7
    assert p["binding_plan_sha256"]==EXPECTED_BINDING
    assert p["arm_schedule_sha256"]==EXPECTED_SCHEDULE_SHA
    assert p["seed_sha256"]==EXPECTED_SEED
    assert p["measurement_authorized"] is False and p["measurement_executed"] is False
    assert p["confirmatory_claim_authorized"] is False
    assert p["effect_size_tuning_performed"] is False and p["scientific_redesign_performed"] is False
    for c in p["arm_position_counts"]:
        vals=list(c.values()); assert max(vals)-min(vals)<=1
    print("r3c_semantic_sessions=40")
    print("r3c_arm_runs=120")
    print("r3c_candidate_actions=2880")
    print("r3c_gate_evaluations_planned=1920")
    print("r3c_gated_arms=80")
    print("r3c_ungated_arms=40")
    print("r3c_api_restarts_planned=120")
    print("r3c_fresh_gated_sessions_planned=80")
    print("r3c_unique_templates=7")
    print("effect_size_tuning_performed=false")
    print("scientific_redesign_performed=false")
    print("measurement_executed=false")
    print("docker_commands_executed=false")
    print("R3_C1_VALIDATION_STAGE_STATIC_VERIFY=PASS")

if __name__=="__main__": main()
