#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

SECTION = r"""
\section{Validation expérimentale et analyse de performance}
\label{sec:experiments}

La validation expérimentale vise à vérifier que MCAD ne se limite pas à une formalisation abstraite, mais qu'il peut être exécuté, audité et rejoué sur des scénarios analytiques réalistes. La campagne expérimentale est organisée en trois volets complémentaires. La Campagne A évalue la profondeur et la stabilité du raisonnement CKG-first sur un grand nombre de sessions FoodMart. La Campagne B évalue la généralisation multi-dataset contrôlée sur FoodMart, AdventureWorksDW et SteelWheels. La Campagne C évalue la portabilité du comportement décisionnel lorsque le backend physique change, en comparant AdventureWorksDW via SQL Server Direct et via XMLA/eMondrian.

\input{article_update/generated_tables_abc/table_abc_evidence_synthesis.tex}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/exp_workflow_diagram.png}
\caption{Chaîne expérimentale reproductible utilisée pour reconstruire les sessions, décisions, preuves CKG, tableaux et figures de l'article.}
\label{fig:abc-workflow}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/fig_protocol_adopte.png}
\caption{Protocole adopté pour l'évaluation A--B--C : profondeur FoodMart, validation multi-dataset contrôlée et portabilité backend.}
\label{fig:abc-protocol}
\end{figure}

\subsection{Campagne A : profondeur expérimentale FoodMart}

La Campagne A constitue la campagne de profondeur. Elle exploite le snapshot FoodMart verrouillé afin d'évaluer la stabilité du mécanisme MCAD sur un volume important de sessions analytiques. Le snapshot verrouillé contient 2266 événements CKG utiles, correspondant aux contributions retenues après application du prédicat de validité contextuelle, de la réalisabilité, de la calculabilité et du filtrage par contribution marginale.

\input{article_update/generated_tables_abc/table_article_policy_summary.tex}

\input{article_update/generated_tables_abc/table_dataset_policy_summary.tex}

\input{article_update/generated_tables_abc/table_campaign_a_block_reasons.tex}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/fig_detection_performance.png}
\caption{Performance de détection : MCAD conserve les requêtes contributives tout en supprimant les exécutions non contributives et les false allows.}
\label{fig:detection-performance}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/false_allow_curve_by_step.png}
\caption{Évolution cumulée des false allows par étape de session. Les politiques permissives dérivent rapidement, tandis que MCAD maintient une sélectivité stricte.}
\label{fig:false-allow-curve}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/dataset_false_allow_portability.png}
\caption{Taux de false allow par dataset et signal de portabilité de la politique MCAD.}
\label{fig:dataset-false-allow-portability}
\end{figure}

\subsection{Robustesse, ablations et explicabilité des blocages}

La robustesse est évaluée au moyen de charges analytiques incluant des requêtes contributives, des requêtes bruitées, des violations de grain, des incompatibilités de slicers, des mesures non ciblées et des requêtes redondantes. L'objectif est de vérifier que MCAD ne bloque pas arbitrairement, mais qu'il produit des décisions explicables par des raisons liées au CKG et à la chaîne QP $\rightarrow$ SAT $\rightarrow$ Real $\rightarrow$ Ceval $\rightarrow$ $\phi$.

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/robustness_false_allow_by_policy.png}
\caption{Robustesse face aux charges bruitées et adversariales : comparaison du taux de false allow par politique.}
\label{fig:robustness-false-allow}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/robustness_block_reason_distribution_mcad.png}
\caption{Distribution des principales raisons de blocage sous MCAD. Les blocages sont rattachés à des violations ou insuffisances interprétables.}
\label{fig:block-reason-distribution}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/ablation_sensitivity_false_allow.png}
\caption{Analyse d'ablation : sensibilité du taux de false allow lorsque certains composants de la chaîne formelle sont affaiblis.}
\label{fig:ablation-sensitivity}
\end{figure}

\subsection{Scalabilité et contrôle de croissance du CKG}

La scalabilité est évaluée en faisant croître le nombre d'objectifs, de contraintes, de nœuds virtuels et d'événements de session. Les résultats visent à distinguer le coût du chemin de décision en ligne du coût de persistance et d'archivage du graphe. Cette distinction est importante, car MCAD doit rester compatible avec un usage interactif, même si le CKG croît au fil des sessions.

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/scalability_latency_vs_nvs.png}
\caption{Latence d'évaluation en fonction de la taille du modèle d'objectif et du nombre de nœuds virtuels.}
\label{fig:scalability-latency}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/ckg_growth_control_nodes.png}
\caption{Contrôle de croissance du CKG runtime : comparaison entre accumulation brute et compaction session-locale.}
\label{fig:ckg-growth-control}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/runtime_latency_quantiles.png}
\caption{Quantiles de latence runtime observés pendant l'évaluation.}
\label{fig:runtime-latency}
\end{figure}

\subsection{Utilité de l'évidence et validation humaine}

La couche d'évidence CKG est évaluée comme une mémoire utile, persistée et réutilisable. Une requête autorisée ne produit pas seulement un résultat analytique : elle crée une trace utile de contribution, liée à la session, à l'objectif, au backend et à la partie de l'objectif rendue calculable. Cette propriété permet d'amorcer des sessions ultérieures et de réduire le nombre d'étapes nécessaires pour retrouver une couverture complète.

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/evidence_usefulness_summary.png}
\caption{Utilité pratique de l'évidence CKG retenue : couverture initiale, réutilisation et réduction des étapes nécessaires.}
\label{fig:evidence-usefulness}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/evidence_bootstrap_steps_to_full.png}
\caption{Analyse bootstrap du nombre d'étapes nécessaires pour atteindre une couverture complète avec et sans évidence réutilisée.}
\label{fig:evidence-bootstrap}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/human_validation_scores.png}
\caption{Validation humaine externe : comparaison entre décisions MCAD et annotations expertes.}
\label{fig:human-validation}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/mcad_advantage_false_allow.png}
\caption{Avantage apparié de MCAD sur la réduction des false allows et des exécutions non contributives.}
\label{fig:paired-advantage}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/fig_paired_comparative_analysis.png}
\caption{Analyse comparative appariée entre MCAD et les politiques de référence.}
\label{fig:paired-comparative-analysis}
\end{figure}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/fig_efficiency_explainability.png}
\caption{Synthèse efficacité--explicabilité : compromis entre filtrage stratégique, coût d'évaluation et justification des décisions.}
\label{fig:efficiency-explainability}
\end{figure}

\subsection{Campagne B : validation multi-dataset contrôlée}

La Campagne B vérifie que MCAD conserve son comportement sur plusieurs entrepôts et plusieurs backends. Elle couvre trois scénarios contrôlés : FoodMart via XMLA/Mondrian, AdventureWorksDW via SQL Server Direct et SteelWheels via SQL Server Direct. Sur 18 requêtes, MCAD produit les 18 décisions attendues. Les 7 décisions ALLOW sont exécutées physiquement, tandis que les 11 décisions BLOCK sont arrêtées avant toute exécution physique. Le CKG verrouillé de la Campagne B contient exactement 7 événements utiles, et le snapshot A reste inchangé à 2266 événements.

\input{article_update/generated_tables_abc/table_campaign_b_controlled_minimal.tex}

\subsection{Campagne C : portabilité backend AdventureWorksDW}

La Campagne C évalue une propriété différente de la Campagne B : la portabilité backend. Le même objectif AdventureWorksDW et la même séquence analytique sont exécutés dans deux sous-runs isolés, l'un via SQL Server Direct et l'autre via XMLA/eMondrian. Chaque sous-run démarre avec un CKG vide afin d'éviter qu'un backend ne bénéficie des événements créés par l'autre. Les deux chemins produisent la même séquence de décisions, les mêmes raisons de décision, la même politique d'exécution physique et deux événements CKG utiles chacun.

\input{article_update/generated_tables_abc/table_campaign_c_portability.tex}

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/fig_backend_portability.png}
\caption{Campagne C : portabilité backend AdventureWorksDW entre SQL Server Direct et XMLA/eMondrian.}
\label{fig:backend-portability}
\end{figure}

\subsection{Synthèse transversale}

Les trois campagnes ne mesurent pas la même propriété. La Campagne A établit la profondeur et la stabilité du raisonnement CKG-first sur un grand nombre de sessions. La Campagne B établit que MCAD peut être appliqué de manière contrôlée à plusieurs datasets et backends tout en préservant la séparation entre requêtes contributives et non contributives. La Campagne C établit que, pour un même objectif et une même séquence analytique, le comportement décisionnel est conservé lorsque le backend physique change.

La portée de ces résultats reste celle d'un prototype de recherche. Les expériences ne démontrent pas une supériorité universelle sur tout moteur OLAP ou toute politique analytique possible. Elles établissent cependant que la chaîne formelle proposée est exécutable, reproductible, auditable, multi-dataset et portable sur les scénarios étudiés.
"""

