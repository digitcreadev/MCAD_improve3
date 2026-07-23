from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from backend.ckg.ckg_updater import CKGGraph
from backend.harness.run_baselines_and_ablations import (
    _normalize_qp,
    _probe_mcad,
)


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def find_objective_id(config: dict[str, Any]) -> str:
    candidates = [
        config.get("objective_id"),
        (config.get("benchmark") or {}).get("objective_id"),
        (config.get("meta") or {}).get("objective_id"),
        (config.get("config") or {}).get("objective_id"),
    ]

    for value in candidates:
        if value:
            return str(value)

    raise ValueError("objective_id not found in scenario config")


def find_scenarios(config: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        config.get("scenarios"),
        (config.get("benchmark") or {}).get("scenarios"),
        (config.get("config") or {}).get("scenarios"),
    ]

    for value in candidates:
        if isinstance(value, list):
            return value

    raise ValueError("scenarios list not found in scenario config")


def clause_to_dict(clause: Any) -> dict[str, Any]:
    if isinstance(clause, dict):
        return {
            "name": clause.get("name"),
            "ok": bool(clause.get("ok")),
            "detail": clause.get("detail"),
        }

    return {
        "name": getattr(clause, "name", None),
        "ok": bool(getattr(clause, "ok", False)),
        "detail": getattr(clause, "detail", None),
    }


def clauses_as_mapping(probe: dict[str, Any]) -> dict[str, bool]:
    result: dict[str, bool] = {}

    for clause in probe.get("clauses") or []:
        parsed = clause_to_dict(clause)

        if parsed["name"]:
            result[str(parsed["name"])] = bool(parsed["ok"])

    return result


def build_mutated_qp(
    original_qp: dict[str, Any],
    qspec: dict[str, Any],
) -> dict[str, Any]:
    mutated_qp = copy.deepcopy(original_qp)
    mutated_qp["query_spec"] = copy.deepcopy(qspec)
    return mutated_qp


