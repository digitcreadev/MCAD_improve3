# MCAD publication artifacts V4 — reproducible generation

This pipeline starts from publication V3 commit
`922815488832ecf20d6f31008da044bd3e1c02b0`.

It performs **publication transformation only**:

- no scientific campaign execution;
- no experiment rerun;
- no statistical rerun;
- no bootstrap rerun;
- no physical backend execution.

## Materialized outputs

`article_update/paper_artifacts_v4/` contains publication-facing data,
vector TikZ/PGFPlots figures, figure-to-source provenance, the P9 citation
audit, reference corrections, bibliography/claim propagation, the enriched
experimental section, the integrated French V4 manuscript, supplementary
figures, a manifest and SHA-256 registry.

## Reproduce

```bash
python3 scripts/paper_artifacts/v4/generate_publication_artifacts_v4.py \
  --repo-root . \
  --output-root article_update/paper_artifacts_v4
```

The visual grammar of earlier manuscript versions is reused where useful,
but historical illustrative values, simulated human validation, Phase-7
May statistics as-is and May timing claims are not reintroduced.

Sensitivity figures show precision diagnostics or final pass/fail cell
structure; they do not convert non-authorized timing into performance claims.


## V4.1 performance restoration

V4.1 restores the performance-evaluation grammar from earlier manuscript
versions: p50 / p95 / p99, explicit tail behavior, and scalability context.

No legacy numerical value is adopted directly. Quantiles are derived from
existing canonical `wall_latency_ms` observations for the three factors whose
existing observations are reused publication-side. This is a deterministic
descriptive transformation, not a new experiment or bootstrap.

`objective_count` Stage-30 remains excluded from absolute-latency
interpretation because its terminal execution manifest explicitly sets
`absolute_timing_magnitudes_interpreted=false`.


## V4.2 patch

V4.2 fixes three publication-only string-escaping defects from V4.1:

1. bibliography insertion now matches the real newline before
   `\end{thebibliography}`;
2. the performance subsection now matches the real newline before
   `\subsection{Portée des conclusions}`;
3. the generated latency table is joined with real newline characters,
   not literal `\n` text.

A regression guard now applies the full bibliography/claim patch to the
committed V3 manuscript before the main generation starts.

No scientific execution, timing execution, bootstrap, statistical rerun, or
backend execution is added by this patch.
