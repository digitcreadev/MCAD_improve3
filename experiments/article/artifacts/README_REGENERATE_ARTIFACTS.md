# Regenerating all article artifacts

This folder provides the current-repo equivalent of the old `backend/harness/paper_artifacts.py` and `scripts/reproduce_article_artifacts.sh` layer.

## One-command regeneration

```bash
cd /workspaces/MCAD_improve3
bash experiments/article/artifacts/rebuild_and_generate_all.sh
```

By default, this will:

1. run `experiments/article/run_article_rebuild.py` to generate a fresh current article benchmark run;
2. read locked Campaign A, B and C evidence;
3. generate all article figures expected by the current LaTeX file under `figures/`;
4. generate LaTeX tables under the selected artifact output directory;
5. write a manifest, data snapshot, artifact index and SHA-256 checksums.

## Fast mode from an existing run

If you already have an `article_summary.json` run directory:

```bash
python experiments/article/artifacts/generate_article_artifacts.py \
  --run-dir reports/article_experiments/<existing_run_id> \
  --out-dir reports/article_experiments/<existing_run_id>/paper_artifacts \
  --figures-dir figures
```

## Output layout

```text
reports/article_experiments/<run_id>/paper_artifacts/
  article_artifact_data.json
  artifact_manifest.json
  artifact_index.txt
  SHA256SUMS.txt
  tables/*.tex
figures/*.png
```

## Design note

The current repository no longer has the old `backend/harness/` artifact stack. These scripts therefore rebuild the article figures and tables from the current evidence layer:

- `experiments/article/run_article_rebuild.py` for current benchmark-style policy traces;
- Campaign A FoodMart 1000 summary and CKG snapshot;
- locked Campaign B manifest and CKG events;
- locked Campaign C manifest and isolated SQL/XMLA CKG events.