def generate_mutations(
    qp: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    qspec = copy.deepcopy(qp.get("query_spec") or qp)
    mutations: list[tuple[str, dict[str, Any]]] = []

    def add(name: str, mutated_qspec: dict[str, Any]) -> None:
        mutations.append(
            (
                name,
                build_mutated_qp(qp, mutated_qspec),
            )
        )

    # 1. Reversed time window.
    if qspec.get("window_start") and qspec.get("window_end"):
        mutated = copy.deepcopy(qspec)
        mutated["window_start"], mutated["window_end"] = (
            mutated["window_end"],
            mutated["window_start"],
        )
        add("reversed_time_window", mutated)

    # 2. Remove the cube while keeping all other semantics.
    if qspec.get("cube"):
        mutated = copy.deepcopy(qspec)
        mutated["cube"] = ""
        add("missing_cube", mutated)

    # 3. Remove measures while keeping the remainder.
    if qspec.get("measures"):
        mutated = copy.deepcopy(qspec)
        mutated["measures"] = []
        add("missing_measures", mutated)

    # 4. Remove objective identifier from QP only.
    mutated = copy.deepcopy(qspec)
    mutated["objective_id"] = "__UNKNOWN_OBJECTIVE__"
    add("unknown_objective", mutated)

    # 5. Duplicate slicer aliases with contradictory values.
    slicers = copy.deepcopy(qspec.get("slicers") or {})

    alias_functions = [
        lambda key: f"[{key}]",
        lambda key: key.replace(".", "_"),
        lambda key: key.replace("_", " "),
        lambda key: key.lower(),
        lambda key: key.upper(),
    ]

    for key, value in list(slicers.items()):
        for alias_function in alias_functions:
            alias = alias_function(str(key))

            if alias == key:
                continue

            mutated = copy.deepcopy(qspec)
            mutated_slicers = copy.deepcopy(slicers)
            mutated_slicers[alias] = f"__CONFLICT__{value}"
            mutated["slicers"] = mutated_slicers

            add(
                f"duplicate_slicer_conflict:{key}:{alias}",
                mutated,
            )

    # 6. Common aliases likely to normalize to one logical dimension.
    alias_pairs = [
        ("Region", "[Geography].[Region]"),
        ("Year", "[Time].[Year]"),
        ("Store", "[Store].[Store]"),
        ("Category", "[Product].[Category]"),
        ("Territory", "[Sales Territory].[Territory]"),
        ("Product Category", "[Product].[Category]"),
    ]

    for first, second in alias_pairs:
        mutated = copy.deepcopy(qspec)
        mutated_slicers = copy.deepcopy(
            mutated.get("slicers") or {}
        )
        mutated_slicers[first] = "__VALUE_A__"
        mutated_slicers[second] = "__VALUE_B__"
        mutated["slicers"] = mutated_slicers

        add(
            f"synthetic_alias_conflict:{first}:{second}",
            mutated,
        )

    # 7. Incompatible aggregators.
    existing_aggregators = list(
        qspec.get("aggregators")
        or qspec.get("analytics")
        or []
    )

    for aggregator in [
        "SUM",
        "AVG",
        "MIN",
        "MAX",
        "LAST_NON_EMPTY",
        "DISTINCT_COUNT",
    ]:
        if aggregator in existing_aggregators:
            continue

        mutated = copy.deepcopy(qspec)
        mutated["aggregators"] = [aggregator]
        add(f"aggregator:{aggregator}", mutated)

    # 8. Incompatible units.
    existing_units = list(qspec.get("units") or [])

    for unit in [
        "USD",
        "EUR",
        "DZD",
        "PERCENT",
        "COUNT",
        "__INVALID_UNIT__",
    ]:
        if unit in existing_units:
            continue

        mutated = copy.deepcopy(qspec)
        mutated["units"] = [unit]
        add(f"unit:{unit}", mutated)

    # 9. Coarser or empty grouping.
    if qspec.get("group_by"):
        mutated = copy.deepcopy(qspec)
        mutated["group_by"] = []
        add("empty_group_by", mutated)

    return mutations


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: python find_sat_ablation_witness.py "
            "<scenario-config.yaml>",
            file=sys.stderr,
        )
        return 2

    config_path = Path(sys.argv[1])

    if not config_path.is_file():
        print(
            f"[ERROR] Config not found: {config_path}",
            file=sys.stderr,
        )
        return 1

    config = load_config(config_path)
    objective_id = find_objective_id(config)
    scenarios = find_scenarios(config)

    print(f"[INFO] config={config_path}")
    print(f"[INFO] objective_id={objective_id}")
    print(f"[INFO] scenarios={len(scenarios)}")

    matches: list[dict[str, Any]] = []
    attempted = 0

    for scenario in scenarios:
        scenario_id = str(
            scenario.get("id")
            or scenario.get("scenario_id")
            or "unknown"
        )

        for step_index, step in enumerate(
            scenario.get("steps") or [],
            start=1,
        ):
            # Start only from a query known to be contributive.
            if not bool(step.get("oracle_allow", False)):
                continue

            base_qp = _normalize_qp(step, objective_id)

            for mutation_name, mutated_qp in generate_mutations(
                base_qp
            ):
                attempted += 1

                full_ckg = CKGGraph(
                    output_dir=(
                        "results_policy_tmp_sat_search/full"
                    )
                )

                full_probe = _probe_mcad(
                    full_ckg,
                    objective_id,
                    step_index,
                    mutated_qp,
                    ignore_sat=False,
                )

                no_sat_ckg = CKGGraph(
                    output_dir=(
                        "results_policy_tmp_sat_search/no_sat"
                    )
                )

                no_sat_probe = _probe_mcad(
                    no_sat_ckg,
                    objective_id,
                    step_index,
                    mutated_qp,
                    ignore_sat=True,
                )

                full_allow = bool(
                    full_probe["sat"]
                    and full_probe["ceval_ids"]
                )

                no_sat_allow = bool(
                    no_sat_probe["ceval_ids"]
                )

                is_witness = (
                    full_probe["sat"] is False
                    and full_allow is False
                    and bool(no_sat_probe["real_nv_ids"])
                    and bool(no_sat_probe["ceval_ids"])
                    and no_sat_allow is True
                )

                if not is_witness:
                    continue

                matches.append(
                    {
                        "source_scenario": scenario_id,
                        "source_step_index": step_index,
                        "source_step_name": step.get("name"),
                        "mutation": mutation_name,
                        "full_sat": full_probe["sat"],
                        "full_allow": full_allow,
                        "no_sat_allow": no_sat_allow,
                        "sat_clauses": clauses_as_mapping(
                            full_probe
                        ),
                        "real_nv_ids_without_sat": (
                            no_sat_probe["real_nv_ids"]
                        ),
                        "ceval_ids_without_sat": (
                            no_sat_probe["ceval_ids"]
                        ),
                        "mutated_qp": mutated_qp,
                    }
                )

    output_path = Path(
        "reports/article_experiments/"
        "sat_ablation_discriminative_candidates.json"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            matches,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    print()
    print(f"[RESULT] attempted_mutations={attempted}")
    print(f"[RESULT] discriminative_matches={len(matches)}")
    print(f"[RESULT] report={output_path}")

    for index, match in enumerate(matches[:10], start=1):
        print()
        print("=" * 88)
        print(f"MATCH {index}")
        print("=" * 88)
        print(
            json.dumps(
                match,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

    if not matches:
        print()
        print(
            "[NOTICE] No SAT-only decision witness was found "
            "among the tested mutations."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
