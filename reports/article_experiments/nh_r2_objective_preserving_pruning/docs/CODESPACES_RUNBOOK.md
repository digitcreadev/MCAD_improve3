# Codespaces runbook - MCAD-NH-R2 (V2 safe procedure)

## 0. Important correction

Do not leave the kit ZIP in the repository root during the clean-tree gate. The V2 safe-start script automatically relocates known NH-R2 kit ZIPs from the repo root to `/workspaces/mcad_kits/` before checking cleanliness.

Never paste `exit` or `set -euo pipefail` into the interactive Codespaces shell for this workflow. Run the provided scripts with `bash ...`; failures then return to the terminal instead of terminating it.

Canonical source branch for this campaign: `paper/phase3-controlled-execution`.
NH-R2 must run on a new dedicated branch created from that exact source after local/remote equality is verified.

## A. Unpack outside the repository

If the ZIP was uploaded into the repo root, move it out first. Example:

```bash
REPO=/workspaces/MCAD_improve3
KITSTORE=/workspaces/mcad_kits
mkdir -p "$KITSTORE"
mv "$REPO"/MCAD_NH_R2_CODESPACES_EXECUTION_KIT_V2.zip "$KITSTORE"/ 2>/dev/null || true
```

Then unpack outside the repository:

```bash
rm -rf /tmp/mcad_nh_r2_kit_v2
mkdir -p /tmp/mcad_nh_r2_kit_v2
unzip -q /workspaces/mcad_kits/MCAD_NH_R2_CODESPACES_EXECUTION_KIT_V2.zip -d /tmp/mcad_nh_r2_kit_v2
```

## B. Safe source gate, base verification, branch creation and installation

```bash
bash /tmp/mcad_nh_r2_kit_v2/MCAD_NH_R2_CODESPACES_EXECUTION_KIT_V2/scripts/00_safe_codespace_start.sh \
  /workspaces/MCAD_improve3 \
  paper/phase3-controlled-execution
```

The script:

1. relocates known kit ZIPs out of the Git tree;
2. prints current branch/head/status;
3. refuses to continue on any other dirty file;
4. runs `git fetch origin --prune`;
5. switches to `paper/phase3-controlled-execution`;
6. verifies local head equals `origin/paper/phase3-controlled-execution`;
7. creates `paper/nh-r2-objective-preserving-pruning-<UTC>`;
8. installs only `reports/article_experiments/nh_r2_objective_preserving_pruning/`.

It performs no commit and no push.

## C. Optional read-only branch inventory

```bash
bash /tmp/mcad_nh_r2_kit_v2/MCAD_NH_R2_CODESPACES_EXECUTION_KIT_V2/scripts/01_branch_inventory.sh \
  /workspaces/MCAD_improve3 \
  paper/phase3-controlled-execution
```

Do not delete branches before the inventory is audited.

## D. Run R2 only after the safe-start output is audited

```bash
cd /workspaces/MCAD_improve3
EXP=reports/article_experiments/nh_r2_objective_preserving_pruning
bash "$EXP/scripts/10_run_all.sh" /workspaces/MCAD_improve3
```

Expected semantic gate: `PASS`, objective preservation failures `0`, false prunes of immediate/deferred contributors `0`.

## E. Verify

```bash
bash "$EXP/scripts/30_verify_results.sh"
```

## F. Return evidence before commit

```bash
cd /workspaces/MCAD_improve3
echo "=== POST-RUN STATE ==="
echo "branch=$(git branch --show-current)"
echo "head_before_commit=$(git rev-parse HEAD)"
git status --short --branch
cat "$EXP/results/gate_results.json"
cat "$EXP/results/SEMANTIC_DIGEST_SHA256.txt"
cat "$EXP/results/MCAD_NH_R2_FREEZE_SHA256.txt"
cat "$EXP/results/MCAD_NH_R2_RESULTS_SHA256.txt"
```

Do not commit or push before audit.
