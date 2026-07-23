# V9.4.7 — One-Click Demo Validation Runner + Evidence Bundle Export

This version extends the V9.4.6 Demo Validation viewer with a UI-triggered validation runner and a downloadable evidence bundle.

## Added capabilities

- `POST /mcad/demo-evidence/run` starts the fixed dual-path validation runner from the UI.
- `GET /mcad/demo-evidence/run/status` returns the current run state: `IDLE`, `RUNNING`, `PASS`, `FAIL`, `TIMEOUT`, or `ERROR`.
- `GET /mcad/demo-evidence/latest/bundle.zip` downloads the latest evidence run as a ZIP bundle.
- `GET /mcad/demo-evidence/runs/{run_id}/bundle.zip` downloads a specific run.
- The UI tab **Demo Validation** includes:
  - `Run Dual-Path Validation`
  - `Refresh latest`
  - `Download Evidence Bundle`
  - links to Markdown, CSV and JSON artifacts.

## Security boundary

The proxy does not execute arbitrary commands. It launches only the fixed script:

```text
/app/scripts/run_dual_path_demo_validation.py
```

The Docker Compose file mounts the host scripts directory read-only:

```yaml
- ./scripts:/app/scripts:ro
```

Generated artifacts are written under:

```text
/app/demo-evidence
```

which is mounted from:

```text
bi-stack/demo-evidence
```

## Expected validation result

After clicking **Run Dual-Path Validation**, the UI should poll `/mcad/demo-evidence/run/status` until the state becomes `PASS` or `FAIL`. A successful run should show:

```json
{
  "overall_status": "PASS",
  "passed_steps": 4,
  "total_steps": 4
}
```

The downloadable ZIP bundle contains:

```text
dual_path_summary.md
dual_path_summary.json
dual_path_steps.csv
raw/*.json
*_response_digest.txt
ui_run_stdout.log
ui_run_stderr.log
```

## Verification

Run:

```bash
bash bi-stack/scripts/check_demo_runner_export.sh .
```

Expected:

```text
Summary: fails=0
```