def ensure_package(tex: str, pkg: str) -> str:
    if f"\\usepackage{{{pkg}}}" in tex or re.search(r"\\usepackage\[[^\]]*\]\{" + re.escape(pkg) + r"\}", tex):
        return tex
    m = re.search(r"(\\documentclass(?:\[[^\]]*\])?\{[^}]+\}\s*)", tex)
    if not m:
        return tex
    return tex[:m.end()] + f"\\usepackage{{{pkg}}}\n" + tex[m.end():]

def ensure_graphicspath(tex: str) -> str:
    if "\\graphicspath" in tex:
        return tex
    anchor = "\\begin{document}"
    if anchor in tex:
        return tex.replace(anchor, "\\graphicspath{{figures/}}\n" + anchor, 1)
    return tex

def replace_section(tex: str) -> str:
    pattern = re.compile(
        r"\\section\{[^}]*VALIDATION EXP[ÉE]RIMENTALE[^}]*\}.*?(?=\\section\{)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(tex)
    if not m:
        raise SystemExit("Could not find the experimental section to replace.")

    # Do not use re.sub/re.subn with SECTION as a replacement string:
    # SECTION contains LaTeX commands such as \section, and Python would
    # interpret \s as an invalid regex replacement escape.
    return tex[:m.start()] + SECTION.strip() + "\n\n" + tex[m.end():]

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tex", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--stable-table-dir", default="article_update/generated_tables_abc")
    args = ap.parse_args()

    tex_path = Path(args.tex)
    run_dir = Path(args.run_dir)
    src_tables = run_dir / "paper_artifacts" / "tables"
    dst_tables = Path(args.stable_table_dir)

    if not tex_path.exists():
        raise SystemExit(f"Missing tex file: {tex_path}")
    if not src_tables.exists():
        raise SystemExit(f"Missing generated tables: {src_tables}")

    dst_tables.mkdir(parents=True, exist_ok=True)
    for p in src_tables.glob("*.tex"):
        shutil.copy2(p, dst_tables / p.name)

    original = tex_path.read_text(encoding="utf-8")
    backup = tex_path.with_suffix(tex_path.suffix + ".bak")
    backup.write_text(original, encoding="utf-8")

    tex = original
    for pkg in ["graphicx", "booktabs", "array"]:
        tex = ensure_package(tex, pkg)
    tex = ensure_graphicspath(tex)
    tex = replace_section(tex)

    tex_path.write_text(tex, encoding="utf-8")

    print("[OK] integrated A-B-C artifacts into", tex_path)
    print("[OK] backup:", backup)
    print("[OK] stable tables:", dst_tables)

if __name__ == "__main__":
    main()
