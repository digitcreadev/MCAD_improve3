from __future__ import annotations

import copy
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from backend.harness.sensitivity_execution import (
    analyze_clustered_timing_precision_v2 as target,
)


class FactorLabelMetadataTests(unittest.TestCase):
    @staticmethod
    def _run_analysis(
        *,
        factor: str | None = None,
    ):
        grouped = {
            (2, 1): {
                0: (1.0,),
                1: (2.0,),
            }
        }

        seeds = {
            0: 101,
            1: 202,
        }

        statistics_record = {
            "median_relative_half_width": 0.01,
            "p95_relative_half_width": 0.02,
        }

        kwargs = {
            "expected_cluster_count": 2,
            "expected_levels": [2],
            "expected_steps": [1],
            "measurements_per_cluster": 1,
            "bootstrap_repetitions": 10,
            "bootstrap_seed": 20260728,
            "confidence_level": 0.95,
            "median_target": 0.10,
            "p95_target": 0.15,
        }

        if factor is not None:
            kwargs["factor"] = factor

        with (
            patch.object(
                target,
                "validate_and_group",
                return_value=(grouped, seeds),
            ),
            patch.object(
                target,
                "cluster_bootstrap_cell",
                return_value=statistics_record,
            ),
        ):
            return target.analyze_precision(
                [],
                **kwargs,
            )

    def test_default_preserves_constraint_count_metadata(
        self,
    ) -> None:
        result = self._run_analysis()

        self.assertEqual(
            result["cell_results"][0]["factor"],
            "constraint_count",
        )

    def test_explicit_objective_count_metadata(
        self,
    ) -> None:
        result = self._run_analysis(
            factor="objective_count",
        )

        self.assertEqual(
            result["cell_results"][0]["factor"],
            "objective_count",
        )

    def test_factor_change_is_metadata_only(
        self,
    ) -> None:
        default = self._run_analysis()
        objective = self._run_analysis(
            factor="objective_count",
        )

        default = copy.deepcopy(default)
        objective = copy.deepcopy(objective)

        for cell in default["cell_results"]:
            cell.pop("factor")

        for cell in objective["cell_results"]:
            cell.pop("factor")

        self.assertEqual(default, objective)

    def test_cli_accepts_objective_count_factor(
        self,
    ) -> None:
        output = io.StringIO()

        with (
            redirect_stdout(output),
            self.assertRaises(SystemExit) as raised,
        ):
            target.main(
                [
                    "--factor",
                    "objective_count",
                    "--help",
                ]
            )

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("--factor", output.getvalue())


if __name__ == "__main__":
    unittest.main()
