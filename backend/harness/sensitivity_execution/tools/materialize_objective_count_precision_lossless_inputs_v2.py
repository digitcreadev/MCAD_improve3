#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

SOURCE_HEADER = [
    "phase", "phase_round", "order_position", "observation_index",
    "cell_id", "canonical_instance_id", "factor_level",
    "replication_index", "seed", "step_position", "step_index",
    "step_id", "prefix_step_count", "fresh_state", "wall_latency_ns",
    "wall_latency_ms", "cpu_latency_ns", "cpu_latency_ms",
    "semantic_digest", "semantic_match",
]
REDUCED_HEADER = [
    "factor_level", "formal_replication_index", "formal_structural_seed",
    "step_index", "wall_latency_ms",
]
LEVELS = {1, 2, 5, 10, 20, 50}
STEPS = set(range(1, 33))


def truthy(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timing-root", required=True)
    parser.add_argument("--reduced-observations", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--synthetic-shadow")
    args = parser.parse_args()

    timing_root = Path(args.timing_root)
    reduced_path = Path(args.reduced_observations)
    output_path = Path(args.output)
    shadow_path = Path(args.synthetic_shadow) if args.synthetic_shadow else None

    sources = sorted(
        timing_root.glob(
            "objective_count_rep_*_portfolio_timing_stage10/"
            "timing_observations.csv"
        )
    )
    if len(sources) != 10:
        raise SystemExit(f"expected 10 timing CSVs, got {len(sources)}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if shadow_path is not None:
        shadow_path.parent.mkdir(parents=True, exist_ok=True)

    out_fields = SOURCE_HEADER + [
        "formal_replication_index",
        "formal_structural_seed",
    ]

    source_counter: Counter[tuple[str, str, str, str, str]] = Counter()
    counts: Counter[tuple[int, int, int]] = Counter()
    rep_to_seed: dict[int, set[int]] = defaultdict(set)

    measurement_count = 0
    warmup_count = 0
    fresh_false_count = 0
    semantic_false_count = 0

    with output_path.open("w", encoding="utf-8", newline="") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=out_fields, lineterminator="\n")
        writer.writeheader()

        shadow_f = None
        shadow_writer = None
        try:
            if shadow_path is not None:
                shadow_f = shadow_path.open("w", encoding="utf-8", newline="")
                shadow_writer = csv.DictWriter(
                    shadow_f,
                    fieldnames=out_fields,
                    lineterminator="\n",
                )
                shadow_writer.writeheader()

            for src in sources:
                with src.open("r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    if reader.fieldnames != SOURCE_HEADER:
                        raise SystemExit(
                            f"unexpected timing header in {src}: {reader.fieldnames}"
                        )

                    for row in reader:
                        phase = row["phase"].strip()
                        if phase == "warmup":
                            warmup_count += 1
                            continue
                        if phase != "measurement":
                            raise SystemExit(f"unexpected phase {phase!r} in {src}")

                        measurement_count += 1

                        if not truthy(row["fresh_state"]):
                            fresh_false_count += 1
                        if not truthy(row["semantic_match"]):
                            semantic_false_count += 1

                        level = int(row["factor_level"])
                        rep = int(row["replication_index"])
                        seed = int(row["seed"])
                        step = int(row["step_index"])

                        if level not in LEVELS or step not in STEPS:
                            raise SystemExit("unexpected level/step")
                        if rep not in range(10):
                            raise SystemExit("unexpected replication index")

                        rep_to_seed[rep].add(seed)
                        counts[(rep, level, step)] += 1

                        output_row = dict(row)
                        output_row["formal_replication_index"] = row["replication_index"]
                        output_row["formal_structural_seed"] = row["seed"]
                        writer.writerow(output_row)

                        source_counter[
                            (
                                row["factor_level"],
                                row["replication_index"],
                                row["seed"],
                                row["step_index"],
                                row["wall_latency_ms"],
                            )
                        ] += 1

                        if shadow_writer is not None:
                            shadow = dict(output_row)
                            shadow["wall_latency_ns"] = "1000000"
                            shadow["wall_latency_ms"] = "1.0"
                            shadow["cpu_latency_ns"] = "1000000"
                            shadow["cpu_latency_ms"] = "1.0"
                            shadow_writer.writerow(shadow)
        finally:
            if shadow_f is not None:
                shadow_f.close()

    if measurement_count != 192000:
        raise SystemExit(f"measurement count mismatch: {measurement_count}")
    if warmup_count != 19200:
        raise SystemExit(f"warmup count mismatch: {warmup_count}")
    if fresh_false_count != 0:
        raise SystemExit(f"non-fresh measurement rows: {fresh_false_count}")
    if semantic_false_count != 0:
        raise SystemExit(f"semantic mismatch measurement rows: {semantic_false_count}")
    if set(rep_to_seed) != set(range(10)):
        raise SystemExit("replication set mismatch")
    if any(len(v) != 1 for v in rep_to_seed.values()):
        raise SystemExit("replication-to-seed mapping mismatch")
    if len({next(iter(v)) for v in rep_to_seed.values()}) != 10:
        raise SystemExit("structural seeds are not unique")
    if len(counts) != 10 * 6 * 32:
        raise SystemExit(f"cluster/cell count mismatch: {len(counts)}")
    if any(v != 100 for v in counts.values()):
        raise SystemExit("measurements-per-cluster/cell mismatch")

    reduced_counter: Counter[tuple[str, str, str, str, str]] = Counter()
    reduced_rows = 0
    with reduced_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != REDUCED_HEADER:
            raise SystemExit(
                f"unexpected reduced observations header: {reader.fieldnames}"
            )
        for row in reader:
            reduced_rows += 1
            reduced_counter[
                (
                    row["factor_level"],
                    row["formal_replication_index"],
                    row["formal_structural_seed"],
                    row["step_index"],
                    row["wall_latency_ms"],
                )
            ] += 1

    if reduced_rows != 192000:
        raise SystemExit(f"reduced row count mismatch: {reduced_rows}")
    if reduced_counter != source_counter:
        raise SystemExit(
            "lossless adapter projection does not match frozen reduced observations"
        )

    print("lossless_materialization=PASS")
    print("timing_source_file_count=10")
    print("warmup_rows_excluded=19200")
    print("measurement_rows_selected=192000")
    print("fresh_state_all_true=true")
    print("semantic_match_all_true=true")
    print("projection_identity_with_frozen_reduced_observations=true")
    print("scientific_latency_values_modified=false")
    print("timing_magnitudes_interpreted=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
