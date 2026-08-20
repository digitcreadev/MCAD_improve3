#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; OUT="$ROOT/results"; cd "$OUT"; sha256sum -c SHA256SUMS.txt; sha256sum -c MCAD_NH_R2_RESULTS_SHA256.txt; unzip -t MCAD_NH_R2_RESULTS.zip >/dev/null; echo "verify=PASS"
