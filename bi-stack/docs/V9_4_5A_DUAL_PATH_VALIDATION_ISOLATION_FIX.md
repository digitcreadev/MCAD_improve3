# V9.4.5a — Dual-Path Validation Isolation Fix

## Purpose

V9.4.5 introduced a live validation pack for the MCAD BI demonstrator. The first live run showed that the validation could start while Docker had launched `mcad-proxy` but `mcad-api` was not yet accepting connections. As a result, `/mcad/session/new` returned an internal server error and the validation failed before Q1 could run.

V9.4.5a makes the validation pack robust and repeatable.

## Changes

### 1. Readiness and retry isolation in the runner

`run_dual_path_demo_validation.py` now retries transient startup failures for:

- `/health`
- `/mcad/datawarehouses`
- `/bi/scenarios`
- `/mcad/session/new`
- `/bi/execute`

The retry logic treats the following as transient:

- HTTP `500`, `502`, `503`, `504`
- HTTP status `0` from local connection exceptions
- structured `MCAD_API_UNAVAILABLE`
- `Connection refused`

It does not retry deterministic guard responses such as `DW_DISABLED` for `adventureworks_xmla`.

Environment variables:

```bash
MCAD_DEMO_RETRY_ATTEMPTS=24
MCAD_DEMO_RETRY_SLEEP_S=1.0
```

### 2. Structured proxy errors

`bi-stack/mcad-proxy/app.py` now converts temporary `mcad-api` connection failures inside `_relay_get()` and `_relay_post()` into structured HTTP 503 JSON errors instead of unhandled 500 stack traces.

Example:

```json
{
  "detail": {
    "code": "MCAD_API_UNAVAILABLE",
    "message": "MCAD API is not reachable yet. Retry after the mcad-api service is ready."
  }
}
```

### 3. Validation output remains identical

The same evidence files are still generated:

```text
bi-stack/demo-evidence/runs/<timestamp>/
  dual_path_summary.json
  dual_path_summary.md
  dual_path_steps.csv
  xmla_q1_response_digest.txt
  direct_q1_response_digest.txt
  raw/*.json
```

## Validation

```bash
bash bi-stack/scripts/check_dual_path_demo_pack.sh .
docker compose -f bi-stack/docker-compose.yml up -d emondrian pivot4j mcad-api mcad-proxy
bash bi-stack/scripts/run_dual_path_demo_validation.sh .
```

Expected live result:

```json
{
  "overall_status": "PASS",
  "passed_steps": 4,
  "total_steps": 4
}
```

## Scope

This patch does not change the MCAD scientific engine, objective semantics, SAT, Real, Ceval, φ, or the article reproducibility campaign. It only hardens the live BI demonstration validation path.
