#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping, Sequence

PRIMARY_METRICS = (
    "full_backend_execution_count",
    "backend_request_count_including_gate_probes",
    "client_wall_ms",
    "sqlserver_cpu_usage_usec_delta",
    "sqlserver_io_rbytes_delta",
    "sqlserver_io_wbytes_delta",
    "response_bytes",
    "time_to_analytical_objective_completion_ms",
)

XMLA_SECONDARY_METRICS = (
    "emondrian_cpu_usage_usec_delta",
    "emondrian_io_rbytes_delta",
    "emondrian_io_wbytes_delta",
)

PRODUCTION_SIGN_FLIP_REPLICATES = 100000
PRODUCTION_BOOTSTRAP_REPLICATES = 20000
PRODUCTION_FAMILYWISE_ALPHA = 0.05

SYNTHETIC_NAMESPACE = (
    "MCAD-NH-R3-E7|SYNTHETIC_ONLY|"
    "45dc105e6e9c1ef800323af2a78987a2b8ddcf11|v1"
)
SYNTHETIC_NAMESPACE_SHA256 = hashlib.sha256(SYNTHETIC_NAMESPACE.encode()).hexdigest()


def seed_from_sha256_prefix(material: str) -> tuple[str, int]:
    h = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return h, int(h[:16], 16)


def mean(xs: Sequence[float]) -> float:
    if not xs:
        raise ValueError("mean requires non-empty values")
    return sum(float(x) for x in xs) / len(xs)


def pct_change_of_means(numerator_mean: float, denominator_mean: float) -> float | None:
    if denominator_mean == 0:
        return None
    return (numerator_mean / denominator_mean - 1.0) * 100.0


def percentile_linear(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("percentile requires non-empty values")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be in [0,1]")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = q * (len(sorted_values) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(sorted_values[lo])
    w = pos - lo
    return float(sorted_values[lo]) * (1.0 - w) + float(sorted_values[hi]) * w


def direction_counts(deltas: Sequence[float]) -> dict[str, int]:
    return {
        "safe_lower_count": sum(float(d) < 0 for d in deltas),
        "equal_count": sum(float(d) == 0 for d in deltas),
        "safe_higher_count": sum(float(d) > 0 for d in deltas),
    }


def sign_flip_test(
    deltas: Sequence[float],
    *,
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    if not deltas:
        raise ValueError("sign_flip_test requires non-empty deltas")
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    values = [float(d) for d in deltas]
    observed = mean(values)
    rng = random.Random(int(seed))
    extreme = 0
    n = len(values)
    for _ in range(replicates):
        total = 0.0
        for d in values:
            total += d if rng.getrandbits(1) else -d
        t_perm = total / n
        if t_perm <= observed:
            extreme += 1
    p = (1.0 + extreme) / (replicates + 1.0)
    return {
        "observed_mean_difference": observed,
        "permutations": replicates,
        "extreme_count_t_perm_le_t_obs": extreme,
        "raw_one_sided_p": p,
    }


def stratified_percentile_bootstrap(
    deltas: Sequence[float],
    strata: Sequence[str],
    *,
    replicates: int,
    seed: int,
    confidence: float = 0.95,
) -> dict[str, Any]:
    if len(deltas) != len(strata) or not deltas:
        raise ValueError("deltas/strata must be non-empty and have equal length")
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0,1)")

    grouped: dict[str, list[float]] = defaultdict(list)
    for d, s in zip(deltas, strata):
        grouped[str(s)].append(float(d))

    rng = random.Random(int(seed))
    keys = sorted(grouped)
    boots: list[float] = []
    for _ in range(replicates):
        total = 0.0
        n = 0
        for key in keys:
            vals = grouped[key]
            m = len(vals)
            for _j in range(m):
                total += vals[rng.randrange(m)]
                n += 1
        boots.append(total / n)

    boots.sort()
    tail = (1.0 - confidence) / 2.0
    return {
        "bootstrap_replicates": replicates,
        "confidence": confidence,
        "ci_lower_mean_difference": percentile_linear(boots, tail),
        "ci_upper_mean_difference": percentile_linear(boots, 1.0 - tail),
    }


def holm_adjust(raw_p: Mapping[str, float]) -> dict[str, dict[str, Any]]:
    if not raw_p:
        raise ValueError("Holm adjustment requires non-empty p-values")
    m = len(raw_p)
    ordered = sorted(
        ((str(metric), float(p)) for metric, p in raw_p.items()),
        key=lambda kv: (kv[1], kv[0]),
    )
    out: dict[str, dict[str, Any]] = {}
    running = 0.0
    for rank, (metric, p) in enumerate(ordered, start=1):
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"invalid p-value for {metric}: {p}")
        candidate = min(1.0, (m - rank + 1) * p)
        running = max(running, candidate)
        out[metric] = {
            "holm_rank": rank,
            "raw_one_sided_p": p,
            "holm_adjusted_one_sided_p": min(1.0, running),
        }
    return out


