#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


SOURCE_PREFIXES = (
    "experiments/article/",
    "reports/article_experiments/",
    "exports/",
    "bi-stack/",
    "audit_uploads/",
    "reproducibility_checkpoints/",
)

UNRESOLVED_ALIASES = {
    "ui_q1_q6": [
        "ui_q1_q6",
        "q1_q6",
        "q1-q6",
        "adventureworks_steps",
        "adventureworks_summary",
        "session_report_json",
        "session_metrics_json",
        "allow_new_total",
        "block_redundant",
    ],

    "baselines": [
        "baseline",
        "baselines",
        "baseline_evidence",
    ],

    "ablations_sat_real_ceval": [
        "ablation",
        "ablations",
        "sat_only",
        "no_sat",
        "no_real",
        "no_ceval",
        "false_allow",
    ],

    "scalability_ckg": [
        "scalability",
        "scalability_benchmark",
        "scale_benchmark",
        "ckg_size",
        "ckg_scale",
    ],

    "evidence_usefulness": [
        "evidence_usefulness",
        "evidence-usefulness",
        "usefulness_benchmark",
    ],

    "human_validation": [
        "human_validation",
        "expert_validation",
        "annotation",
        "annotations",
        "annotator",
        "adjudication",
    ],
}

REQUIRED = {
    "ui_q1_q6",
    "baselines",
    "ablations_sat_real_ceval",
    "scalability_ckg",
    "evidence_usefulness",
}

OPTIONAL = {
    "human_validation",
}

CONTROL_WORDS = (
    "manifest",
    "freeze",
    "status",
    "provenance",
    "sha256",
    "summary",
    "decision",
    "verdict",
    "reproduce",
    "audit",
)

RESULT_SUFFIXES = {
    ".json",
    ".csv",
    ".jsonl",
    ".tsv",
    ".txt",
    ".md",
}

SCRIPT_SUFFIXES = {
    ".py",
    ".sh",
}


