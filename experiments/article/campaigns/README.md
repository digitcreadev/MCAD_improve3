# MCAD campaign hub — cross-version consolidation

This directory is a non-destructive campaign hub. It centralizes recovered historical primary outputs and points to already-canonical sources that remain elsewhere in the repository.

Rules:
- no experiment is rerun by installation;
- existing scientific sources are not moved or rewritten;
- recovered May-2026 offline runs are `RECOVERED_HISTORICAL_PRIMARY` until qualification;
- Q1–Q6 / A / B / C recovered packages preserve historical canonical evidence;
- robustness is a frozen primary source;
- simulated `sim_expert_*` files are quarantined and excluded from human-validation claims;
- current sensitivity freezes remain authoritative in their existing repository locations until a later controlled migration.

The next step after installation is source qualification and creation of publication-normalized datasets, not experimental rerun.

## Cross-version lineage contracts

- `_lineage/EXPERIMENTAL_TIMELINE.json`: chronology and scope of all experimental families.
- `_lineage/ARTICLE_ARTIFACT_LINEAGE.json`: genealogy and authority class of historical article artifacts.
- `_lineage/ARTIFACT_AUTHORITY_POLICY.md`: precedence rules between primary evidence and publication artifacts.
- `_lineage/RECOVERED_RUN_QUALIFICATION.json`: qualification of the six recovered May offline rebuild runs.

The six May runs are only the recovered offline evaluation suite; the July/August
A/B/C, Q1-Q6, robustness and sensitivity campaigns are distinct later evidence families.

Historical article artifacts are preserved for genealogy and presentation design,
but final numerical claims must resolve to qualified primary or frozen evidence.
