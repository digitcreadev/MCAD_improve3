# V9.4.5 — Dual-Path Demo Validation Pack

## Purpose

This version adds a reproducible demonstration pack for the MCAD BI demonstrator. It validates that the same MCAD objective can gate two selectable physical execution paths:

1. **FoodMart via XMLA/eMondrian**.
2. **FoodMart via Direct BI**.

It also validates two negative cases:

1. A MCAD **BLOCK** decision does not trigger physical execution.
2. A forced incompatible or disabled DW is rejected without producing a misleading physical result.

This pack is for the live BI demonstrator. It does not replace the article reproducibility campaigns under `/backend`, `/harness`, `/scripts/reproduce_article_artifacts.sh` or `/campaign_runs`.

## Added files

```text
bi-stack/scripts/run_dual_path_demo_validation.sh
bi-stack/scripts/run_dual_path_demo_validation.py
bi-stack/scripts/check_dual_path_demo_pack.sh
bi-stack/demo-evidence/.gitkeep
bi-stack/demo-evidence/.gitignore
bi-stack/docs/V9_4_5_DUAL_PATH_DEMO_VALIDATION_PACK.md
```

## Validation flow

The runner executes the following steps against `mcad-proxy`:

| Step | Expected result |
|---|---|
| FoodMart via XMLA/eMondrian Q1 | `ALLOW`, `physical_execution=true`, XMLA/eMondrian evidence |
| FoodMart via Direct BI Q1 | `ALLOW`, `physical_execution=true`, Direct BI evidence |
| Q3 out of scope | `BLOCK`, `physical_execution=false` |
| Forced AdventureWorks XMLA / incompatible DW | rejected or blocked, `physical_execution=false` |

The pack captures decision and execution evidence: decision, reason, φ, Δφ, SAT, Real, Ceval, adapter, execution path, selected DW, HTTP status, elapsed time, response bytes, digest, row count and XMLA response type.

## Static check

```bash
bash bi-stack/scripts/check_dual_path_demo_pack.sh .
```

Expected:

```text
Summary: fails=0
```

## Live run

Make sure the stack is running:

```bash
docker compose -f bi-stack/docker-compose.yml up -d emondrian pivot4j mcad-api mcad-proxy
```

Then run:

```bash
bash bi-stack/scripts/run_dual_path_demo_validation.sh .
```

The output directory is:

```text
bi-stack/demo-evidence/runs/<timestamp>/
```

It contains:

```text
dual_path_summary.json
dual_path_summary.md
dual_path_steps.csv
xmla_q1_response_digest.txt
direct_q1_response_digest.txt
raw/*.json
```

The file below points to the latest run:

```text
bi-stack/demo-evidence/latest_path.txt
```

## Expected summary

```text
FoodMart via XMLA/eMondrian : PASS
FoodMart via Direct BI       : PASS
MCAD BLOCK no-exec           : PASS
Compatibility/DW guard       : PASS
```

## Interpretation for defense

This version produces a compact proof that MCAD is not merely a UI filter. MCAD evaluates the query first, then allows or blocks the physical BI execution path. When allowed, the selected physical path is explicit and evidenced. When blocked, the evidence must show that physical execution did not happen.
