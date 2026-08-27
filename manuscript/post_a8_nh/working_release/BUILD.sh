#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PATH="$ROOT/.build-bin:$PATH"
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1787096820}"
export FORCE_SOURCE_DATE=1
export TZ=UTC
export LC_ALL=C.UTF-8
rm -rf build/fr build/en
mkdir -p build/fr build/en
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build/fr manuscript/fr/MCAD_FR_V8_7_6.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build/en manuscript/en/MCAD_EN_V8_7_6.tex
cp build/fr/MCAD_FR_V8_7_6.pdf manuscript/fr/MCAD_FR_V8_7_6.pdf
cp build/en/MCAD_EN_V8_7_6.pdf manuscript/en/MCAD_EN_V8_7_6.pdf
printf 'Built reproducibly with SOURCE_DATE_EPOCH=%s:\n  %s\n  %s\n' "$SOURCE_DATE_EPOCH" "$ROOT/manuscript/fr/MCAD_FR_V8_7_6.pdf" "$ROOT/manuscript/en/MCAD_EN_V8_7_6.pdf"
