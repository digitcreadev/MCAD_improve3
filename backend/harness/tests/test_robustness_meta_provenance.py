from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.harness import (
    run_robustness_benchmark as robustness,
)


def test_robustness_meta_records_cli_seed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    results_dir = tmp_path / "results"
    runtime_dir = tmp_path / "runtime"

    monkeypatch.setenv(
        "MCAD_TMP_DIR",
        str(runtime_dir),
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_robustness_benchmark.py",
            "--config",
            (
                "backend/harness/"
                "scenarios_robustness_foodmart.yaml"
            ),
            "--results-dir",
            str(results_dir),
            "--repeats",
            "1",
            "--seed",
            "314159",
        ],
    )

    robustness.main()

    meta_path = (
        results_dir
        / "robustness_meta.json"
    )

    assert meta_path.is_file()

    metadata = json.loads(
        meta_path.read_text(
            encoding="utf-8"
        )
    )

    assert isinstance(metadata, list)
    assert len(metadata) == 1

    entry = metadata[0]

    assert entry["repeats"] == 1
    assert entry["seed"] == 314159
    assert entry["dw_id"] == "FOODMART"
    assert entry["n_scenarios"] == 4
    assert entry["config_path"].endswith(
        "scenarios_robustness_foodmart.yaml"
    )
