# V9.4.3a — Evidence Propagation to Reports + Session-Bound UI Sync

## Purpose

This patch completes the V9.4.3 execution-evidence layer by propagating evidence beyond the immediate `/bi/execute` response and by fixing the UI regression where the execution-result area remained stale when switching sessions.

## Scope

V9.4.3a affects only the BI demonstration layer under `bi-stack`:

- `bi-stack/mcad-proxy/app.py`
- `bi-stack/mcad-proxy/session_ui.html`
- `bi-stack/scripts/check_evidence_reports_session_sync.sh`
- this documentation file

It does not modify the MCAD engine, `backend/mcad/engine.py`, the article experiment harness, or generated campaign artifacts.

## Main changes

### 1. Proxy-side execution evidence archive

`mcad-proxy` now archives each `execution_evidence` object per active MCAD session in:

```text
/app/data/execution_evidence_archive.json
```

Each archived evidence item is keyed and matched by:

- `session_id`
- `step_index`
- scenario query id / query id
- query digest

### 2. Evidence propagation to JSON reports

The following endpoints enrich their returned rows with execution evidence fields:

```text
/mcad/history/current
/mcad/decision-details/current
/mcad/decision-details/current/{step_index}
/mcad/reports/current/session
/mcad/metrics/current/session
/mcad/evidence/current
/mcad/evidence/current/archive
```

Typical row-level fields added include:

```text
execution_status
execution_path
adapter_id
selected_dw_id
physical_execution
status_code
elapsed_ms
response_bytes
response_digest
xmla_response_type
row_count
```

### 3. Evidence propagation to Markdown and CSV exports

The proxy now enriches the forwarded backend exports:

```text
/mcad/reports/current/session/markdown
/mcad/reports/current/session/csv
/mcad/metrics/current/session/markdown
/mcad/metrics/current/session/csv
```

Markdown exports receive an `Execution Evidence` table. CSV exports receive explicit evidence columns.

### 4. Scenario, metrics and governance UI reports

The UI now appends execution-evidence tables to:

- Scenario contribution report
- Governance report
- Session JSON export
- History CSV export

The backend-proxied session and metrics reports are enriched by the proxy endpoints.

### 5. Session-bound result synchronization

When the active session changes, the UI now clears stale execution panels immediately and hydrates the latest evidence for the newly active session, if one exists.

This fixes the issue where the BI result/decision area stayed visually attached to the previous session.

Expected behavior:

```text
switch session
→ stale BI result is cleared immediately
→ last evidence for the new active session is loaded, if available
→ otherwise the result and decision panels show empty session-bound placeholders
```

## Validation

Run:

```bash
bash bi-stack/scripts/check_evidence_reports_session_sync.sh .
```

Expected:

```text
Summary: fails=0 warnings=0
```

Then rebuild the proxy:

```bash
docker compose -f bi-stack/docker-compose.yml build --no-cache mcad-proxy
docker compose -f bi-stack/docker-compose.yml up -d mcad-proxy
```

## UI validation procedure

1. Open `/mcad/session/ui`.
2. Create session A and run Q1.
3. Verify that `BI Execution Result` shows the correct execution path and digest.
4. Create/resume session B.
5. Verify that the result/decision panel no longer displays session A's old result.
6. Run Q1 in session B.
7. Generate session, scenario, metrics and governance reports.
8. Verify that execution evidence appears in each generated report/export.
