#!/usr/bin/env bash
REPO="${1:-/workspaces/MCAD_improve3}"
EXP="$REPO/reports/article_experiments/nh_r3_end_to_end_resource_benchmark"
python "$EXP/implementation/verify_protocol.py" "$REPO"
cat "$EXP/results/BINDING_PLAN_SHA256.txt"
cat "$EXP/results/MCAD_NH_R3_A_PROTOCOL_FREEZE_SHA256.txt"
