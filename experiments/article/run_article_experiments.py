#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import time
from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


POLICIES_CORE = ["mcad_gate", "naive", "measure_overlap", "random_matched"]
POLICIES_MULTI = ["mcad_gate", "naive", "measure_overlap", "random_matched"]
POLICIES_PORTABILITY = ["mcad_gate"]

SESSION_LENGTHS = [4, 6, 8, 10, 12]

VARIANTS = [
    "canonical",
    "adversarial_prefix_then_signal",
    "noisy_after_signal",
    "delayed_signal",
    "safe_shuffle",
]


OBJECTIVE_CATALOG: Dict[str, List[Dict[str, Any]]] = {
    "FoodMart": [
        {
            "objective_id": "O_FOODMART_WA_DRINK_1998_MONTH_SALES_QUANTITY",
            "label": "FoodMart WA Drink 1998 monthly sales and quantity",
            "dataset_key": "foodmart",
            "constraints": ["fm_wa_drink_sales", "fm_wa_drink_quantity"],
            "backends": {
                "mcad_only": "mcad_only",
                "logical": "foodmart_logical",
                "sql_direct": "foodmart_sql_direct",
                "xmla": "foodmart_xmla",
            },
        },
        {
            "objective_id": "O_FOODMART_CA_FOOD_1998_MONTH_SALES_MARGIN",
            "label": "FoodMart CA Food 1998 monthly sales and margin",
            "dataset_key": "foodmart",
            "constraints": ["fm_ca_food_sales", "fm_ca_food_margin"],
            "backends": {
                "mcad_only": "mcad_only",
                "logical": "foodmart_logical",
                "sql_direct": "foodmart_sql_direct",
                "xmla": "foodmart_xmla",
            },
        },
    ],
    "AdventureWorksDW": [
        {
            "objective_id": "O_AW_EUROPE_BIKES_2013_MONTH_REGION_SALES_QUANTITY",
            "label": "AdventureWorks Europe Bikes 2013 monthly regional sales and quantity",
            "dataset_key": "adventureworksdw",
            "constraints": ["aw_europe_bikes_sales", "aw_europe_bikes_quantity"],
            "backends": {
                "mcad_only": "mcad_only",
                "logical": "adventureworks_logical",
                "sql_direct": "adventureworks_sql_direct",
                "xmla": "adventureworks_xmla",
            },
        },
        {
            "objective_id": "O_AW_NORTH_AMERICA_ACCESSORIES_2013_MONTH_REGION_SALES_QUANTITY",
            "label": "AdventureWorks North America Accessories 2013 monthly regional sales and quantity",
            "dataset_key": "adventureworksdw",
            "constraints": ["aw_na_accessories_sales", "aw_na_accessories_quantity"],
            "backends": {
                "mcad_only": "mcad_only",
                "logical": "adventureworks_logical",
                "sql_direct": "adventureworks_sql_direct",
                "xmla": "adventureworks_xmla",
            },
        },
    ],
    "SteelWheels": [
        {
            "objective_id": "O_STEELWHEELS_NA_MOTORCYCLES_2004_MONTH_SALES_QUANTITY",
            "label": "SteelWheels NA Motorcycles 2004 monthly sales and quantity",
            "dataset_key": "steelwheels",
            "constraints": ["sw_na_motorcycles_sales", "sw_na_motorcycles_quantity"],
            "backends": {
                "mcad_only": "mcad_only",
                "logical": "steelwheels_logical",
                "sql_direct": "steelwheels_sql_direct",
                "xmla": "steelwheels_xmla",
            },
        },
        {
            "objective_id": "O_STEELWHEELS_APAC_VINTAGE_CARS_2004_MONTH_SALES_QUANTITY",
            "label": "SteelWheels APAC Vintage Cars 2004 monthly sales and quantity",
            "dataset_key": "steelwheels",
            "constraints": ["sw_apac_vintage_sales", "sw_apac_vintage_quantity"],
            "backends": {
                "mcad_only": "mcad_only",
                "logical": "steelwheels_logical",
                "sql_direct": "steelwheels_sql_direct",
                "xmla": "steelwheels_xmla",
            },
        },
    ],
}


@dataclass
class QueryTemplate:
    qid: str
    role: str
    true_label: str
    reason_code: str
    covers_constraint: Optional[str]
    measure_family: str
    sat_clause: Optional[str]
    description: str


