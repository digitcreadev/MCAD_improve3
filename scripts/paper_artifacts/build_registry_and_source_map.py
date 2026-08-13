#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


SOURCE_ROOTS = (
    "experiments/article/",
    "reports/article_experiments/",
    "backend/harness/",
    "bi-stack/",
    "exports/",
)


CAMPAIGNS = [
    {
        "campaign_id": "ui_q1_q6",
        "label": "UI / trace canonique Q1-Q6",
        "evidence_class": "physical_end_to_end",
        "scientific_question":
            "Le chemin MCAD peut-il être observé de bout en bout, "
            "de la requête à la décision physique et à l'évolution du CKG ?",
        "aliases": [
            "ui_q1_q6",
            "q1_q6",
            "q1-q6",
            "adventureworks_sales_margin_territory_q1_q6",
            "mcad_q1_q6_canonical",
        ],
        "runner_aliases": [
            "adventureworks",
            "q1_q6",
            "q1-q6",
        ],
    },
    {
        "campaign_id": "campaign_a_foodmart_depth",
        "label": "Campagne A — profondeur expérimentale FoodMart",
        "evidence_class": "physical_consolidated",
        "scientific_question":
            "Le contrat MCAD reste-t-il stable sur un volume conséquent "
            "de sessions et de décisions ?",
        "aliases": [
            "foodmart_campaign_a",
            "campaign_a_1000",
            "a_foodmart_1000",
            "foodmart_1000",
        ],
        "runner_aliases": [
            "foodmart_campaign_a",
            "campaign_a_1000",
            "foodmart_1000",
        ],
    },
    {
        "campaign_id": "campaign_b_multidataset_physical",
        "label": "Campagne B — validation physique multi-dataset",
        "evidence_class": "physical_multidataset",
        "scientific_question":
            "Le contrat ALLOW/BLOCK reste-t-il opérationnel sur plusieurs "
            "datasets, modèles sémantiques et chemins physiques ?",
        "aliases": [
            "campaign_b",
            "b_multidataset",
            "multidataset_controlled",
            "multidataset",
        ],
        "runner_aliases": [
            "campaign_b",
            "multidataset",
        ],
    },
    {
        "campaign_id": "campaign_c_backend_portability",
        "label": "Campagne C — portabilité backend contrôlée",
        "evidence_class": "physical_paired_backend",
        "scientific_question":
            "À dataset, objectif, workload et séquence constants, "
            "les décisions restent-elles stables lorsque seul le backend change ?",
        "aliases": [
            "campaign_c",
            "c_backend_portability",
            "backend_portability",
            "sql_vs_xmla",
        ],
        "runner_aliases": [
            "campaign_c",
            "backend_portability",
            "sql_vs_xmla",
        ],
    },
    {
        "campaign_id": "baselines",
        "label": "Baselines contrôlées",
        "evidence_class": "controlled_replay",
        "scientific_question":
            "Comment MCAD se compare-t-il à des politiques plus simples "
            "sur les exécutions inutiles et la couverture ?",
        "aliases": [
            "baseline",
            "baselines",
        ],
        "runner_aliases": [
            "baseline",
            "baselines",
        ],
    },
    {
        "campaign_id": "ablations_sat_real_ceval",
        "label": "Ablations SAT / Real / Ceval",
        "evidence_class": "controlled_ablation",
        "scientific_question":
            "SAT, Real et Ceval ont-ils chacun une contribution observable "
            "au comportement du système ?",
        "aliases": [
            "ablation",
            "ablations",
        ],
        "runner_aliases": [
            "ablation",
            "ablations",
        ],
    },
    {
        "campaign_id": "robustness",
        "label": "Robustesse",
        "evidence_class": "controlled_robustness",
        "scientific_question":
            "MCAD conserve-t-il un comportement sûr et explicable "
            "face à des perturbations et cas difficiles ?",
        "aliases": [
            "robustness",
            "robust",
        ],
        "runner_aliases": [
            "robustness",
            "robust",
        ],
    },
    {
        "campaign_id": "scalability_ckg",
        "label": "Scalabilité structurelle du CKG",
        "evidence_class": "controlled_scalability",
        "scientific_question":
            "Comment évoluent le coût de décision et l'état du CKG "
            "lorsque sa taille et son historique augmentent ?",
        "aliases": [
            "scalability",
            "scalabilite",
            "scale_benchmark",
            "scalability_benchmark",
        ],
        "runner_aliases": [
            "scalability",
            "scale_benchmark",
        ],
    },
    {
        "campaign_id": "evidence_usefulness",
        "label": "Evidence usefulness",
        "evidence_class": "controlled_treatment_control",
        "scientific_question":
            "L'evidence utile conservée après une session "
            "améliore-t-elle une session ultérieure ?",
        "aliases": [
            "evidence_usefulness",
            "evidence-usefulness",
            "usefulness",
        ],
        "runner_aliases": [
            "evidence_usefulness",
            "usefulness",
        ],
    },
    {
        "campaign_id": "sensitivity_constraint_count",
        "label": "Sensibilité — constraint_count",
        "evidence_class": "controlled_sensitivity_timing",
        "scientific_question":
            "Quel est l'effet du nombre de contraintes sur le comportement "
            "et le coût de décision sémantique de MCAD ?",
        "aliases": [
            "constraint_count",
            "sa3_constraint_count",
        ],
        "runner_aliases": [
            "constraint_count",
            "sensitivity_execution",
            "analyze_clustered_timing_precision",
        ],
    },
    {
        "campaign_id": "sensitivity_virtual_node_count",
        "label": "Sensibilité — virtual_node_count",
        "evidence_class": "controlled_sensitivity_timing",
        "scientific_question":
            "Quel est l'effet du nombre de nœuds virtuels sur le comportement "
            "et le coût de décision sémantique de MCAD ?",
        "aliases": [
            "virtual_node_count",
            "sa3_virtual_node_count",
        ],
        "runner_aliases": [
            "virtual_node_count",
            "sensitivity_execution",
            "analyze_clustered_timing_precision",
        ],
    },
    {
        "campaign_id": "sensitivity_membership_density",
        "label": "Sensibilité — membership_density",
        "evidence_class": "controlled_sensitivity_timing",
        "scientific_question":
            "Quel est l'effet de la densité d'appartenance exigences↔nœuds virtuels "
            "sur MCAD ?",
        "aliases": [
            "membership_density",
            "sa4_membership_density",
        ],
        "runner_aliases": [
            "membership_density",
            "sensitivity_execution",
            "analyze_clustered_timing_precision",
        ],
    },
    {
        "campaign_id": "sensitivity_objective_count",
        "label": "Sensibilité — objective_count",
        "evidence_class": "controlled_sensitivity_timing",
        "scientific_question":
            "Quel est l'effet du nombre d'objectifs sur le coût de décision "
            "sémantique et sa précision d'estimation ?",
        "aliases": [
            "objective_count",
            "sa5_objective_count",
        ],
        "runner_aliases": [
            "objective_count",
            "sensitivity_execution",
            "analyze_clustered_timing_precision",
        ],
    },
    {
        "campaign_id": "human_validation",
        "label": "Validation humaine / experts",
        "evidence_class": "optional_human_validation",
        "scientific_question":
            "Les jugements MCAD concordent-ils avec des annotations humaines "
            "dont la provenance est traçable ?",
        "aliases": [
            "human_validation",
            "human-validation",
            "annotator",
            "annotation",
            "expert_validation",
        ],
        "runner_aliases": [
            "human_validation",
            "annotation",
            "scoring",
        ],
        "optional": True,
    },
]


