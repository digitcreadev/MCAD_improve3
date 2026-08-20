#!/usr/bin/env bash
set -euo pipefail
REPO="${1:-/workspaces/MCAD_improve3}"; REL="${2:-reports/article_experiments/nh_r2_objective_preserving_pruning}"; cd "$REPO"; git add "$REL"; git status --short --branch; git commit -m "evidence(nh-r2): objective-preserving safe-pruning campaign"; echo "commit=$(git rev-parse HEAD)"; echo "Nothing was pushed. Push only after you inspect the commit."
