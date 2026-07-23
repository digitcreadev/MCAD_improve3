# V9.5.2 — AdventureWorksDW Evidence Validation Pack

## Purpose

This pack validates the real AdventureWorksDW SQL Server Direct execution path.
It complements the FoodMart dual-path pack by proving that MCAD can control a
second physical data warehouse backed by SQL Server Docker.

The pack is scenario-driven. It does not require a fixed Q1-Q6 length; it reads
all queries from the AdventureWorks scenario JSON and validates each query using
its `expected_decision` field.

## Files

- `bi-stack/scripts/run_adventureworks_demo_validation.py`
- `bi-stack/scripts/run_adventureworks_demo_validation.sh`
- `bi-stack/scripts/check_adventureworks_evidence_validation_pack.sh`
- `bi-stack/objectives/objective_adventureworks_sales_margin_territory_month.json`
- `bi-stack/direct-scenarios/adventureworks_sales_margin_territory_q1_q6.json`
- `bi-stack/mcad-proxy/execution/adapters/adventureworks_direct_adapter.py`

## Preconditions

1. V9.5.0 SQL Server Docker integration is installed.
2. `AdventureWorksDW2022` has been restored successfully.
3. V9.5.1 objective/scenario files are present, or the copies in this pack are installed.
4. `mcad-api` and `mcad-proxy` are running.

## Run

```bash
bash bi-stack/scripts/check_adventureworks_evidence_validation_pack.sh .

bash bi-stack/scripts/import_adventureworks_objective_scenario.sh .

bash bi-stack/scripts/run_adventureworks_demo_validation.sh .
```

## Outputs

The runner writes evidence under:

```text
bi-stack/demo-evidence/runs/adventureworks_<timestamp>/
```

with:

```text
adventureworks_summary.json
adventureworks_summary.md
adventureworks_steps.csv
adventureworks_response_digests.txt
raw/*.json
```

It also updates:

```text
bi-stack/demo-evidence/latest_adventureworks_path.txt
```

This intentionally does not overwrite the FoodMart dual-path pointer
`latest_path.txt`.

## Validation contract

For `ALLOW` queries, the runner checks:

- MCAD decision is `ALLOW`.
- `physical_execution=true`.
- execution evidence identifies AdventureWorks SQL Direct.
- row count is positive.
- response digest exists when available.

For `BLOCK` queries, the runner checks:

- MCAD decision is `BLOCK`.
- `physical_execution=false`.

## Scope

This pack validates the demonstrator path. It does not replace the article
reproducibility campaign and does not modify the canonical MCAD engine or the article experiment harness.