CONTROL_TOKENS = (
    "manifest",
    "status",
    "freeze",
    "provenance",
    "sha256sums",
    "summary",
    "decision",
    "verdict",
    "audit",
    "locked_runtime_readme",
    "reproduce",
    "readme",
)


DECLARED_KEYS = (
    "status",
    "next_stage",
    "rerun_forbidden",
    "precision_rerun_forbidden",
    "stage40_authorized",
    "stage30_sufficient",
    "stage20_sufficient",
    "stage10_sufficient",
    "all_precision_targets_met",
    "campaign_id",
    "factor",
    "replication_count",
    "measurement_count",
    "observation_count",
    "failing_cell_count",
    "failing_cells",
)


def run(*cmd: str) -> str:
    return subprocess.check_output(
        cmd,
        cwd=REPO,
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def last_commit(rel: str):
    try:
        value = run(
            "git",
            "log",
            "-1",
            "--format=%H",
            "--",
            rel,
        )
        return value or None
    except Exception:
        return None


def file_score(path: str, aliases) -> int:
    p = path.lower()
    score = 0

    for alias in aliases:
        if alias.lower() in p:
            score += 120

    if "/frozen_campaigns/" in p:
        score += 1200

    if "/locked/" in p:
        score += 1100

    if "/publication/final_" in p:
        score += 1000

    name = Path(p).name

    if "final_verdict" in name:
        score += 950

    if name == "freeze.json":
        score += 900

    if name == "manifest.json" or name.endswith("_manifest.json"):
        score += 800

    if name == "status.json":
        score += 760

    if name == "provenance.json":
        score += 720

    if name == "sha256sums" or "sha256sum" in name:
        score += 680

    if "decision" in name:
        score += 620

    if "summary" in name:
        score += 480

    if "audit" in name:
        score += 420

    return score


def is_control(path: str) -> bool:
    name = Path(path).name.lower()
    return any(token in name for token in CONTROL_TOKENS)


def declared_fields(path: Path):
    if path.suffix.lower() != ".json":
        return {}

    if path.stat().st_size > 10 * 1024 * 1024:
        return {}

    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(obj, dict):
        return {}

    result = {}

    for key in DECLARED_KEYS:
        value = obj.get(key)

        if isinstance(value, (str, int, float, bool)) or value is None:
            if key in obj:
                result[key] = value

        elif key == "failing_cells" and isinstance(value, list):
            result["failing_cell_count"] = len(value)

    return result


def record(rel: str, score=None):
    path = REPO / rel

    item = {
        "path": rel,
        "exists": path.is_file(),
        "git_last_commit": last_commit(rel),
    }

    if score is not None:
        item["score"] = score

    if path.is_file():
        item["size_bytes"] = path.stat().st_size
        item["sha256"] = sha256_file(path)

        fields = declared_fields(path)

        if fields:
            item["declared_fields"] = fields

    return item


def resolve_campaign(spec, source_files):
    aliases = [x.lower() for x in spec["aliases"]]
    runner_aliases = [x.lower() for x in spec["runner_aliases"]]

    candidates = []
    runners = []

    for rel in source_files:
        low = rel.lower()

        if any(alias in low for alias in aliases):
            candidates.append(
                (file_score(rel, aliases), rel)
            )

        if (
            rel.endswith((".py", ".sh"))
            and any(alias in low for alias in runner_aliases)
        ):
            runners.append(
                (file_score(rel, runner_aliases), rel)
            )

    candidates.sort(
        key=lambda value: (-value[0], value[1])
    )

    runners.sort(
        key=lambda value: (-value[0], value[1])
    )

    controls = [
        (score, rel)
        for score, rel in candidates
        if is_control(rel)
    ]

    canonical_controls = [
        (score, rel)
        for score, rel in controls
        if score >= 900
    ]

    if canonical_controls:
        selected = canonical_controls[:8]
        resolution = "CANONICAL_ANCHOR_IDENTIFIED"

    elif candidates:
        selected = controls[:8]
        resolution = "DISCOVERED_REQUIRES_CANONICAL_SELECTION"

    else:
        selected = []
        resolution = "SOURCE_NOT_FOUND"

    return {
        "campaign_id": spec["campaign_id"],
        "label": spec["label"],
        "scientific_question": spec["scientific_question"],
        "evidence_class": spec["evidence_class"],
        "optional": bool(spec.get("optional", False)),
        "source_resolution_status": resolution,

        "authoritative_control_files": [
            record(rel, score)
            for score, rel in selected
        ],

        "runner_candidates": [
            record(rel, score)
            for score, rel in runners[:10]
        ],

        "top_source_candidates": [
            record(rel, score)
            for score, rel in candidates[:20]
        ],
    }


def write_json(path: Path, obj):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            obj,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )


