#!/usr/bin/env bash
REPO="${1:-/workspaces/MCAD_improve3}"
python "$REPO/reports/article_experiments/nh_r3_end_to_end_resource_benchmark/implementation/verify_protocol.py" "$REPO" || exit $?
python "$REPO/reports/article_experiments/nh_r3_end_to_end_resource_benchmark/implementation/verify_a2_semantic_refinement.py" "$REPO"