def shell(repo: Path, *cmd: str, check=True) -> str:
    cp = subprocess.run(
        cmd,
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if check and cp.returncode != 0:
        raise RuntimeError(
            f"command failed {cmd}: {cp.stderr}"
        )

    return cp.stdout.strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(block)

    return h.hexdigest()


def tracked_files(repo: Path):
    return shell(
        repo,
        "git",
        "ls-files",
    ).splitlines()


def blob_oid_map(repo: Path):
    result = {}

    raw = shell(
        repo,
        "git",
        "ls-files",
        "-s",
    )

    for line in raw.splitlines():
        left, path = line.split("\t", 1)
        parts = left.split()

        if len(parts) >= 2:
            result[path] = parts[1]

    return result


def git_grep(repo: Path, alias: str):
    cp = subprocess.run(
        [
            "git",
            "grep",
            "-I",
            "-l",
            "-i",
            "-F",
            alias,
            "--",
            *SOURCE_PREFIXES,
        ],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    if cp.returncode not in (0, 1):
        raise RuntimeError(
            f"git grep failed for {alias}"
        )

    if not cp.stdout.strip():
        return []

    return cp.stdout.splitlines()


def bundle_root(rel: str) -> str:
    p = rel.split("/")

    # frozen campaign
    if (
        len(p) >= 4
        and p[:3]
        == [
            "experiments",
            "article",
            "frozen_campaigns",
        ]
    ):
        return "/".join(p[:4])

    # locked runtime bundle
    marker = [
        "ckg_runtimes",
        "locked",
    ]

    for i in range(len(p) - 2):
        if p[i:i + 2] == marker:
            return "/".join(p[:i + 3])

    # exported canonical UI evidence
    if (
        len(p) >= 2
        and p[0] == "exports"
        and p[1].startswith(
            "MCAD_UI_REAL_EVIDENCE_"
        )
    ):
        if (
            "bi-stack" in p
            and "demo-evidence" in p
            and "final-evidence" in p
        ):
            idx = p.index("final-evidence")
            return "/".join(p[:idx + 1])

        if (
            "reports" in p
            and "article_experiments" in p
        ):
            idx = p.index(
                "article_experiments"
            )

            if len(p) > idx + 1:
                return "/".join(
                    p[:idx + 2]
                )

        return "/".join(p[:2])

    # ordinary reports campaign
    if (
        len(p) >= 3
        and p[:2]
        == [
            "reports",
            "article_experiments",
        ]
    ):
        return "/".join(p[:3])

    # baseline evidence
    if (
        "baseline_evidence"
        in p
    ):
        idx = p.index(
            "baseline_evidence"
        )
        return "/".join(p[:idx + 1])

    # demo final evidence
    if (
        len(p) >= 4
        and p[:4]
        == [
            "bi-stack",
            "demo-evidence",
            "final-evidence",
            "raw",
        ]
    ):
        return "bi-stack/demo-evidence/final-evidence"

    if rel.startswith(
        "bi-stack/demo-evidence/final-evidence/"
    ):
        return "bi-stack/demo-evidence/final-evidence"

    # generic experiment bundle
    if (
        len(p) >= 3
        and p[:2]
        == [
            "experiments",
            "article",
        ]
    ):
        return "/".join(p[:3])

    # reproducibility checkpoint
    if (
        len(p) >= 2
        and p[0]
        == "reproducibility_checkpoints"
    ):
        return "/".join(p[:2])

    # audit upload
    if (
        len(p) >= 2
        and p[0] == "audit_uploads"
    ):
        return "/".join(p[:2])

    return str(Path(rel).parent)


def git_tree_oid(
    repo: Path,
    root: str,
):
    cp = subprocess.run(
        [
            "git",
            "rev-parse",
            f"HEAD:{root}",
        ],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    if cp.returncode == 0:
        return cp.stdout.strip()

    return None


def last_commit(
    repo: Path,
    rel: str,
):
    cp = subprocess.run(
        [
            "git",
            "log",
            "-1",
            "--format=%H",
            "--",
            rel,
        ],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    return (
        cp.stdout.strip()
        if cp.returncode == 0
        and cp.stdout.strip()
        else None
    )


def relevant_result_file(rel: str):
    name = Path(rel).name.lower()
    suffix = Path(rel).suffix.lower()

    if suffix not in RESULT_SUFFIXES:
        return False

    if name in {
        "readme.md",
        "readme.txt",
    }:
        return False

    return True


def score_bundle(
    campaign_id,
    root,
    files,
    relevant_paths,
):
    low_root = root.lower()

    score = 0
    reasons = []

    if "/frozen_campaigns/" in low_root:
        score += 1000
        reasons.append(
            "existing_frozen_campaign"
        )

    if "/locked/" in low_root:
        score += 900
        reasons.append(
            "existing_locked_bundle"
        )

    if (
        "mcad_ui_real_evidence_"
        in low_root
    ):
        score += 850
        reasons.append(
            "exported_real_ui_evidence"
        )

    if (
        "final-evidence"
        in low_root
    ):
        score += 500
        reasons.append(
            "final_evidence_bundle"
        )

    if root.startswith(
        "reports/article_experiments/"
    ):
        score += 220

    if root.startswith(
        "experiments/article/"
    ):
        score += 260

    if root.startswith(
        "exports/"
    ):
        score += 260

    if root.startswith(
        "reproducibility_checkpoints/"
    ):
        score += 100

    controls = []
    results = []

    for rel in files:
        name = Path(rel).name.lower()

        if any(
            word in name
            for word in CONTROL_WORDS
        ):
            controls.append(rel)

        if relevant_result_file(rel):
            results.append(rel)

    control_bonus = min(
        400,
        len(controls) * 55,
    )

    result_bonus = min(
        300,
        len(results) * 15,
    )

    relevance_bonus = min(
        300,
        len(relevant_paths) * 25,
    )

    score += (
        control_bonus
        + result_bonus
        + relevance_bonus
    )

    if controls:
        reasons.append(
            f"control_files={len(controls)}"
        )

    if results:
        reasons.append(
            f"result_files={len(results)}"
        )

    if relevant_paths:
        reasons.append(
            f"relevant_matches={len(relevant_paths)}"
        )

    # ----------------------------------------------------------
    # campaign-specific evidence
    # ----------------------------------------------------------

    names = {
        Path(x).name.lower()
        for x in files
    }

    if campaign_id == "ui_q1_q6":
        if (
            "adventureworks_steps.csv"
            in names
        ):
            score += 700
            reasons.append(
                "canonical_steps_csv"
            )

        if (
            "session_report_json.json"
            in names
        ):
            score += 450
            reasons.append(
                "session_report"
            )

        if (
            "session_metrics_json.json"
            in names
        ):
            score += 350
            reasons.append(
                "session_metrics"
            )

        if (
            "adventureworks_summary.md"
            in names
        ):
            score += 250
            reasons.append(
                "adventureworks_summary"
            )

    elif campaign_id == "baselines":
        if "baseline" in low_root:
            score += 250

    elif (
        campaign_id
        == "ablations_sat_real_ceval"
    ):
        if "ablation" in low_root:
            score += 300

    elif (
        campaign_id
        == "scalability_ckg"
    ):
        if (
            "scalab" in low_root
            or "scale" in low_root
        ):
            score += 300

    elif (
        campaign_id
        == "evidence_usefulness"
    ):
        if (
            "evidence_usefulness"
            in low_root
            or "usefulness"
            in low_root
        ):
            score += 350

    elif (
        campaign_id
        == "human_validation"
    ):
        annotation_files = [
            rel
            for rel in files
            if any(
                token
                in Path(rel).name.lower()
                for token in (
                    "annotation",
                    "annotator",
                    "expert",
                    "label",
                    "adjudication",
                )
            )
        ]

        provenance_files = [
            rel
            for rel in files
            if (
                "provenance"
                in Path(rel).name.lower()
                or "manifest"
                in Path(rel).name.lower()
            )
        ]

        if annotation_files:
            score += 300
            reasons.append(
                f"annotation_files={len(annotation_files)}"
            )

        if provenance_files:
            score += 250
            reasons.append(
                f"annotation_provenance_files={len(provenance_files)}"
            )

    eligible = bool(
        results
        and relevant_paths
    )

    return {
        "score": score,
        "reasons": reasons,
        "control_files": sorted(
            controls
        ),
        "result_files": sorted(
            results
        ),
        "eligible": eligible,
    }


def source_file_record(
    repo,
    rel,
    blob_map,
):
    path = repo / rel

    size = (
        path.stat().st_size
        if path.is_file()
        else None
    )

    # SHA256 is useful but do not reread huge datasets here.
    sha = None

    if (
        path.is_file()
        and size is not None
        and size <= 25 * 1024 * 1024
    ):
        sha = sha256_file(path)

    return {
        "path": rel,
        "size_bytes": size,
        "git_blob_oid":
            blob_map.get(rel),
        "sha256": sha,
        "git_last_commit":
            last_commit(
                repo,
                rel,
            ),
    }


def existing_campaign_selection(
    repo,
    campaign,
    tracked,
    blob_map,
):
    controls = [
        x["path"]
        for x in campaign[
            "authoritative_control_files"
        ]
        if x.get("path")
    ]

    roots = sorted(
        {
            bundle_root(rel)
            for rel in controls
        }
    )

    return {
        "campaign_id":
            campaign["campaign_id"],

        "label":
            campaign["label"],

        "evidence_class":
            campaign["evidence_class"],

        "resolution":
            "IMPORTED_CANONICAL_ANCHOR",

        "selection_basis":
            "existing_registry_canonical_anchor",

        "selected_bundles": [
            {
                "root": root,
                "git_tree_oid":
                    git_tree_oid(
                        repo,
                        root,
                    ),
            }
            for root in roots
        ],

        "authoritative_files": [
            source_file_record(
                repo,
                rel,
                blob_map,
            )
            for rel in controls
        ],

        "publication_eligible": True,
    }


def resolve_unresolved(
    repo,
    campaign,
    tracked,
    blob_map,
):
    cid = campaign["campaign_id"]
    aliases = UNRESOLVED_ALIASES[cid]

    candidate_paths = set()

    if cid == "human_validation":
        # Human validation is publication-authorized only from
        # explicitly identifiable human/expert annotation bundles.
        #
        # We intentionally ignore the first-pass registry candidates
        # and generic content grep here because terms such as
        # "annotation" or "audit" may occur in unrelated experiment
        # metadata, notably sensitivity runs.
        human_path_tokens = (
            "human_validation",
            "human-validation",
            "expert_validation",
            "expert-validation",
            "annotator",
            "adjudication",
            "/annotations/",
            "/annotation/",
            "human_annotation",
            "expert_annotation",
        )

        candidate_paths = {
            rel
            for rel in tracked
            if (
                rel.startswith(SOURCE_PREFIXES)
                and any(
                    token in rel.lower()
                    for token in human_path_tokens
                )
            )
        }

    else:
        for group_name in (
            "top_source_candidates",
            "runner_candidates",
            "authoritative_control_files",
        ):
            for x in campaign.get(
                group_name,
                [],
            ):
                rel = x.get("path")

                if rel:
                    candidate_paths.add(rel)

        for alias in aliases:
            candidate_paths.update(
                git_grep(
                    repo,
                    alias,
                )
            )

        candidate_paths = {
            rel
            for rel in candidate_paths
            if rel.startswith(
                SOURCE_PREFIXES
            )
        }

    by_root = defaultdict(set)

    for rel in candidate_paths:
        by_root[
            bundle_root(rel)
        ].add(rel)

    scored = []

    for root, relevant in by_root.items():
        files = [
            rel
            for rel in tracked
            if (
                rel == root
                or rel.startswith(
                    root.rstrip("/")
                    + "/"
                )
            )
        ]

        if not files:
            continue

        evaluation = score_bundle(
            cid,
            root,
            files,
            relevant,
        )

        scored.append(
            {
                "root": root,
                "git_tree_oid":
                    git_tree_oid(
                        repo,
                        root,
                    ),
                **evaluation,
                "relevant_paths":
                    sorted(relevant),
                "bundle_file_count":
                    len(files),
            }
        )

    scored.sort(
        key=lambda x: (
            -x["score"],
            x["root"],
        )
    )

    eligible = [
        x for x in scored
        if x["eligible"]
    ]

    # ----------------------------------------------------------
    # Optional human validation:
    # require BOTH actual annotation artefacts and provenance.
    # ----------------------------------------------------------

    if cid == "human_validation":
        validated = []

        for x in eligible:
            names = [
                Path(rel).name.lower()
                for rel in (
                    x["result_files"]
                    + x["control_files"]
                )
            ]

            has_annotation = any(
                any(
                    token in name
                    for token in (
                        "annotation",
                        "annotator",
                        "expert",
                        "label",
                        "adjudication",
                    )
                )
                for name in names
            )

            has_provenance = any(
                (
                    "provenance" in name
                    or "manifest" in name
                )
                for name in names
            )

            if (
                has_annotation
                and has_provenance
            ):
                validated.append(x)

        if not validated:
            return {
                "campaign_id": cid,
                "label":
                    campaign["label"],
                "evidence_class":
                    campaign["evidence_class"],
                "resolution":
                    "EXCLUDED_NO_CANONICAL_ANNOTATION_PROVENANCE",
                "selection_basis":
                    "human_metrics_not_publication_authorized",
                "selected_bundles": [],
                "authoritative_files": [],
                "publication_eligible":
                    False,
                "candidate_bundles":
                    scored[:10],
            }

        eligible = validated

    if not eligible:
        return {
            "campaign_id": cid,
            "label":
                campaign["label"],
            "evidence_class":
                campaign["evidence_class"],
            "resolution":
                "UNRESOLVED_NO_ELIGIBLE_RESULT_BUNDLE",
            "selection_basis":
                None,
            "selected_bundles": [],
            "authoritative_files": [],
            "publication_eligible":
                False,
            "candidate_bundles":
                scored[:10],
        }

    top = eligible[0]

    second_score = (
        eligible[1]["score"]
        if len(eligible) > 1
        else None
    )

    high_confidence_marker = any(
        marker
        in top["reasons"]
        for marker in (
            "existing_frozen_campaign",
            "existing_locked_bundle",
            "exported_real_ui_evidence",
            "final_evidence_bundle",
        )
    )

    margin = (
        top["score"] - second_score
        if second_score is not None
        else top["score"]
    )

    # Conservative deterministic selection:
    # either a strong existing canonical marker, or a uniquely
    # dominant tracked result bundle.
    confident = (
        high_confidence_marker
        or (
            top["score"] >= 350
            and margin >= 75
        )
        or (
            top["score"] >= 600
            and margin >= 25
        )
    )

    if not confident:
        return {
            "campaign_id": cid,
            "label":
                campaign["label"],
            "evidence_class":
                campaign["evidence_class"],
            "resolution":
                "UNRESOLVED_AMBIGUOUS_TOP_BUNDLES",
            "selection_basis":
                None,
            "selected_bundles": [],
            "authoritative_files": [],
            "publication_eligible":
                False,
            "candidate_bundles":
                scored[:10],
        }

    # Authoritative set:
    # control files + relevant result files from chosen bundle.
    selected_paths = []

    for rel in (
        top["control_files"]
        + top["result_files"]
    ):
        low = rel.lower()

        if (
            rel in top["relevant_paths"]
            or any(
                word
                in Path(rel).name.lower()
                for word in CONTROL_WORDS
            )
            or cid == "ui_q1_q6"
        ):
            selected_paths.append(rel)

    # Keep inventory bounded but deterministic.
    selected_paths = sorted(
        set(selected_paths)
    )[:200]

    if (
        "existing_frozen_campaign"
        in top["reasons"]
    ):
        basis = "existing_frozen_bundle"

    elif (
        "existing_locked_bundle"
        in top["reasons"]
    ):
        basis = "existing_locked_bundle"

    elif (
        "exported_real_ui_evidence"
        in top["reasons"]
    ):
        basis = "existing_real_evidence_export"

    else:
        basis = (
            "tracked_result_bundle_selected_and_publication_frozen"
        )

    return {
        "campaign_id": cid,
        "label":
            campaign["label"],
        "evidence_class":
            campaign["evidence_class"],
        "resolution":
            "PUBLICATION_SOURCE_SELECTED",
        "selection_basis":
            basis,
        "selected_bundles": [
            {
                "root":
                    top["root"],
                "git_tree_oid":
                    top["git_tree_oid"],
                "score":
                    top["score"],
                "selection_reasons":
                    top["reasons"],
                "bundle_file_count":
                    top["bundle_file_count"],
            }
        ],
        "authoritative_files": [
            source_file_record(
                repo,
                rel,
                blob_map,
            )
            for rel
            in selected_paths
        ],
        "publication_eligible":
            True,
        "candidate_bundles":
            scored[:10],
    }


def write_json(path: Path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--repo-root",
        required=True,
    )

    ap.add_argument(
        "--registry",
        required=True,
    )

    ap.add_argument(
        "--selection-json",
        required=True,
    )

    ap.add_argument(
        "--selection-md",
        required=True,
    )

    ap.add_argument(
        "--inventory",
        required=True,
    )

    ap.add_argument(
        "--contract",
        required=True,
    )

    args = ap.parse_args()

    repo = Path(
        args.repo_root
    ).resolve()

    registry_path = (
        repo
        / args.registry
    )

    registry = json.loads(
        registry_path.read_text(
            encoding="utf-8"
        )
    )

    tracked = tracked_files(repo)
    blob_map = blob_oid_map(repo)

    selections = []

    for campaign in registry["campaigns"]:
        cid = campaign["campaign_id"]

        if (
            campaign[
                "source_resolution_status"
            ]
            == "CANONICAL_ANCHOR_IDENTIFIED"
        ):
            selection = existing_campaign_selection(
                repo,
                campaign,
                tracked,
                blob_map,
            )

        elif cid in UNRESOLVED_ALIASES:
            selection = resolve_unresolved(
                repo,
                campaign,
                tracked,
                blob_map,
            )

        else:
            selection = {
                "campaign_id": cid,
                "label":
                    campaign["label"],
                "evidence_class":
                    campaign["evidence_class"],
                "resolution":
                    "UNHANDLED",
                "selection_basis":
                    None,
                "selected_bundles": [],
                "authoritative_files": [],
                "publication_eligible":
                    False,
            }

        selections.append(selection)

    required_unresolved = [
        s["campaign_id"]
        for s in selections
        if (
            s["campaign_id"] in REQUIRED
            and not s["publication_eligible"]
        )
    ]

    optional_excluded = [
        s["campaign_id"]
        for s in selections
        if (
            s["campaign_id"] in OPTIONAL
            and not s["publication_eligible"]
        )
    ]

    generated_at = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    output = {
        "schema_version":
            "mcad-publication-source-selection-v1",

        "generated_at_utc":
            generated_at,

        "git": {
            "commit":
                shell(
                    repo,
                    "git",
                    "rev-parse",
                    "HEAD",
                ),

            "tree":
                shell(
                    repo,
                    "git",
                    "rev-parse",
                    "HEAD^{tree}",
                ),

            "branch":
                shell(
                    repo,
                    "git",
                    "branch",
                    "--show-current",
                ),
        },

        "scientific_execution_performed":
            False,

        "experiment_rerun_performed":
            False,

        "statistical_execution_performed":
            False,

        "required_campaigns":
            sorted(REQUIRED),

        "optional_campaigns":
            sorted(OPTIONAL),

        "required_unresolved":
            required_unresolved,

        "optional_excluded":
            optional_excluded,

        "selections":
            selections,
    }

    write_json(
        repo / args.selection_json,
        output,
    )

    # ----------------------------------------------------------
    # Markdown audit
    # ----------------------------------------------------------

    lines = [
        "# MCAD — sélection canonique des sources de publication",
        "",
        f"- Git commit : `{output['git']['commit']}`",
        f"- Branche : `{output['git']['branch']}`",
        "- Nouvelle exécution expérimentale : **non**",
        "- Nouvelle exécution statistique : **non**",
        "",
        "| Bloc | Résolution | Publication | Source primaire |",
        "|---|---|---:|---|",
    ]

    for s in selections:
        root = (
            s["selected_bundles"][0]["root"]
            if s["selected_bundles"]
            else "—"
        )

        lines.append(
            "| "
            + s["campaign_id"]
            + " | `"
            + s["resolution"]
            + "` | "
            + (
                "oui"
                if s[
                    "publication_eligible"
                ]
                else "non"
            )
            + " | `"
            + root
            + "` |"
        )

    lines += [
        "",
        "## Règle",
        "",
        "Les résultats publiables sont extraits uniquement des "
        "bundles sélectionnés ci-dessus. Les autres candidats "
        "restent auditables mais ne sont pas autorisés comme "
        "source numérique par défaut.",
        "",
    ]

    if optional_excluded:
        lines += [
            "## Validation humaine",
            "",
            "La validation humaine n'est pas autorisée pour les "
            "métriques de publication tant qu'un bundle contenant "
            "à la fois les annotations et leur provenance canonique "
            "n'est pas identifié.",
            "",
        ]

    md_path = repo / args.selection_md
    md_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    md_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    # ----------------------------------------------------------
    # File-level source inventory
    # ----------------------------------------------------------

    inventory_path = (
        repo / args.inventory
    )

    inventory_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with inventory_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "campaign_id",
                "evidence_class",
                "selection_basis",
                "bundle_root",
                "bundle_git_tree_oid",
                "source_path",
                "size_bytes",
                "git_blob_oid",
                "sha256",
                "git_last_commit",
            ],
            lineterminator="\\n",
        )

        writer.writeheader()

        for s in selections:
            if not s[
                "publication_eligible"
            ]:
                continue

            roots = {
                b["root"]:
                    b.get(
                        "git_tree_oid"
                    )
                for b in s[
                    "selected_bundles"
                ]
            }

            for src in s[
                "authoritative_files"
            ]:
                source_path = src["path"]

                matching_root = ""

                for root in roots:
                    if (
                        source_path == root
                        or source_path.startswith(
                            root.rstrip("/")
                            + "/"
                        )
                    ):
                        matching_root = root
                        break

                writer.writerow(
                    {
                        "campaign_id":
                            s["campaign_id"],

                        "evidence_class":
                            s[
                                "evidence_class"
                            ],

                        "selection_basis":
                            s[
                                "selection_basis"
                            ],

                        "bundle_root":
                            matching_root,

                        "bundle_git_tree_oid":
                            roots.get(
                                matching_root
                            ),

                        "source_path":
                            source_path,

                        "size_bytes":
                            src.get(
                                "size_bytes"
                            ),

                        "git_blob_oid":
                            src.get(
                                "git_blob_oid"
                            ),

                        "sha256":
                            src.get(
                                "sha256"
                            ),

                        "git_last_commit":
                            src.get(
                                "git_last_commit"
                            ),
                    }
                )

    # ----------------------------------------------------------
    # Normalization contract
    # ----------------------------------------------------------

    contract = {
        "schema_version":
            "mcad-normalized-publication-data-contract-v1",

        "generated_at_utc":
            generated_at,

        "principles": {
            "no_hand_entered_final_numeric_results":
                True,

            "all_rows_retain_source_provenance":
                True,

            "physical_execution_and_replay_are_distinct":
                True,

            "semantic_decision_latency_not_backend_latency":
                True,

            "q1_q6_unit_of_evidence":
                "one_six_step_instrumented_trace",
        },

        "common_columns": [
            "campaign_id",
            "evidence_class",
            "run_id",
            "replication",
            "seed",
            "dataset",
            "backend",
            "session_id",
            "query_id",
            "step",
            "metric",
            "value",
            "unit",
            "source_path",
            "source_sha256",
            "source_git_blob_oid",
        ],

        "decision_columns": [
            "sat",
            "real_count",
            "ceval_count",
            "phi_intrinsic",
            "phi_cumulative",
            "delta_phi",
            "decision",
            "reason",
            "physical_executed",
            "ckg_updated",
        ],

        "timing_columns": [
            "factor",
            "factor_level",
            "semantic_decision_latency_ms",
            "measurement_role",
        ],

        "publication_families": {
            "physical": [
                "ui_q1_q6",
                "campaign_a_foodmart_depth",
                "campaign_b_multidataset_physical",
                "campaign_c_backend_portability",
            ],

            "controlled_replay_or_benchmark": [
                "baselines",
                "ablations_sat_real_ceval",
                "robustness",
                "scalability_ckg",
                "evidence_usefulness",
            ],

            "controlled_sensitivity_timing": [
                "sensitivity_constraint_count",
                "sensitivity_virtual_node_count",
                "sensitivity_membership_density",
                "sensitivity_objective_count",
            ],

            "conditional_human_validation": [
                "human_validation",
            ],
        },

        "next_generated_layers": [
            "data/long_form",
            "data/aggregated",
            "statistics",
            "tables/csv",
            "tables/tex",
            "figures/pdf",
            "figures/png",
            "claims/claim_evidence_matrix.csv",
            "sections",
        ],
    }

    write_json(
        repo / args.contract,
        contract,
    )

    # ----------------------------------------------------------
    # Console summary
    # ----------------------------------------------------------

    print(
        "PUBLICATION_SOURCE_RESOLUTION"
    )

    for s in selections:
        root = (
            s["selected_bundles"][0][
                "root"
            ]
            if s["selected_bundles"]
            else "NONE"
        )

        print(
            f"{s['campaign_id']}="
            f"{s['resolution']} "
            f"root={root}"
        )

    print(
        "required_unresolved_count="
        + str(
            len(
                required_unresolved
            )
        )
    )

    print(
        "optional_excluded_count="
        + str(
            len(
                optional_excluded
            )
        )
    )

    print(
        "scientific_execution_performed=false"
    )

    print(
        "experiment_rerun_performed=false"
    )

    print(
        "statistical_execution_performed=false"
    )

    if required_unresolved:
        print(
            "publication_source_resolution=BLOCKED"
        )

        print(
            "required_unresolved="
            + ",".join(
                required_unresolved
            )
        )

        raise SystemExit(42)

    print(
        "publication_source_resolution=PASS"
    )


if __name__ == "__main__":
    main()
