# MCAD V9.4.3b — Evidence Deduplication, Session Result Sync and DW Guard

## Purpose

V9.4.3b corrects three issues observed after V9.4.3a:

1. The same execution evidence was displayed twice: once in **BI Execution Result** and again in **MCAD Decision**.
2. The tabular BI result disappeared after switching from one session to another and back, even when the session had already executed a query.
3. Disabled/future data warehouses such as `adventureworks_xmla` could still be selected or resumed, creating misleading UI states.

## Changes

### Evidence deduplication

The full execution evidence block is now displayed only in **BI Execution Result**. The **MCAD Decision** panel keeps the MCAD decision, formal SAT metrics and SAT evidence, but no longer duplicates the physical execution evidence grid.

### Session-bound BI result restoration

The UI now stores the last BI result, MCAD decision and execution evidence by `session_id` in memory and in `sessionStorage`. When the user switches sessions, the stale panel is cleared immediately; when the user comes back to a previously executed session, its table/result is restored.

### Disabled DW guard

The Data Warehouse selector now exposes only executable DWs by default:

- `foodmart` — FoodMart via XMLA/eMondrian
- `foodmart_sql_direct` — FoodMart via Direct BI

Future/experimental entries remain registered but hidden from the default selector. Backend session creation and execution also reject disabled DWs with `BLOCK_DISABLED_DW` instead of pretending to execute.

## Validation

Run:

```bash
bash bi-stack/scripts/check_evidence_dedup_session_dw_guard.sh .
```

Expected:

```text
Summary: fails=0 warnings=0
```

## Demonstration scenario

1. Create session A with `FoodMart via XMLA/eMondrian`.
2. Execute Q1 and confirm the evidence appears once in `BI Execution Result`.
3. Create or resume session B.
4. Confirm session A result disappears from the panels.
5. Resume session A.
6. Confirm the Q1 table/result is restored for session A.
7. Confirm `AdventureWorksDW — XMLA/eMondrian` is not offered in the normal DW selector.