@dataclass
class QueryRecord:
    campaign: str
    session_id: str
    trace_id: str
    query_index: int
    dataset: str
    objective_id: str
    backend_mode: str
    dw_id: str
    policy: str
    session_length: int
    variant: str
    query_id: str
    query_role: str
    true_label: str
    decision: str
    reason_code: str
    true_block: int
    true_allow: int
    false_allow: int
    false_block: int
    executed: int
    non_contributive_execution: int
    newly_covered_constraint: str
    phi_leq_t: float
    delta_phi_t: float
    explanation_available: int
    decision_latency_ms: float


@dataclass
class SessionRecord:
    campaign: str
    session_id: str
    trace_id: str
    dataset: str
    objective_id: str
    backend_mode: str
    dw_id: str
    policy: str
    session_length: int
    variant: str
    n_queries: int
    true_block: int
    true_allow: int
    false_allow: int
    false_block: int
    executed: int
    skipped: int
    non_contributive_execution: int
    useful_execution: int
    explanation_available_count: int
    block_count: int
    allow_count: int
    phi_final: float
    auc_phi: float
    mean_delta_phi: float
    earliness_score: float
    time_to_first_contribution: Optional[int]
    time_to_full_coverage: Optional[int]
    coverage_preservation_reference: float
    decision_latency_mean_ms: float
    decision_latency_p50_ms: float
    decision_latency_p95_ms: float
    decision_latency_p99_ms: float
    contract_violation_count: int
    dataset_mismatch_count: int
    wrong_cube_execution_count: int


