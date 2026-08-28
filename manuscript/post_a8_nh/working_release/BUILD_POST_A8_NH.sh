#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export PATH="$ROOT/.build-bin:$PATH"
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1787096820}"
export FORCE_SOURCE_DATE=1
export TZ=UTC
export LC_ALL=C.UTF-8

SOURCE="manuscript/fr/MCAD_FR_POST_A8_NH.tex"
OUTDIR="build/post_a8_nh/fr"
PDF_NAME="MCAD_FR_POST_A8_NH.pdf"
FINAL_PDF="manuscript/fr/$PDF_NAME"

printf '=== MCAD post-A8 descendant build harness ===\n'
printf 'source=%s\n' "$SOURCE"
printf 'outdir=%s\n' "$OUTDIR"
printf 'final_pdf=%s\n' "$FINAL_PDF"
printf 'SOURCE_DATE_EPOCH=%s\n' "$SOURCE_DATE_EPOCH"

[ -f "$SOURCE" ] || {
  printf 'ERROR: descendant source missing: %s\n' "$SOURCE" >&2
  exit 10
}

for tool in latexmk pdflatex bibtex; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf 'ERROR: required TeX tool unavailable: %s\n' "$tool" >&2
    printf 'BUILD_REFUSED_TOOLCHAIN_INCOMPLETE=true\n' >&2
    exit 20
  fi
done

rm -rf "$OUTDIR"
mkdir -p "$OUTDIR"

latexmk \
  -pdf \
  -interaction=nonstopmode \
  -halt-on-error \
  -file-line-error \
  -outdir="$OUTDIR" \
  "$SOURCE"

BUILT_PDF="$OUTDIR/$PDF_NAME"
[ -f "$BUILT_PDF" ] || {
  printf 'ERROR: expected PDF not produced: %s\n' "$BUILT_PDF" >&2
  exit 30
}

cp "$BUILT_PDF" "$FINAL_PDF"

printf 'POST_A8_BUILD=PASS\n'
printf 'built_pdf=%s\n' "$BUILT_PDF"
printf 'final_pdf=%s\n' "$FINAL_PDF"
sha256sum "$FINAL_PDF"