def write_markdown(path: Path, registry):
    lines = [
        "# MCAD — registre maître des sources expérimentales de publication",
        "",
        f"- Base git : `{registry['git']['base_commit']}`",
        f"- Branche : `{registry['git']['branch']}`",
        f"- Généré : `{registry['generated_at_utc']}`",
        "- Mode : résolution de sources et provenance uniquement.",
        "- Exécution scientifique : **non**.",
        "",
        "| Bloc | Classe de preuve | Résolution | Sources de contrôle | Runners |",
        "|---|---|---|---:|---:|",
    ]

    for campaign in registry["campaigns"]:
        lines.append(
            "| "
            + campaign["label"]
            + " | `"
            + campaign["evidence_class"]
            + "` | `"
            + campaign["source_resolution_status"]
            + "` | "
            + str(len(campaign["authoritative_control_files"]))
            + " | "
            + str(len(campaign["runner_candidates"]))
            + " |"
        )

    lines += [
        "",
        "## Contrat de publication",
        "",
        "Un nombre, tableau, graphique ou claim ne doit être publié "
        "que s'il peut être relié à une source canonique/gelée, "
        "à sa provenance et à un checksum.",
        "",
        "Les anciens manuscrits servent à reconstruire la structure "
        "éditoriale et les questions scientifiques ; ils ne constituent "
        "pas des sources numériques autoritaires.",
        "",
        "Les classes de preuves physiques, replay/benchmark et "
        "sensibilité/timing restent distinctes.",
        "",
        "## Étape suivante",
        "",
        "Résoudre exclusivement les campagnes marquées "
        "`DISCOVERED_REQUIRES_CANONICAL_SELECTION` à partir des bundles "
        "`locked` ou `frozen`, sans relancer les expériences. "
        "Les extracteurs publication-ready seront ensuite construits "
        "sur les sources sélectionnées.",
        "",
    ]

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--repo-root",
        required=True,
    )

    parser.add_argument(
        "--base-commit",
        required=True,
    )

    parser.add_argument(
        "--out",
        required=True,
    )

    args = parser.parse_args()

    global REPO

    REPO = Path(
        args.repo_root
    ).resolve()

    out = REPO / args.out

    tracked = run(
        "git",
        "ls-files",
    ).splitlines()

    source_files = [
        rel
        for rel in tracked
        if rel.startswith(SOURCE_ROOTS)
    ]

    campaigns = [
        resolve_campaign(
            spec,
            source_files,
        )
        for spec in CAMPAIGNS
    ]

    imported_maps = []

    for rel in (
        "reports/article_experiments/publication/"
        "final_sensitivity_sources/"
        "final_sensitivity_publication_source_map.json",

        "reports/article_experiments/publication/"
        "final_experimental_section/"
        "FINAL_EXPERIMENTAL_SECTION_MANIFEST.json",

        "reports/article_experiments/publication/"
        "final_experimental_section/"
        "PUBLICATION_CLAIMS_GATE.json",
    ):
        if (REPO / rel).is_file():
            imported_maps.append(
                record(rel)
            )

    generated_at = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    registry = {
        "schema_version":
            "mcad-publication-registry-v1",

        "generated_at_utc":
            generated_at,

        "generation_mode":
            "metadata_discovery_and_publication_source_resolution",

        "scientific_execution_performed":
            False,

        "experiment_rerun_performed":
            False,

        "git": {
            "base_commit":
                args.base_commit,

            "branch":
                run(
                    "git",
                    "branch",
                    "--show-current",
                ),

            "tree":
                run(
                    "git",
                    "rev-parse",
                    "HEAD^{tree}",
                ),

            "origin":
                run(
                    "git",
                    "remote",
                    "get-url",
                    "origin",
                ),
        },

        "methodology": {
            "lifecycle": [
                "audit",
                "validation",
                "freeze",
                "archive",
                "article_integration",
            ],

            "publication_flow": [
                "canonical_campaigns",
                "normalized_data",
                "statistics",
                "figures_tables_claims",
                "manuscript_pdf",
            ],

            "evidence_classes_must_remain_separate":
                True,
        },

        "campaigns":
            campaigns,

        "imported_existing_publication_maps":
            imported_maps,

        "derived_stages": [
            "normalization",
            "final_statistics",
            "article_ready_figures",
            "article_ready_tables",
            "claim_evidence_matrix",
            "generated_latex_sections",
            "final_manuscript_pdf",
        ],
    }

    write_json(
        out
        / "registry"
        / "campaign_registry.json",
        registry,
    )

    source_map = {
        "schema_version":
            "mcad-experimental-source-map-v1",

        "generated_at_utc":
            generated_at,

        "git":
            registry["git"],

        "campaigns":
            campaigns,

        "imported_existing_publication_maps":
            imported_maps,
    }

    write_json(
        out
        / "provenance"
        / "experimental_source_map.json",
        source_map,
    )

    write_markdown(
        out
        / "provenance"
        / "experimental_source_map.md",
        registry,
    )

    generator_rel = (
        "scripts/paper_artifacts/"
        "build_registry_and_source_map.py"
    )

    manifest = {
        "schema_version":
            "mcad-publication-build-manifest-v1",

        "generated_at_utc":
            generated_at,

        "generator":
            record(generator_rel),

        "base_commit":
            args.base_commit,

        "scientific_execution_performed":
            False,

        "experiment_rerun_performed":
            False,

        "campaign_count":
            len(campaigns),

        "canonical_anchor_identified_count":
            sum(
                campaign["source_resolution_status"]
                == "CANONICAL_ANCHOR_IDENTIFIED"
                for campaign in campaigns
            ),

        "requires_selection_count":
            sum(
                campaign["source_resolution_status"]
                == "DISCOVERED_REQUIRES_CANONICAL_SELECTION"
                for campaign in campaigns
            ),

        "source_not_found_count":
            sum(
                campaign["source_resolution_status"]
                == "SOURCE_NOT_FOUND"
                for campaign in campaigns
            ),
    }

    write_json(
        out
        / "manifests"
        / "publication_build_manifest.json",
        manifest,
    )

    checksums_dir = (
        out
        / "checksums"
    )

    checksums_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    checksum_targets = [
        out
        / "registry"
        / "campaign_registry.json",

        out
        / "provenance"
        / "experimental_source_map.json",

        out
        / "provenance"
        / "experimental_source_map.md",

        out
        / "manifests"
        / "publication_build_manifest.json",
    ]

    checksum_lines = []

    for path in checksum_targets:
        checksum_lines.append(
            sha256_file(path)
            + "  "
            + path.relative_to(REPO).as_posix()
        )

    (
        checksums_dir
        / "SHA256SUMS"
    ).write_text(
        "\n".join(checksum_lines)
        + "\n",
        encoding="utf-8",
    )

    print("PUBLICATION_REGISTRY_BUILD")
    print(
        "base_commit="
        + args.base_commit
    )
    print(
        "campaign_count="
        + str(len(campaigns))
    )
    print(
        "canonical_anchor_identified_count="
        + str(
            manifest[
                "canonical_anchor_identified_count"
            ]
        )
    )
    print(
        "requires_selection_count="
        + str(
            manifest[
                "requires_selection_count"
            ]
        )
    )
    print(
        "source_not_found_count="
        + str(
            manifest[
                "source_not_found_count"
            ]
        )
    )

    for campaign in campaigns:
        print(
            campaign["campaign_id"]
            + "="
            + campaign["source_resolution_status"]
        )

    print(
        "scientific_execution_performed=false"
    )
    print(
        "experiment_rerun_performed=false"
    )
    print(
        "registry_build=PASS"
    )


if __name__ == "__main__":
    main()
