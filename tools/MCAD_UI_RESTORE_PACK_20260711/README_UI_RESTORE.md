# MCAD UI restoration pack

This pack restores a **clean interactive runtime** without reverting the current source code and without modifying the locked A/B/C evidence.

## Why this is the correct repair

The current and intact repositories contain the same `session_ui.html`, the same execution UI, the same Cytoscape vendor file, and the same shared backend/proxy UI logic. The current proxy differs only by additive report-contract fields (`blocked_before_execution` and `contract_version`). The observed regression is primarily caused by the live runtime data being reused for large article campaigns.

Current live data observed during the audit:

- `decision_details.json`: about 82 MB, 446 session keys, 3301 records;
- `ckg_state.json`: about 33 MB, 2266 history items and 300 session-coverage entries;
- `ckg_events.jsonl`: about 17 MB, 2266 events;
- `imported_objectives.json`: 102 imported objectives;
- source catalog: 118 objective JSON files and 124 scenario JSON files.

The monolithic decision archive is read, parsed and rewritten on every new decision. Keeping campaign evidence in the live UI runtime therefore causes avoidable latency and may trigger UI/API timeouts. The locked campaign evidence under `reports/article_experiments/ckg_runtimes/locked/` must remain separate from the interactive runtime.

## Recommended procedure

From the repository root:

```bash
python /path/to/prepare_clean_ui_runtime.py --repo . --profile adventureworks
```

Review the dry-run output. Then apply:

```bash
python /path/to/prepare_clean_ui_runtime.py \
  --repo . \
  --profile adventureworks \
  --apply
```

The script creates a timestamped backup under:

```text
exports/ui_runtime_backups/ui_runtime_before_reset_<UTC timestamp>/
```

It does **not** modify:

```text
reports/article_experiments/ckg_runtimes/locked/**
reports/article_experiments/**
bi-stack/demo-evidence/**
bi-stack/objectives/**
bi-stack/direct-scenarios/**
source code
```

Then verify:

```bash
python /path/to/verify_ui_restore.py --repo .
```

Restart the stack:

```bash
cd /workspaces/MCAD_improve3

docker compose -f bi-stack/docker-compose.yml down

docker compose -f bi-stack/docker-compose.yml up -d --build

docker compose -f bi-stack/docker-compose.yml ps
```

Open the UI in a **new incognito/private window**, or clear `sessionStorage` for the Codespaces origin. This avoids restoring stale browser-side scenario/result state from a previous container run.

## Fresh AdventureWorks session

In the UI:

1. Select objective `O_AW_BIKES_EUROPE_MONTH_TERRITORY_MARGIN`.
2. Select DW `adventureworks_sql_direct`.
3. Click **Create & Activate**.
4. Open **Scenario Runner**.
5. Select `adventureworks_sales_margin_territory_q1_q6`.
6. Click **Load into session**.
7. Before executing, open **Reports** and click **Reset effective session trace** once.
8. Run Q1 through Q6 in order.
9. Verify the expected sequence: ALLOW, ALLOW, ALLOW, BLOCK, BLOCK, BLOCK.
10. Export the session report, metrics, history CSV, evidence JSON/Markdown, and capture the CKG before/after progression.

## Restore a previous runtime backup

Stop the stack, then copy the chosen backup files back:

```bash
docker compose -f bi-stack/docker-compose.yml down

BACKUP="exports/ui_runtime_backups/ui_runtime_before_reset_<timestamp>"
cp -a "$BACKUP/ckg_state.json" bi-stack/mcad-api-data/ckg_state.json
cp -a "$BACKUP/decision_details.json" bi-stack/mcad-api-data/decision_details.json
cp -a "$BACKUP/imported_objectives.json" bi-stack/mcad-api-data/imported_objectives.json
cp -a "$BACKUP/ckg_events.jsonl" bi-stack/mcad-api-data/ckg_events.jsonl

docker compose -f bi-stack/docker-compose.yml up -d --build
```

## Long-term prevention

For future campaigns, do not reuse the interactive `bi-stack/mcad-api-data` directory as the article-campaign runtime. Use an isolated work runtime and activate it only for the campaign. After locking the evidence, reactivate a clean UI runtime. The existing `manage_ckg_campaign_runtime.py` already isolates `ckg_events.jsonl` and `ckg_state.json`; the same separation should be extended to `decision_details.json` and `imported_objectives.json`.