def analyze_primary_pair(
    safe: Sequence[float],
    permissive: Sequence[float],
    strata: Sequence[str],
    *,
    permutation_replicates: int,
    bootstrap_replicates: int,
    permutation_seed: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    if len(safe) != len(permissive) or len(safe) != len(strata) or not safe:
        raise ValueError("safe/permissive/strata must be non-empty and aligned")
    safe_f = [float(x) for x in safe]
    perm_f = [float(x) for x in permissive]
    deltas = [s - p for s, p in zip(safe_f, perm_f)]

    perm = sign_flip_test(
        deltas,
        replicates=permutation_replicates,
        seed=permutation_seed,
    )
    boot = stratified_percentile_bootstrap(
        deltas,
        strata,
        replicates=bootstrap_replicates,
        seed=bootstrap_seed,
        confidence=0.95,
    )
    return {
        "n_pairs": len(deltas),
        "mean_safe": mean(safe_f),
        "mean_permissive": mean(perm_f),
        "mean_difference_safe_minus_permissive": mean(deltas),
        "median_difference_safe_minus_permissive": statistics.median(deltas),
        "percent_change_of_means_safe_vs_permissive": pct_change_of_means(
            mean(safe_f), mean(perm_f)
        ),
        **direction_counts(deltas),
        **perm,
        **boot,
    }


def analyze_secondary_pair(
    safe: Sequence[float],
    comparator: Sequence[float],
    strata: Sequence[str],
    *,
    bootstrap_replicates: int,
    bootstrap_seed: int,
    comparator_label: str,
) -> dict[str, Any]:
    if len(safe) != len(comparator) or len(safe) != len(strata) or not safe:
        raise ValueError("safe/comparator/strata must be non-empty and aligned")
    safe_f = [float(x) for x in safe]
    comp_f = [float(x) for x in comparator]
    deltas = [s - c for s, c in zip(safe_f, comp_f)]
    boot = stratified_percentile_bootstrap(
        deltas,
        strata,
        replicates=bootstrap_replicates,
        seed=bootstrap_seed,
        confidence=0.95,
    )
    return {
        "n_pairs": len(deltas),
        "comparator": comparator_label,
        "mean_safe": mean(safe_f),
        "mean_comparator": mean(comp_f),
        "mean_difference_safe_minus_comparator": mean(deltas),
        "median_difference_safe_minus_comparator": statistics.median(deltas),
        "percent_change_of_means_safe_vs_comparator": pct_change_of_means(
            mean(safe_f), mean(comp_f)
        ),
        **direction_counts(deltas),
        **boot,
        "confirmatory_p_value_computed": False,
    }


def build_synthetic_20x15(value: float) -> tuple[list[float], list[str]]:
    values: list[float] = []
    strata: list[str] = []
    for stratum in range(20):
        label = f"S{stratum:02d}"
        for _rep in range(15):
            values.append(float(value))
            strata.append(label)
    return values, strata


def synthetic_seed(kind: str, scenario: str) -> tuple[str, int]:
    return seed_from_sha256_prefix(
        f"{SYNTHETIC_NAMESPACE_SHA256}|{kind}|{scenario}"
    )


def run_synthetic_self_test() -> dict[str, Any]:
    permutation_reps = 4096
    bootstrap_reps = 2048

    zero_safe, strata = build_synthetic_20x15(100.0)
    zero_perm, _ = build_synthetic_20x15(100.0)
    neg_safe, _ = build_synthetic_20x15(90.0)
    neg_perm, _ = build_synthetic_20x15(100.0)
    pos_safe, _ = build_synthetic_20x15(105.0)
    pos_perm, _ = build_synthetic_20x15(100.0)

    def case(name: str, safe: list[float], perm: list[float]) -> dict[str, Any]:
        _, pseed = synthetic_seed("permutation", name)
        _, bseed = synthetic_seed("bootstrap", name)
        a = analyze_primary_pair(
            safe,
            perm,
            strata,
            permutation_replicates=permutation_reps,
            bootstrap_replicates=bootstrap_reps,
            permutation_seed=pseed,
            bootstrap_seed=bseed,
        )
        b = analyze_primary_pair(
            safe,
            perm,
            strata,
            permutation_replicates=permutation_reps,
            bootstrap_replicates=bootstrap_reps,
            permutation_seed=pseed,
            bootstrap_seed=bseed,
        )
        if a != b:
            raise RuntimeError(f"synthetic determinism failed for {name}")
        return a

    zero = case("zero", zero_safe, zero_perm)
    negative = case("negative", neg_safe, neg_perm)
    positive = case("positive", pos_safe, pos_perm)

    if zero["mean_difference_safe_minus_permissive"] != 0.0:
        raise RuntimeError("zero-case mean mismatch")
    if zero["raw_one_sided_p"] != 1.0:
        raise RuntimeError("zero-case p-value mismatch")
    if zero["ci_lower_mean_difference"] != 0.0 or zero["ci_upper_mean_difference"] != 0.0:
        raise RuntimeError("zero-case CI mismatch")

    if negative["mean_difference_safe_minus_permissive"] != -10.0:
        raise RuntimeError("negative-case mean mismatch")
    if not negative["raw_one_sided_p"] <= 0.01:
        raise RuntimeError("negative-case p-value not sufficiently small")
    if negative["ci_lower_mean_difference"] != -10.0 or negative["ci_upper_mean_difference"] != -10.0:
        raise RuntimeError("negative-case CI mismatch")

    if positive["mean_difference_safe_minus_permissive"] != 5.0:
        raise RuntimeError("positive-case mean mismatch")
    if positive["raw_one_sided_p"] != 1.0:
        raise RuntimeError("positive-case p-value mismatch")
    if positive["ci_lower_mean_difference"] != 5.0 or positive["ci_upper_mean_difference"] != 5.0:
        raise RuntimeError("positive-case CI mismatch")

    raw = {
        metric: p
        for metric, p in zip(
            PRIMARY_METRICS,
            [0.001, 0.01, 0.02, 0.2, 0.3, 0.4, 0.8, 1.0],
        )
    }
    holm = holm_adjust(raw)
    expected = [0.008, 0.07, 0.12, 1.0, 1.0, 1.0, 1.0, 1.0]
    got = [holm[m]["holm_adjusted_one_sided_p"] for m in PRIMARY_METRICS]
    for a, b in zip(got, expected):
        if abs(a - b) > 1e-12:
            raise RuntimeError(f"Holm vector mismatch: {got}")

    _, sec_seed = synthetic_seed("secondary_bootstrap", "xmla_diagnostic")
    secondary = analyze_secondary_pair(
        neg_safe,
        neg_perm,
        strata,
        bootstrap_replicates=bootstrap_reps,
        bootstrap_seed=sec_seed,
        comparator_label="PERMISSIVE_GATED",
    )
    if secondary["confirmatory_p_value_computed"] is not False:
        raise RuntimeError("secondary diagnostic computed confirmatory p-value")

    return {
        "contract_version": "mcad.nh_r3.e7.synthetic_self_test_result.v1",
        "synthetic_only": True,
        "synthetic_namespace_sha256": SYNTHETIC_NAMESPACE_SHA256,
        "permutation_replicates": permutation_reps,
        "bootstrap_replicates": bootstrap_reps,
        "zero_case": {
            "mean_difference": zero["mean_difference_safe_minus_permissive"],
            "raw_p": zero["raw_one_sided_p"],
            "ci95": [
                zero["ci_lower_mean_difference"],
                zero["ci_upper_mean_difference"],
            ],
        },
        "negative_case": {
            "mean_difference": negative["mean_difference_safe_minus_permissive"],
            "raw_p": negative["raw_one_sided_p"],
            "ci95": [
                negative["ci_lower_mean_difference"],
                negative["ci_upper_mean_difference"],
            ],
        },
        "positive_case": {
            "mean_difference": positive["mean_difference_safe_minus_permissive"],
            "raw_p": positive["raw_one_sided_p"],
            "ci95": [
                positive["ci_lower_mean_difference"],
                positive["ci_upper_mean_difference"],
            ],
        },
        "holm_adjusted_vector": got,
        "secondary_confirmatory_p_value_computed": False,
        "measured_data_used": False,
        "backend_query_executed": False,
        "docker_command_executed": False,
        "measurement_performed": False,
        "real_effect_analysis_performed": False,
        "synthetic_effect_analysis_performed": True,
        "status": "PASS",
    }


def prove_measured_data_refusal() -> None:
    raise RuntimeError(
        "R3-E7 exposes synthetic tests only; measured XMLA receipt ingestion and real inference "
        "require a separate post-measurement analysis authorization"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic-self-test", action="store_true")
    ap.add_argument("--prove-measured-data-refusal", action="store_true")
    args = ap.parse_args()

    if args.synthetic_self_test:
        result = run_synthetic_self_test()
        print(json.dumps(result, indent=2, sort_keys=True))
        print("R3_E7_XMLA_INFERENCE_SYNTHETIC_SELF_TEST=PASS")
        return

    if args.prove_measured_data_refusal:
        try:
            prove_measured_data_refusal()
        except RuntimeError as exc:
            expected = (
                "R3-E7 exposes synthetic tests only; measured XMLA receipt ingestion and real inference "
                "require a separate post-measurement analysis authorization"
            )
            if str(exc) != expected:
                raise
            print(f"authorization_refusal_reason={exc}")
            print("measured_receipt_ingested=false")
            print("real_p_value_computed=false")
            print("real_confidence_interval_computed=false")
            print("real_effect_analysis_performed=false")
            print("R3_E7_MEASURED_DATA_REFUSAL_PROBE=PASS")
            return
        raise RuntimeError("measured-data refusal unexpectedly did not refuse")

    raise SystemExit(
        "R3-E7 has no measured-data CLI. Use --synthetic-self-test or "
        "--prove-measured-data-refusal."
    )


if __name__ == "__main__":
    main()