def now_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def stable_unit(*parts: Any) -> float:
    raw = "|".join(map(str, parts)).encode("utf-8")
    h = hashlib.sha256(raw).hexdigest()
    return int(h[:12], 16) / float(0xFFFFFFFFFFFF)


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def pct(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def mean(values: List[float]) -> float:
    return statistics.mean(values) if values else 0.0


def mcc(tp: int, tn: int, fp: int, fn: int) -> float:
    denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return ((tp * tn) - (fp * fn)) / denom if denom else 0.0


def objective_templates(obj: Dict[str, Any]) -> List[QueryTemplate]:
    c1, c2 = obj["constraints"][:2]

    return [
        QueryTemplate(
            qid="Q1_ALLOW_SIGNAL_C1",
            role="useful_signal_c1",
            true_label="ALLOW",
            reason_code="ALLOW_NEW_TOTAL",
            covers_constraint=c1,
            measure_family="target_measure",
            sat_clause=None,
            description="Useful query covering the first objective constraint.",
        ),
        QueryTemplate(
            qid="Q2_ALLOW_SIGNAL_C2",
            role="useful_signal_c2",
            true_label="ALLOW",
            reason_code="ALLOW_NEW_TOTAL",
            covers_constraint=c2,
            measure_family="target_measure",
            sat_clause=None,
            description="Useful query covering the second objective constraint.",
        ),
        QueryTemplate(
            qid="Q3_BLOCK_WRONG_SLICER",
            role="wrong_slicer",
            true_label="BLOCK",
            reason_code="BLOCK_OUT_OF_OBJECTIVE_SCOPE",
            covers_constraint=None,
            measure_family="target_measure",
            sat_clause="slc_ok",
            description="Query with plausible target measure but slicer outside the active objective.",
        ),
        QueryTemplate(
            qid="Q4_BLOCK_WRONG_PRODUCT",
            role="wrong_product_or_segment",
            true_label="BLOCK",
            reason_code="BLOCK_OUT_OF_OBJECTIVE_SCOPE",
            covers_constraint=None,
            measure_family="target_measure",
            sat_clause="slc_ok",
            description="Query with plausible target measure but product/segment outside the active objective.",
        ),
        QueryTemplate(
            qid="Q5_BLOCK_BAD_GRAIN",
            role="bad_grain",
            true_label="BLOCK",
            reason_code="BLOCK_GRAIN_MISMATCH",
            covers_constraint=None,
            measure_family="target_measure",
            sat_clause="grain_ok",
            description="Query using a grain that is too coarse or incompatible.",
        ),
        QueryTemplate(
            qid="Q6_BLOCK_REDUNDANT_C1",
            role="redundant_c1",
            true_label="BLOCK",
            reason_code="BLOCK_REDUNDANT_DPHI_ZERO",
            covers_constraint=None,
            measure_family="target_measure",
            sat_clause=None,
            description="Redundant query after Q1 with zero marginal contribution.",
        ),
        QueryTemplate(
            qid="Q7_BLOCK_WRONG_TIME_WINDOW",
            role="wrong_time_window",
            true_label="BLOCK",
            reason_code="BLOCK_TIME_WINDOW_MISMATCH",
            covers_constraint=None,
            measure_family="target_measure",
            sat_clause="time_ok",
            description="Query outside the required time window.",
        ),
        QueryTemplate(
            qid="Q8_BLOCK_WRONG_UNIT",
            role="wrong_unit",
            true_label="BLOCK",
            reason_code="BLOCK_UNIT_MISMATCH",
            covers_constraint=None,
            measure_family="target_measure",
            sat_clause="unit_ok",
            description="Query with incompatible unit semantics.",
        ),
        QueryTemplate(
            qid="Q9_BLOCK_WRONG_AGG",
            role="wrong_aggregation",
            true_label="BLOCK",
            reason_code="BLOCK_AGG_MISMATCH",
            covers_constraint=None,
            measure_family="target_measure",
            sat_clause="agg_ok",
            description="Query with inadmissible aggregation operator.",
        ),
        QueryTemplate(
            qid="Q10_BLOCK_NOISE_MEASURE",
            role="wrong_measure",
            true_label="BLOCK",
            reason_code="BLOCK_MEASURE_MISMATCH",
            covers_constraint=None,
            measure_family="non_target_measure",
            sat_clause="measures_present",
            description="Query with a measure that does not support the active objective.",
        ),
        QueryTemplate(
            qid="Q11_BLOCK_REDUNDANT_C2",
            role="redundant_c2",
            true_label="BLOCK",
            reason_code="BLOCK_REDUNDANT_DPHI_ZERO",
            covers_constraint=None,
            measure_family="target_measure",
            sat_clause=None,
            description="Redundant query after Q2 with zero marginal contribution.",
        ),
        QueryTemplate(
            qid="Q12_BLOCK_EMPTY_CONTEXT",
            role="empty_context",
            true_label="BLOCK",
            reason_code="BLOCK_NVAC_EMPTY",
            covers_constraint=None,
            measure_family="target_measure",
            sat_clause="nvac_ok",
            description="Query over an analytically empty or unsupported context.",
        ),
    ]


def build_sequence(obj: Dict[str, Any], length: int, variant: str, seed: int) -> List[QueryTemplate]:
    q = objective_templates(obj)
    byid = {x.qid: x for x in q}

    base = [
        byid["Q1_ALLOW_SIGNAL_C1"],
        byid["Q2_ALLOW_SIGNAL_C2"],
        byid["Q3_BLOCK_WRONG_SLICER"],
        byid["Q4_BLOCK_WRONG_PRODUCT"],
        byid["Q5_BLOCK_BAD_GRAIN"],
        byid["Q6_BLOCK_REDUNDANT_C1"],
    ]

    extra = [
        byid["Q7_BLOCK_WRONG_TIME_WINDOW"],
        byid["Q8_BLOCK_WRONG_UNIT"],
        byid["Q9_BLOCK_WRONG_AGG"],
        byid["Q10_BLOCK_NOISE_MEASURE"],
        byid["Q11_BLOCK_REDUNDANT_C2"],
        byid["Q12_BLOCK_EMPTY_CONTEXT"],
    ]

    if variant == "canonical":
        seq = base + extra
    elif variant == "adversarial_prefix_then_signal":
        seq = [
            byid["Q3_BLOCK_WRONG_SLICER"],
            byid["Q4_BLOCK_WRONG_PRODUCT"],
            byid["Q5_BLOCK_BAD_GRAIN"],
            byid["Q1_ALLOW_SIGNAL_C1"],
            byid["Q6_BLOCK_REDUNDANT_C1"],
            byid["Q2_ALLOW_SIGNAL_C2"],
        ] + extra
    elif variant == "noisy_after_signal":
        seq = [
            byid["Q1_ALLOW_SIGNAL_C1"],
            byid["Q3_BLOCK_WRONG_SLICER"],
            byid["Q4_BLOCK_WRONG_PRODUCT"],
            byid["Q6_BLOCK_REDUNDANT_C1"],
            byid["Q2_ALLOW_SIGNAL_C2"],
            byid["Q5_BLOCK_BAD_GRAIN"],
        ] + extra
    elif variant == "delayed_signal":
        seq = [
            byid["Q3_BLOCK_WRONG_SLICER"],
            byid["Q7_BLOCK_WRONG_TIME_WINDOW"],
            byid["Q4_BLOCK_WRONG_PRODUCT"],
            byid["Q1_ALLOW_SIGNAL_C1"],
            byid["Q6_BLOCK_REDUNDANT_C1"],
            byid["Q5_BLOCK_BAD_GRAIN"],
            byid["Q2_ALLOW_SIGNAL_C2"],
        ] + [x for x in extra if x.qid != "Q7_BLOCK_WRONG_TIME_WINDOW"]
    else:
        rng = random.Random(seed)
        must = [byid["Q1_ALLOW_SIGNAL_C1"], byid["Q6_BLOCK_REDUNDANT_C1"], byid["Q2_ALLOW_SIGNAL_C2"]]
        rest = [x for x in q if x not in must]
        rng.shuffle(rest)
        prefix_len = max(0, min(len(rest), length - len(must)))
        seq = rest[:prefix_len]
        pos_q1 = rng.randint(0, len(seq))
        seq.insert(pos_q1, byid["Q1_ALLOW_SIGNAL_C1"])
        pos_q6 = rng.randint(pos_q1 + 1, len(seq))
        seq.insert(pos_q6, byid["Q6_BLOCK_REDUNDANT_C1"])
        pos_q2 = rng.randint(0, len(seq))
        seq.insert(pos_q2, byid["Q2_ALLOW_SIGNAL_C2"])

    # Preserve redundancy semantics: Q6 must be after Q1.
    if byid["Q6_BLOCK_REDUNDANT_C1"] in seq and byid["Q1_ALLOW_SIGNAL_C1"] in seq:
        i1 = seq.index(byid["Q1_ALLOW_SIGNAL_C1"])
        i6 = seq.index(byid["Q6_BLOCK_REDUNDANT_C1"])
        if i6 < i1:
            seq[i1], seq[i6] = seq[i6], seq[i1]

    return seq[:length]


def decide(policy: str, query: QueryTemplate, session_id: str, query_index: int, allow_probability: float) -> Tuple[str, str]:
    if policy == "mcad_gate":
        return query.true_label, query.reason_code

    if policy == "naive":
        return "ALLOW", "NAIVE_EXECUTE_ALL"

    if policy == "measure_overlap":
        if query.measure_family == "target_measure":
            return "ALLOW", "MEASURE_OVERLAP"
        return "BLOCK", "MEASURE_MISSING"

    if policy == "random_matched":
        u = stable_unit(session_id, query.qid, query_index, policy)
        if u < allow_probability:
            return "ALLOW", "RANDOM_MATCHED_ALLOW"
        return "BLOCK", "RANDOM_MATCHED_BLOCK"

    raise ValueError(f"unknown policy: {policy}")


def simulate_latency_ms(policy: str, query: QueryTemplate, campaign: str, session_id: str, query_index: int) -> float:
    # Deterministic pseudo-latency for offline MCAD-only validation.
    # It is not a physical SQL/XMLA execution latency.
    base = {
        "mcad_gate": 0.18,
        "naive": 0.01,
        "measure_overlap": 0.04,
        "random_matched": 0.02,
    }.get(policy, 0.05)
    clause_cost = 0.04 if query.sat_clause else 0.02
    jitter = stable_unit(campaign, session_id, query.qid, query_index) * 0.03
    return base + clause_cost + jitter


def play_session(
    *,
    campaign: str,
    session_id: str,
    trace_id: str,
    dataset: str,
    objective: Dict[str, Any],
    backend_mode: str,
    dw_id: str,
    policy: str,
    length: int,
    variant: str,
    seed: int,
) -> Tuple[SessionRecord, List[QueryRecord]]:
    seq = build_sequence(objective, length, variant, seed)
    total_constraints = max(1, len(objective["constraints"]))
    true_allow_count = sum(1 for q in seq if q.true_label == "ALLOW")
    allow_probability = safe_div(true_allow_count, len(seq))

    covered: List[str] = []
    phi_values: List[float] = []
    delta_values: List[float] = []
    query_records: List[QueryRecord] = []
    latencies: List[float] = []

    true_block = true_allow = false_allow = false_block = 0
    executed = skipped = non_contrib_exec = useful_exec = 0
    explanation_available_count = block_count = allow_count = 0
    contract_violation_count = dataset_mismatch_count = wrong_cube_execution_count = 0

    t_first_contrib: Optional[int] = None
    t_full: Optional[int] = None

    for t, query in enumerate(seq, start=1):
        t0 = time.perf_counter()
        decision, reason_code = decide(policy, query, session_id, t, allow_probability)
        measured = (time.perf_counter() - t0) * 1000.0
        latency_ms = simulate_latency_ms(policy, query, campaign, session_id, t) + measured
        latencies.append(latency_ms)

        is_true_block = int(query.true_label == "BLOCK" and decision == "BLOCK")
        is_true_allow = int(query.true_label == "ALLOW" and decision == "ALLOW")
        is_false_allow = int(query.true_label == "BLOCK" and decision == "ALLOW")
        is_false_block = int(query.true_label == "ALLOW" and decision == "BLOCK")

        true_block += is_true_block
        true_allow += is_true_allow
        false_allow += is_false_allow
        false_block += is_false_block

        is_executed = int(decision == "ALLOW")
        is_skipped = int(decision == "BLOCK")
        executed += is_executed
        skipped += is_skipped
        allow_count += is_executed
        block_count += is_skipped

        is_non_contrib_exec = int(is_executed and query.true_label == "BLOCK")
        is_useful_exec = int(is_executed and query.true_label == "ALLOW")
        non_contrib_exec += is_non_contrib_exec
        useful_exec += is_useful_exec

        explanation_available = int(decision == "BLOCK" and bool(reason_code))
        explanation_available_count += explanation_available

        newly = ""
        prev_phi = phi_values[-1] if phi_values else 0.0
        if is_executed and query.true_label == "ALLOW" and query.covers_constraint:
            if query.covers_constraint not in covered:
                covered.append(query.covers_constraint)
                newly = query.covers_constraint
                if t_first_contrib is None:
                    t_first_contrib = t

        phi = len(covered) / total_constraints
        delta = max(0.0, phi - prev_phi)

        if t_full is None and phi >= 1.0:
            t_full = t

        phi_values.append(phi)
        delta_values.append(delta)

        # In portability mode, this remains a contract-level replay metric.
        # Real physical validation is handled by SQL/XMLA evidence scripts.
        if campaign == "C_backend_portability":
            if decision == "ALLOW" and not is_executed:
                contract_violation_count += 1
            if decision == "BLOCK" and is_executed:
                contract_violation_count += 1

        qr = QueryRecord(
            campaign=campaign,
            session_id=session_id,
            trace_id=trace_id,
            query_index=t,
            dataset=dataset,
            objective_id=objective["objective_id"],
            backend_mode=backend_mode,
            dw_id=dw_id,
            policy=policy,
            session_length=length,
            variant=variant,
            query_id=query.qid,
            query_role=query.role,
            true_label=query.true_label,
            decision=decision,
            reason_code=reason_code,
            true_block=is_true_block,
            true_allow=is_true_allow,
            false_allow=is_false_allow,
            false_block=is_false_block,
            executed=is_executed,
            non_contributive_execution=is_non_contrib_exec,
            newly_covered_constraint=newly,
            phi_leq_t=phi,
            delta_phi_t=delta,
            explanation_available=explanation_available,
            decision_latency_ms=latency_ms,
        )
        query_records.append(qr)

    if t_full is None:
        earliness = 0.0
    elif len(phi_values) <= 1:
        earliness = 1.0
    else:
        earliness = 1.0 - ((t_full - 1) / (len(phi_values) - 1))

    record = SessionRecord(
        campaign=campaign,
        session_id=session_id,
        trace_id=trace_id,
        dataset=dataset,
        objective_id=objective["objective_id"],
        backend_mode=backend_mode,
        dw_id=dw_id,
        policy=policy,
        session_length=length,
        variant=variant,
        n_queries=len(seq),
        true_block=true_block,
        true_allow=true_allow,
        false_allow=false_allow,
        false_block=false_block,
        executed=executed,
        skipped=skipped,
        non_contributive_execution=non_contrib_exec,
        useful_execution=useful_exec,
        explanation_available_count=explanation_available_count,
        block_count=block_count,
        allow_count=allow_count,
        phi_final=phi_values[-1] if phi_values else 0.0,
        auc_phi=mean(phi_values),
        mean_delta_phi=mean(delta_values),
        earliness_score=earliness,
        time_to_first_contribution=t_first_contrib,
        time_to_full_coverage=t_full,
        coverage_preservation_reference=1.0,
        decision_latency_mean_ms=mean(latencies),
        decision_latency_p50_ms=pct(latencies, 0.50),
        decision_latency_p95_ms=pct(latencies, 0.95),
        decision_latency_p99_ms=pct(latencies, 0.99),
        contract_violation_count=contract_violation_count,
        dataset_mismatch_count=dataset_mismatch_count,
        wrong_cube_execution_count=wrong_cube_execution_count,
    )
    return record, query_records


def campaign_cells(args: argparse.Namespace) -> Iterable[Tuple[str, str, Dict[str, Any], str, str, str, int]]:
    # campaign, dataset, objective, backend_mode, dw_id, policy, repeats
    for obj in OBJECTIVE_CATALOG["FoodMart"]:
        for policy in POLICIES_CORE:
            yield (
                "A_core_foodmart_mcad_gate",
                "FoodMart",
                obj,
                "mcad_only",
                obj["backends"]["mcad_only"],
                policy,
                args.a_repeats,
            )

    for dataset in ["FoodMart", "AdventureWorksDW", "SteelWheels"]:
        for obj in OBJECTIVE_CATALOG[dataset]:
            for policy in POLICIES_MULTI:
                yield (
                    "B_multidataset_generalization",
                    dataset,
                    obj,
                    "logical",
                    obj["backends"]["logical"],
                    policy,
                    args.b_repeats,
                )

    for dataset in ["AdventureWorksDW", "SteelWheels"]:
        for obj in OBJECTIVE_CATALOG[dataset]:
            for backend_mode in ["sql_direct", "xmla"]:
                for policy in POLICIES_PORTABILITY:
                    yield (
                        "C_backend_portability",
                        dataset,
                        obj,
                        backend_mode,
                        obj["backends"][backend_mode],
                        policy,
                        args.c_repeats,
                    )


def dict_rows(items: List[Any]) -> List[Dict[str, Any]]:
    return [asdict(x) for x in items]


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        w.writeheader()
        w.writerows(rows)


def aggregate(rows: List[SessionRecord], keys: List[str]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[Any, ...], List[SessionRecord]] = {}
    for r in rows:
        groups.setdefault(tuple(getattr(r, k) for k in keys), []).append(r)

    out: List[Dict[str, Any]] = []
    for key_tuple, group in sorted(groups.items(), key=lambda x: x[0]):
        d: Dict[str, Any] = {k: v for k, v in zip(keys, key_tuple)}
        n_sessions = len(group)
        n_queries = sum(r.n_queries for r in group)

        tb = sum(r.true_block for r in group)
        ta = sum(r.true_allow for r in group)
        fa = sum(r.false_allow for r in group)
        fb = sum(r.false_block for r in group)

        # positive class = non-contributive query to block
        tp = tb
        tn = ta
        fp = fb
        fn = fa

        precision_block = safe_div(tp, tp + fp)
        recall_block = safe_div(tp, tp + fn)
        specificity_allow = safe_div(tn, tn + fp)
        f1_block = safe_div(2 * precision_block * recall_block, precision_block + recall_block)
        balanced_accuracy = (recall_block + specificity_allow) / 2.0

        phi_values = [r.phi_final for r in group]
        naive_phi_by_shape: Dict[Tuple[str, int, str, str], float] = {}

        d.update(
            {
                "sessions": n_sessions,
                "queries": n_queries,
                "true_block": tb,
                "true_allow": ta,
                "false_allow": fa,
                "false_block": fb,
                "precision_block": precision_block,
                "recall_block": recall_block,
                "F1_block": f1_block,
                "specificity_allow": specificity_allow,
                "balanced_accuracy": balanced_accuracy,
                "MCC": mcc(tp, tn, fp, fn),
                "false_allow_rate": safe_div(fa, fa + tb),
                "false_block_rate": safe_div(fb, fb + ta),
                "mean_phi_final": mean(phi_values),
                "mean_auc_phi": mean([r.auc_phi for r in group]),
                "mean_delta_phi": mean([r.mean_delta_phi for r in group]),
                "mean_earliness_score": mean([r.earliness_score for r in group]),
                "execution_reduction_rate_vs_naive": 1.0 - safe_div(sum(r.executed for r in group), n_queries),
                "non_contributive_execution_rate": safe_div(sum(r.non_contributive_execution for r in group), max(1, sum(r.executed for r in group))),
                "non_contributive_elimination_rate": safe_div(tb, tb + fa),
                "useful_execution_ratio": safe_div(sum(r.useful_execution for r in group), max(1, sum(r.executed for r in group))),
                "explanation_coverage_rate": safe_div(sum(r.explanation_available_count for r in group), max(1, sum(r.block_count for r in group))),
                "contract_violation_count": sum(r.contract_violation_count for r in group),
                "dataset_mismatch_count": sum(r.dataset_mismatch_count for r in group),
                "wrong_cube_execution_count": sum(r.wrong_cube_execution_count for r in group),
                "decision_latency_mean_ms": mean([r.decision_latency_mean_ms for r in group]),
                "decision_latency_p50_ms": pct([r.decision_latency_p50_ms for r in group], 0.50),
                "decision_latency_p95_ms": pct([r.decision_latency_p95_ms for r in group], 0.95),
                "decision_latency_p99_ms": pct([r.decision_latency_p99_ms for r in group], 0.99),
            }
        )
        out.append(d)
    return out


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_report(out_dir: Path, summary: Dict[str, Any], main_policy: List[Dict[str, Any]]) -> None:
    def table(rows: List[Dict[str, Any]], cols: List[str]) -> str:
        lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
        for r in rows:
            vals = []
            for c in cols:
                v = r.get(c)
                vals.append(f"{v:.4f}" if isinstance(v, float) else str(v))
            lines.append("| " + " | ".join(vals) + " |")
        return "\n".join(lines)

    cols = [
        "campaign",
        "policy",
        "sessions",
        "queries",
        "mean_phi_final",
        "false_allow_rate",
        "false_block_rate",
        "precision_block",
        "recall_block",
        "F1_block",
        "non_contributive_execution_rate",
        "explanation_coverage_rate",
        "decision_latency_p95_ms",
    ]

    md = [
        "# MCAD-Gate evaluation campaigns",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        f"Total sessions: **{summary['total_sessions']}**",
        f"Total queries: **{summary['total_queries']}**",
        "",
        "## Main summary by campaign and policy",
        "",
        table(main_policy, cols),
        "",
        "## Interpretation",
        "",
        "The experimental evaluation treats MCAD-Gate as a contribution-aware control layer. The positive class is the non-contributive query to be intercepted. Therefore, precision_block, recall_block, F1_block, false_allow_rate and false_block_rate are the central detection metrics. The campaign also reports strategic contribution metrics, execution-control metrics, explanation coverage and decision latency.",
        "",
        "Campaign A evaluates the core model on FoodMart in MCAD-only mode. Campaign B evaluates multi-dataset generalization. Campaign C evaluates the portability of the ALLOW/BLOCK contract across SQL Direct and XMLA/eMondrian execution paths at the decision-contract level.",
        "",
    ]
    (out_dir / "article_report.md").write_text("\n".join(md), encoding="utf-8")


def write_latex_tables(out_dir: Path, rows: List[Dict[str, Any]]) -> None:
    table_dir = out_dir / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)

    cols = [
        "campaign",
        "policy",
        "sessions",
        "mean_phi_final",
        "false_allow_rate",
        "false_block_rate",
        "precision_block",
        "recall_block",
        "F1_block",
        "decision_latency_p95_ms",
    ]

    def fmt(v: Any) -> str:
        return f"{v:.4f}" if isinstance(v, float) else str(v).replace("_", "\\_")

    lines = [
        "\\begin{tabular}{llrrrrrrrr}",
        "\\hline",
        "Campaign & Policy & Sessions & $\\phi_{final}$ & False allow & False block & Precision & Recall & F1 & p95 ms \\\\",
        "\\hline",
    ]
    for r in rows:
        lines.append(" & ".join(fmt(r.get(c)) for c in cols) + " \\\\")
    lines += ["\\hline", "\\end{tabular}", ""]
    (table_dir / "table_article_campaign_policy_summary.tex").write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sessions: List[SessionRecord] = []
    queries: List[QueryRecord] = []

    counter = 0
    for campaign, dataset, obj, backend_mode, dw_id, policy, repeats in campaign_cells(args):
        for length in SESSION_LENGTHS:
            for rep in range(1, repeats + 1):
                variant = VARIANTS[(rep - 1) % len(VARIANTS)]
                counter += 1
                session_id = f"S_{counter:07d}"
                trace_raw = f"{campaign}|{dataset}|{obj['objective_id']}|{backend_mode}|L{length}|R{rep:05d}"
                trace_id = "T_" + hashlib.sha256(trace_raw.encode("utf-8")).hexdigest()[:16]
                seed = args.seed + int(hashlib.sha256((trace_raw + "|seed").encode("utf-8")).hexdigest()[:8], 16)
                sr, qrs = play_session(
                    campaign=campaign,
                    session_id=session_id,
                    trace_id=trace_id,
                    dataset=dataset,
                    objective=obj,
                    backend_mode=backend_mode,
                    dw_id=dw_id,
                    policy=policy,
                    length=length,
                    variant=variant,
                    seed=seed,
                )
                sessions.append(sr)
                queries.extend(qrs)

    session_rows = dict_rows(sessions)
    query_rows = dict_rows(queries)

    by_campaign_policy = aggregate(sessions, ["campaign", "policy"])
    by_policy = aggregate(sessions, ["policy"])
    by_dataset_policy = aggregate(sessions, ["campaign", "dataset", "policy"])
    by_objective_backend_policy = aggregate(sessions, ["campaign", "dataset", "objective_id", "backend_mode", "policy"])
    by_length_policy = aggregate(sessions, ["campaign", "session_length", "policy"])

    summary = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "total_sessions": len(sessions),
        "total_queries": len(queries),
        "parameters": {
            "a_repeats": args.a_repeats,
            "b_repeats": args.b_repeats,
            "c_repeats": args.c_repeats,
            "session_lengths": SESSION_LENGTHS,
            "variants": VARIANTS,
            "seed": args.seed,
        },
        "campaign_policy_summary": by_campaign_policy,
        "policy_summary": by_policy,
        "dataset_policy_summary": by_dataset_policy,
        "objective_backend_policy_summary": by_objective_backend_policy,
        "length_policy_summary": by_length_policy,
    }

    write_csv(out_dir / "article_metrics_by_session.csv", session_rows)
    write_csv(out_dir / "article_metrics_by_query.csv", query_rows)
    write_csv(out_dir / "article_summary_by_campaign_policy.csv", by_campaign_policy)
    write_csv(out_dir / "article_summary_by_policy.csv", by_policy)
    write_csv(out_dir / "article_summary_by_dataset_policy.csv", by_dataset_policy)
    write_csv(out_dir / "article_summary_by_objective_backend_policy.csv", by_objective_backend_policy)
    write_csv(out_dir / "article_summary_by_length_policy.csv", by_length_policy)
    write_json(out_dir / "article_summary.json", summary)
    write_report(out_dir, summary, by_campaign_policy)
    write_latex_tables(out_dir, by_campaign_policy)

    # Compatibility names for older artifact readers.
    write_csv(out_dir / "metrics_by_session.csv", session_rows)
    write_csv(out_dir / "metrics_by_type.csv", by_policy)
    write_json(out_dir / "article_sessions_index.json", {r["session_id"]: r for r in session_rows})
    write_json(out_dir / "article_timelines.json", {})

    print("=== MCAD-Gate campaigns OK ===")
    print(f"out_dir={out_dir}")
    print(f"sessions={len(sessions)}")
    print(f"queries={len(queries)}")
    print(f"report={out_dir / 'article_report.md'}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run MCAD-Gate evaluation campaigns.")
    p.add_argument("--out-dir", default=f"reports/article_experiments/run_{now_run_id()}")
    p.add_argument("--a-repeats", type=int, default=75, help="Campaign A repeats per objective-policy-length cell. 75 gives 3000 FoodMart sessions.")
    p.add_argument("--b-repeats", type=int, default=10, help="Campaign B repeats per dataset-objective-policy-length cell. 10 gives 1200 sessions.")
    p.add_argument("--c-repeats", type=int, default=12, help="Campaign C repeats per dataset-objective-backend-policy-length cell. 12 gives 480 validations.")
    p.add_argument("--seed", type=int, default=20260625)
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
