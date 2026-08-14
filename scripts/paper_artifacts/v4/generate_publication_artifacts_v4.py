#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_HEAD = "922815488832ecf20d6f31008da044bd3e1c02b0"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def normalize_text_bytes(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def read_csv(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    first = text.splitlines()[0] if text.splitlines() else ""
    delim = ";" if first.count(";") > first.count(",") else ","
    return delim, list(csv.DictReader(io.StringIO(text), delimiter=delim))


def write_csv(path: Path, fields, rows, delimiter=","):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=delimiter, lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def tex_escape(s) -> str:
    s = str(s)
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(repl.get(ch, ch) for ch in s)


def boolish(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "pass"}


def linear_quantile(values, probability: float) -> float:
    vals = sorted(float(v) for v in values)
    if not vals:
        raise RuntimeError("cannot compute quantile from empty values")
    if len(vals) == 1:
        return vals[0]
    pos = probability * (len(vals) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return vals[lo]
    frac = pos - lo
    return vals[lo] + frac * (vals[hi] - vals[lo])


def read_latency_rows(path: Path):
    _, rows = read_csv(path)
    valid = []
    for row in rows:
        if row.get("phase") and row.get("phase") != "measurement":
            continue
        if row.get("fresh_state") not in (None, "") and not boolish(row.get("fresh_state")):
            continue
        if row.get("semantic_match") not in (None, "") and not boolish(row.get("semantic_match")):
            continue
        try:
            level = float(row["factor_level"])
            step = int(float(row.get("step_index", 0)))
            latency = float(row["wall_latency_ms"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(latency) or latency <= 0:
            continue
        valid.append((level, step, latency))
    if not valid:
        raise RuntimeError(f"no valid wall_latency_ms observations in {path}")
    return valid


def summarize_latency_quantiles(factor: str, rows, source: str):
    grouped = {}
    for level, step, latency in rows:
        grouped.setdefault(level, []).append(latency)
    out = []
    for level in sorted(grouped):
        vals = grouped[level]
        p50 = linear_quantile(vals, 0.50)
        p95 = linear_quantile(vals, 0.95)
        p99 = linear_quantile(vals, 0.99)
        out.append({
            "factor": factor,
            "factor_level": int(level) if float(level).is_integer() else level,
            "observation_count": len(vals),
            "p50_ms": f"{p50:.9f}",
            "p95_ms": f"{p95:.9f}",
            "p99_ms": f"{p99:.9f}",
            "p95_over_p50": f"{(p95/p50):.6f}",
            "p99_over_p50": f"{(p99/p50):.6f}",
            "source": source,
            "interpretation": "DESCRIPTIVE_EXISTING_MEASUREMENTS_NO_NEW_EXECUTION",
        })
    return out


def pgf_line(path: Path, title: str, xlabel: str, ylabel: str, series,
             xticks=None, xticklabels=None, ymin=None, ymax=None,
             legend_columns=2):
    opts = [
        r"width=\linewidth",
        r"height=0.58\linewidth",
        rf"title={{{title}}}",
        rf"xlabel={{{xlabel}}}",
        rf"ylabel={{{ylabel}}}",
        r"grid=major",
        rf"legend style={{font=\scriptsize,at={{(0.5,-0.28)}},anchor=north,legend columns={legend_columns}}}",
    ]
    if xticks is not None:
        opts.append("xtick={" + ",".join(str(x) for x in xticks) + "}")
    if xticklabels is not None:
        opts.append("xticklabels={" + ",".join("{" + str(x) + "}" for x in xticklabels) + "}")
        opts.append(r"x tick label style={rotate=22,anchor=east,font=\scriptsize}")
    if ymin is not None:
        opts.append(f"ymin={ymin}")
    if ymax is not None:
        opts.append(f"ymax={ymax}")
    lines = [r"\begin{tikzpicture}", r"\begin{axis}[" + ",\n".join(opts) + "]"]
    marks = ["*", "square*", "triangle*", "diamond*", "x", "+", "o", "asterisk"]
    for i, (name, xs, ys) in enumerate(series):
        coords = " ".join(f"({x},{y})" for x, y in zip(xs, ys))
        lines.append(rf"\addplot+[mark={marks[i % len(marks)]}] coordinates {{{coords}}};")
        lines.append(r"\addlegendentry{" + name + "}")
    lines += [r"\end{axis}", r"\end{tikzpicture}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def pgf_grouped_bar(path: Path, title: str, ylabel: str, labels, series,
                    ymax=None, legend_columns=2):
    n = len(labels)
    opts = [
        r"ybar",
        r"bar width=7pt",
        r"width=\linewidth",
        r"height=0.58\linewidth",
        rf"title={{{title}}}",
        rf"ylabel={{{ylabel}}}",
        "xtick={" + ",".join(str(i) for i in range(n)) + "}",
        "xticklabels={" + ",".join("{" + x + "}" for x in labels) + "}",
        r"x tick label style={rotate=20,anchor=east,font=\scriptsize}",
        r"grid=major",
        rf"legend style={{font=\scriptsize,at={{(0.5,-0.28)}},anchor=north,legend columns={legend_columns}}}",
        r"ymin=0",
    ]
    if ymax is not None:
        opts.append(f"ymax={ymax}")
    lines = [r"\begin{tikzpicture}", r"\begin{axis}[" + ",\n".join(opts) + "]"]
    for name, vals in series:
        coords = " ".join(f"({i},{v})" for i, v in enumerate(vals))
        lines.append(r"\addplot+ coordinates {" + coords + "};")
        lines.append(r"\addlegendentry{" + name + "}")
    lines += [r"\end{axis}", r"\end{tikzpicture}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def pgf_xbar(path: Path, title: str, xlabel: str, labels, values):
    n = len(labels)
    opts = [
        r"xbar",
        r"bar width=7pt",
        r"width=\linewidth",
        r"height=0.68\linewidth",
        rf"title={{{title}}}",
        rf"xlabel={{{xlabel}}}",
        "ytick={" + ",".join(str(i) for i in range(n)) + "}",
        "yticklabels={" + ",".join("{" + x + "}" for x in labels) + "}",
        r"y tick label style={font=\scriptsize}",
        r"grid=major",
        r"xmin=0",
    ]
    coords = " ".join(f"({v},{i})" for i, v in enumerate(values))
    lines = [
        r"\begin{tikzpicture}",
        r"\begin{axis}[" + ",\n".join(opts) + "]",
        r"\addplot+ coordinates {" + coords + "};",
        r"\end{axis}",
        r"\end{tikzpicture}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one occurrence, found {count}")
    return text.replace(old, new, 1)


def replace_regex_once(text: str, pattern: str, repl, label: str) -> str:
    new, n = re.subn(pattern, repl, text, count=1, flags=re.S)
    if n != 1:
        raise RuntimeError(f"{label}: expected exactly one regex replacement, found {n}")
    return new


def extract_single_archive_member(archive: Path, suffix: str, out_path: Path):
    with tarfile.open(archive, "r:gz") as tf:
        candidates = [m for m in tf.getmembers() if m.isfile() and m.name.endswith(suffix)]
        if len(candidates) != 1:
            raise RuntimeError(
                f"expected exactly one archive member ending with {suffix!r}, found {len(candidates)}"
            )
        raw = tf.extractfile(candidates[0]).read()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(normalize_text_bytes(raw))
    return candidates[0].name


def extract_constraint_count_intervals(repo: Path, out_path: Path):
    archive_dir = repo / "experiments/article/frozen_campaigns/sa3_constraint_count_stage20/archive"
    archives = sorted(archive_dir.glob("constraint_count_stage20_canonical_*.tar.gz"))
    if len(archives) != 1:
        raise RuntimeError(f"constraint_count: expected exactly one canonical archive, found {len(archives)}")
    archive = archives[0]
    with tarfile.open(archive, "r:gz") as tf:
        candidates = [
            m for m in tf.getmembers()
            if m.isfile()
            and m.name.endswith(
                "planning/aggregates/constraint_count_nv24_stage20/"
                "formal_timing/cluster_bootstrap_intervals.csv"
            )
        ]
        if len(candidates) != 1:
            raise RuntimeError(
                f"constraint_count: expected one Stage20 interval CSV in archive, found {len(candidates)}"
            )
        raw = tf.extractfile(candidates[0]).read()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(normalize_text_bytes(raw))
    return {
        "archive": archive.relative_to(repo).as_posix(),
        "archive_sha256": sha256_file(archive),
        "member": candidates[0].name,
    }


def patch_bibliography_and_claims(manuscript: str):
    changes = []

    old_abs = (
        "Aucune de ces lignes de recherche ne fournit un mécanisme formel permettant "
        "de mesurer, requête par requête et session par session, dans quelle mesure "
        "une requête OLAP contribue effectivement à un objectif stratégique donné."
    )
    new_abs = (
        "À notre connaissance, parmi les familles de travaux examinées dans la "
        "Section~\\ref{sec:related}, nous n'avons pas identifié de mécanisme formel "
        "unifié qui mesure, requête par requête et session par session, la part de "
        "contraintes stratégiques explicitement rendues calculables par une requête OLAP."
    )
    manuscript = replace_once(manuscript, old_abs, new_abs, "bounded novelty in abstract")
    changes.append({"id": "CIT01", "location": "Résumé", "action": "absolute novelty -> bounded literature conclusion"})

    old_intro = (
        "Ces travaux constituent des briques importantes, mais ils ne fournissent pas "
        "un cadre unifié capable de répondre à la question suivante pour une requête donnée : "
        "\\emph{dans quelle mesure cette requête contribue-t-elle réellement à l'objectif stratégique visé ?}"
    )
    new_intro = (
        "Ces travaux constituent des briques importantes. À notre connaissance, "
        "la synthèse de la Section~\\ref{sec:related} ne met toutefois pas en évidence "
        "un cadre unifié qui relie, au niveau d'une requête individuelle, admissibilité "
        "contextuelle, évidence réalisable et nouvelles contraintes stratégiques "
        "rendues calculables."
    )
    manuscript = replace_once(manuscript, old_intro, new_intro, "bounded novelty in introduction")
    changes.append({"id": "CIT01-PROP", "location": "Introduction", "action": "propagate bounded novelty wording"})

    for old, new, cid in [
        ("\\cite{SHACL2017}", "\\cite{W3CSHACL2017}", "KEY-SHACL"),
        ("\\cite{PROVO2013}", "\\cite{W3CPROVO2013}", "KEY-PROVO"),
        ("\\cite{TaramadIntent2022}", "\\cite{FarihaMeliou2019}", "KEY-INTENT"),
    ]:
        if old not in manuscript:
            raise RuntimeError(f"{cid}: old citation key not found")
        manuscript = manuscript.replace(old, new)
        changes.append({"id": cid, "location": "Section II", "action": f"{old} -> {new}"})

    positioning = r'''\begin{table*}[!t]
\centering
\caption{Positionnement et frontières de MCAD par rapport aux familles de recherche voisines. Les qualificatifs « non central » et « non ciblé » décrivent le centre de gravité des travaux cités et ne constituent pas des affirmations d'absence exhaustive.}
\scriptsize
\setlength{\tabcolsep}{3pt}
\begin{tabular}{@{}p{2.65cm}p{1.15cm}p{1.25cm}p{2.15cm}p{2.2cm}p{1.75cm}p{1.55cm}@{}}
\toprule
Famille & Centré utilisateur & Centré objectif & Modèle principal de contexte & Cible principale d'évaluation & Calculabilité stratégique & Gating au niveau requête \\
\midrule
Personnalisation OLAP~\cite{AissiGouider2012,GarrigosER2009,JacobGunklachMaedche2025} & Oui & Non central & Profil / préférences / métadonnées & Adaptation personnalisée de vue ou de schéma & Non ciblée & Non ciblé \\
Guidage BI\&A et recommandation OLAP~\cite{AligonDSS2015,GunklachNadj2023} & Oui & Non central & État de session / traces / support d'interaction & Exploration guidée et pertinence des étapes suivantes & Non ciblée & Non ciblé \\
OLAP sensible au contexte~\cite{RoyContextOLAP2022,AdomaviciusTuzhilin2011} & Partiel & Non central & Attributs de contexte & Classement ou filtrage dépendant du contexte & Non ciblée & Limité / non central \\
BI / DSS orientés objectifs~\cite{Pourshahid2014} & Non central & Oui & Objectifs, KPI, processus de décision & Alignement de l'objectif au niveau processus & Partiel & Non ciblé \\
Graphes de connaissances / modèles sémantiques de KPI~\cite{HoganKGSurvey2021,DiamantiniKPISurvey2025,Niedritis2011,StaudingerSchuetzSchrefl2025} & Non central & Partiel & Graphe / ontologie / provenance & Cohérence sémantique et interprétation & Non ciblée & Non ciblé \\
KG-OLAP / QB4OLAP~\cite{Etcheverry2014,SchuetzSerafiniBozzato2021} & Non central & Non central & Graphe sémantique multidimensionnel & Modélisation et interrogation de style OLAP & Non ciblée & Non ciblé \\
DSS explicables / DSS fondés sur XAI~\cite{KostopoulosXAIDSS2024} & Partiel & Partiel & Modèle / cas / provenance / interface d'explication & Recommandation ou prédiction transparente & Non ciblée & Non ciblé \\
MCAD (proposé) & Non central & Oui & Graphe de connaissances contextuel ancré aux objectifs & Calculabilité des contraintes et contribution de session & Oui & Oui \\
\bottomrule
\end{tabular}
\normalsize
\label{tab:positioning}
\end{table*}'''
    manuscript = replace_regex_once(
        manuscript,
        r"\\begin\{table\*\}\[!t\]\s*\\centering\s*\\caption\{Positionnement et frontières de MCAD.*?\\label\{tab:positioning\}\s*\\end\{table\*\}",
        lambda m: positioning,
        "positioning table"
    )
    changes.append({"id": "CIT02", "location": "Section II / tableau de positionnement", "action": "categorical absence softened"})

    old_rel_sentence = (
        "Les arêtes sont étiquetées par des relations telles que \\textit{rolls\\_up\\_to}, "
        "\\textit{has\\_measure}, \\textit{defines\\_KPI}, \\textit{uses\\_unit}, "
        "\\textit{allowed\\_agg}, \\textit{requires\\_grain}, \\textit{conflicts\\_with}, "
        "ou \\textit{applicable\\_in\\_scenario}~\\cite{HoganKGSurvey2021,DiamantiniKPISurvey2025,Niedritis2011,RomeroAbello2010}. "
        "Les règles de calcul des KPI et les contraintes métier sont encodées sous forme de nœuds et d'arêtes supplémentaires."
    )
    new_rel_sentence = (
        "La littérature sur les graphes de connaissances, les indicateurs sémantiques et "
        "la conception multidimensionnelle motive l'emploi d'une représentation graphée "
        "et de définitions formelles des objets analytiques~\\cite{HoganKGSurvey2021,"
        "DiamantiniKPISurvey2025,Niedritis2011,RomeroAbello2010}. "
        "Dans MCAD, les noms de relations \\textit{rolls\\_up\\_to}, "
        "\\textit{has\\_measure}, \\textit{defines\\_KPI}, \\textit{uses\\_unit}, "
        "\\textit{allowed\\_agg}, \\textit{requires\\_grain}, \\textit{conflicts\\_with} "
        "et \\textit{applicable\\_in\\_scenario} sont des choix de conception propres au "
        "prototype; ils ne sont pas attribués aux travaux cités. Les règles de calcul des "
        "KPI et les contraintes métier sont encodées sous forme de nœuds et d'arêtes supplémentaires."
    )
    manuscript = replace_once(manuscript, old_rel_sentence, new_rel_sentence, "MCAD-specific relation vocabulary")
    changes.append({"id": "CIT06", "location": "Section IV / CKG", "action": "generic literature separated from MCAD relation vocabulary"})

    portability = r'''\subsection{Portabilité entre langages de requête}

Le formalisme de MCAD dépend d'une représentation canonique
$QP=(f_Q,g_Q,M_Q,\alpha_Q,u_Q,S_Q,w_Q)$, et non d'une syntaxe de requête
particulière. L'indépendance revendiquée à ce niveau est donc une propriété
d'interface conceptuelle : pour tout langage analytique $L$ pour lequel un
extracteur fiable $\mathcal{E}_L(q,CKG)=QP$ est disponible, le même raisonneur
$\mathrm{SAT}/\mathrm{Real}/C_{\mathrm{eval}}/\varphi$ peut être réutilisé sans
modifier sa sémantique.

Cette propriété ne signifie pas que des extracteurs de maturité équivalente
existent ou ont été validés pour tous les langages analytiques. La
Section~\ref{sec:arch} décrit séparément les chemins effectivement implémentés
dans le prototype courant (MDX, SQL analytique et plan canonique matérialisé),
tandis que la Section~\ref{sec:exp} borne les affirmations de portabilité aux
datasets, adaptateurs et backends effectivement exercés expérimentalement.

'''
    manuscript = replace_regex_once(
        manuscript,
        r"\\subsection\{Portabilité entre langages de requête\}.*?(?=\\section\{Architecture du prototype et flux de travail\})",
        lambda m: portability,
        "query language portability scope"
    )
    changes.append({"id": "CIT07", "location": "Section IV", "action": "conceptual canonicalization separated from implemented parsers/evidence"})

    old_impl = (
        "Cette conception rend explicite, au niveau de l'implémentation, l'affirmation "
        "du papier sur l'indépendance vis-à-vis du langage : le raisonneur d'exécution "
        "consomme des plans canoniques même lorsque les requêtes initiales proviennent "
        "de syntaxes front-end différentes."
    )
    new_impl = (
        "Cette conception matérialise, pour les chemins effectivement implémentés, "
        "l'interface canonique postulée par le modèle : le raisonneur consomme des plans "
        "canoniques après extraction MDX ou SQL analytique, ou directement lorsqu'un QP "
        "est fourni. Elle ne constitue pas une validation de DAX ni d'autres langages "
        "non exercés par le prototype courant."
    )
    manuscript = replace_once(manuscript, old_impl, new_impl, "Section V implementation scope")
    changes.append({"id": "CIT07-PROP", "location": "Section V", "action": "implemented parser scope made explicit"})

    bib_repls = {
        "SchuetzSerafiniBozzato2021": (
            "\\bibitem{SchuetzSerafiniBozzato2021}\n"
            "C.~G. Schuetz, L.~Bozzato, B.~Neumayr, M.~Schrefl, and L.~Serafini, "
            "``Knowledge Graph OLAP: A multidimensional model and query operations for "
            "contextualized knowledge graphs,'' \\emph{Semantic Web}, vol.~12, no.~4, "
            "pp.~649--683, 2021, doi: 10.3233/SW-200419.\n"
        ),
        "StaudingerSchuetzSchrefl2025": (
            "\\bibitem{StaudingerSchuetzSchrefl2025}\n"
            "S.~Staudinger, C.~G. Schuetz, M.~Schrefl, and T.~Neub\\\"ock, "
            "``Knowledge graph support for descriptive business analytics,'' "
            "\\emph{DECISION}, vol.~52, no.~3, pp.~285--306, 2025, "
            "doi: 10.1007/s40622-025-00432-4.\n"
        ),
        "KostopoulosXAIDSS2024": (
            "\\bibitem{KostopoulosXAIDSS2024}\n"
            "G.~Kostopoulos, G.~Davrazos, and S.~Kotsiantis, ``Explainable artificial "
            "intelligence-based decision support systems: A recent review,'' "
            "\\emph{Electronics}, vol.~13, no.~14, Art.~no.~2842, 2024, "
            "doi: 10.3390/electronics13142842.\n"
        ),
    }
    for key, block in bib_repls.items():
        pattern = rf"\\bibitem\{{{re.escape(key)}\}}.*?(?=\n\\bibitem|\n\\end\{{thebibliography\}})"
        manuscript = replace_regex_once(manuscript, pattern, lambda m, b=block: b.rstrip(), f"bibliography {key}")
        changes.append({"id": f"BIB-{key}", "location": "Bibliographie", "action": "verified metadata correction"})

    # Performance-evaluation methodology references.
    perf_bib = r"""
\bibitem{DeanBarroso2013}
J.~Dean and L.~A. Barroso, ``The tail at scale,'' \emph{Communications of the ACM}, vol.~56, no.~2, pp.~74--80, 2013.

\bibitem{KaliberaJones2013}
T.~Kalibera and R.~E. Jones, ``Rigorous benchmarking in reasonable time,'' in \emph{Proc. ACM SIGPLAN Int. Symp. Memory Management (ISMM)}, 2013, pp.~63--74, doi: 10.1145/2464157.2464160.
"""
    manuscript = replace_once(
        manuscript,
        "\n\\end{thebibliography}",
        "\n" + perf_bib.strip() + "\n\n\\end{thebibliography}",
        "performance bibliography insertion",
    )
    changes.append({
        "id": "BIB-PERFORMANCE-METHOD",
        "location": "Bibliographie + Section VII",
        "action": "add tail-latency and rigorous benchmarking methodology references",
    })

    manuscript = manuscript.replace(r"\begin{thebibliography}{23}", r"\begin{thebibliography}{99}")
    manuscript = manuscript.replace("sur deux entrepôts de type benchmark", "sur plusieurs entrepôts et chemins backend contrôlés")

    conclusion_new = r'''Les preuves physiques Q1--Q6 et A--C, le freeze de robustesse non temporel,
la scalabilité structurelle, l'étude contrôlée de réutilisation de l'évidence
et les quatre campagnes de sensibilité convergent vers une conclusion bornée :
sur les scénarios étudiés, MCAD rend l'exécution analytique sélective et
explicable en reliant chaque décision à la calculabilité marginale de
contraintes stratégiques explicites. Les comparaisons du freeze de robustesse
montrent l'élimination observée des \emph{false allows} et des exécutions non
contributives pour MCAD dans ce protocole, tandis que les campagnes physiques
établissent le gate avant backend sur les datasets et adaptateurs testés.

La portée de ce résultat reste celle d'un prototype de recherche. La
scalabilité publiée est structurelle; les timings historiques de mai ne sont
pas utilisés comme preuve de performance finale; aucune validation humaine ou
experte n'est revendiquée. La sensibilité au nombre d'objectifs documente en
outre une limite négative importante : au Stage-30 terminal, 17 des 192
cellules de précision restent hors des cibles préenregistrées malgré 30
clusters structurels et 576000 mesures. Cette limite est conservée comme
résultat scientifique et non contournée par un rerun, un bootstrap
supplémentaire ou un Stage-40. L'ensemble soutient donc une démonstration
reproductible et auditée du mécanisme MCAD, sans revendiquer une supériorité
universelle ni une maturité industrielle déjà acquise.'''
    manuscript = replace_regex_once(
        manuscript,
        r"L'étude de cas FoodMart, la généralisation à un second dataset de type AdventureWorks,.*?(?=\n\n\\appendices)",
        lambda m: conclusion_new,
        "conclusion evidence propagation"
    )
    changes.append({"id": "PROP-CONCLUSION", "location": "Conclusion", "action": "human/timing stale claims removed; final evidence gates propagated"})

    for key in ["SHACL2017", "PROVO2013", "TaramadIntent2022"]:
        if re.search(rf"\\cite\{{[^}}]*\b{re.escape(key)}\b", manuscript):
            raise RuntimeError(f"old citation alias still used: {key}")

    return manuscript, changes


def publication_patch_regression_guard(repo: Path) -> None:
    manuscript_path = (
        repo
        / "article_update/paper_artifacts_final/manuscript/"
          "MCAD_audited_real_main_fr_v3.tex"
    )
    if not manuscript_path.is_file():
        raise RuntimeError("V3 manuscript missing for publication patch regression guard")

    source = manuscript_path.read_text(encoding="utf-8")
    patched, _ = patch_bibliography_and_claims(source)

    required = [
        r"\bibitem{DeanBarroso2013}",
        r"\bibitem{KaliberaJones2013}",
        r"\bibitem{W3CSHACL2017}",
        r"\bibitem{W3CPROVO2013}",
    ]
    for token in required:
        if token not in patched:
            raise RuntimeError(
                f"publication patch regression guard missing token: {token}"
            )

    forbidden = [
        r"\cite{SHACL2017}",
        r"\cite{PROVO2013}",
        r"\cite{TaramadIntent2022}",
    ]
    for token in forbidden:
        if token in patched:
            raise RuntimeError(
                f"publication patch regression guard stale token: {token}"
            )

    if patched.count(r"\end{thebibliography}") != 1:
        raise RuntimeError(
            "publication patch regression guard bibliography closure mismatch"
        )


def main(repo: Path, out: Path):
    repo = repo.resolve()
    out = out.resolve()
    if out.exists():
        shutil.rmtree(out)

    dirs = {
        "data": out / "data",
        "fig": out / "figures",
        "prov": out / "provenance",
        "bibprov": out / "provenance" / "bibliography",
        "visprov": out / "provenance" / "visual",
        "sections": out / "sections",
        "manuscript": out / "manuscript",
        "supplement": out / "supplement",
        "manifest": out / "manifest",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    current_head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    if current_head != EXPECTED_HEAD:
        raise RuntimeError(f"expected HEAD {EXPECTED_HEAD}, got {current_head}")

    publication_patch_regression_guard(repo)
    print("publication_patch_regression_guard=PASS")

    v3 = repo / "article_update/paper_artifacts_final"
    v3_main = v3 / "manuscript/MCAD_audited_real_main_fr_v3.tex"
    v3_sec = v3 / "sections/section_experimentale_finale_v3.tex"
    if not v3_main.is_file() or not v3_sec.is_file():
        raise RuntimeError("V3 manuscript/experimental section missing")

    copy_files = [
        "campaign_a_1000_summary.json",
        "campaign_b_summary.csv",
        "campaign_c_summary.csv",
        "evidence_bootstrap_secondary.json",
        "evidence_usefulness_secondary.json",
        "q1_q6_canonical_trace.csv",
        "robustness_by_scenario_type.csv",
        "robustness_explainability_summary.csv",
        "robustness_policy_summary.csv",
        "scalability_catalog_structural.csv",
        "policy_summary_secondary_non_temporal.csv",
    ]
    for name in copy_files:
        src = v3 / "data" / name
        if not src.is_file():
            raise RuntimeError(f"missing V3 publication-facing data: {name}")
        (dirs["data"] / name).write_bytes(normalize_text_bytes(src.read_bytes()))

    sensitivity_map_src = v3 / "provenance/final_sensitivity_publication_source_map.json"
    sensitivity_map = json.loads(sensitivity_map_src.read_text(encoding="utf-8"))
    shutil.copy2(sensitivity_map_src, dirs["prov"] / "final_sensitivity_publication_source_map.json")

    cc_meta = extract_constraint_count_intervals(
        repo, dirs["data"] / "sensitivity_constraint_count_stage20_intervals.csv"
    )

    cc_archive = repo / cc_meta["archive"]
    cc_obs_member = extract_single_archive_member(
        cc_archive,
        "planning/aggregates/constraint_count_nv24_stage20/formal_timing/formal_timing_observations.csv",
        dirs["data"] / "sensitivity_constraint_count_stage20_observations.csv",
    )

    vn_decision_src = repo / sensitivity_map["sources"]["virtual_node_count"]["decision"]["path"]
    md_decision_src = repo / sensitivity_map["sources"]["membership_density"]["decision"]["path"]
    oc_intervals_src = repo / sensitivity_map["sources"]["objective_count"]["intervals"]["path"]
    oc_verdict_src = repo / sensitivity_map["sources"]["objective_count"]["verdict"]["path"]
    for src, dst in [
        (vn_decision_src, dirs["data"] / "sensitivity_virtual_node_count_stage10_decision.json"),
        (md_decision_src, dirs["data"] / "sensitivity_membership_density_stage10_decision.json"),
        (oc_intervals_src, dirs["data"] / "sensitivity_objective_count_stage30_intervals.csv"),
        (oc_verdict_src, dirs["data"] / "sensitivity_objective_count_stage30_verdict.json"),
    ]:
        if not src.is_file():
            raise RuntimeError(f"missing canonical sensitivity source: {src}")
        dst.write_bytes(normalize_text_bytes(src.read_bytes()))

    vn_decision = json.loads(vn_decision_src.read_text(encoding="utf-8"))
    vn_intervals_src = repo / vn_decision["analysis"]["intervals_csv_path"]
    (dirs["data"] / "sensitivity_virtual_node_count_stage10_intervals.csv").write_bytes(
        normalize_text_bytes(vn_intervals_src.read_bytes())
    )

    md_decision = json.loads(md_decision_src.read_text(encoding="utf-8"))
    md_rows = md_decision["cell_results"]
    write_csv(
        dirs["data"] / "sensitivity_membership_density_stage10_precision_cells.csv",
        [
            "factor", "factor_level", "step_index",
            "median_relative_half_width", "p95_relative_half_width",
            "median_relative_half_width_target", "p95_relative_half_width_target",
            "median_target_met", "p95_target_met", "all_cell_targets_met"
        ],
        md_rows,
    )

    # Publication-side descriptive performance characterization.
    # No experiment, timing run, bootstrap or backend execution is performed here.
    cc_obs_path = dirs["data"] / "sensitivity_constraint_count_stage20_observations.csv"
    vn_obs_path = repo / vn_decision["analysis"]["observations_path"]
    md_obs_path = repo / md_decision["source_artifacts"]["observations"]["path"]

    perf_rows = []
    perf_rows += summarize_latency_quantiles(
        "constraint_count",
        read_latency_rows(cc_obs_path),
        cc_meta["archive"] + "::" + cc_obs_member,
    )
    perf_rows += summarize_latency_quantiles(
        "virtual_node_count",
        read_latency_rows(vn_obs_path),
        vn_decision["analysis"]["observations_path"],
    )
    perf_rows += summarize_latency_quantiles(
        "membership_density",
        read_latency_rows(md_obs_path),
        md_decision["source_artifacts"]["observations"]["path"],
    )

    write_csv(
        dirs["data"] / "semantic_latency_quantiles_p50_p95_p99.csv",
        [
            "factor", "factor_level", "observation_count",
            "p50_ms", "p95_ms", "p99_ms",
            "p95_over_p50", "p99_over_p50",
            "source", "interpretation",
        ],
        perf_rows,
    )

    figmap = []

    def register(fid, filename, title, source, placement, authority):
        figmap.append({
            "figure_id": fid,
            "file": f"figures/{filename}",
            "title": title,
            "source": source,
            "placement": placement,
            "authority": authority,
        })

    f = dirs["fig"] / "F01_conceptual_chain.tex"
    f.write_text(r'''\begin{tikzpicture}[
node distance=5mm and 6mm,
every node/.style={font=\scriptsize,align=center},
box/.style={draw,rounded corners=1mm,minimum width=17mm,minimum height=8mm,inner sep=2pt},
>=Stealth
]
\node[box] (q) {Requête\\analytique};
\node[box,right=of q] (qp) {$QP$\\canonique};
\node[box,right=of qp] (sat) {$\mathrm{SAT}$\\admissibilité};
\node[box,right=of sat] (real) {$\mathrm{Real}$\\évidence};
\node[box,right=of real] (ceval) {$C_{\mathrm{eval}}$\\calculabilité};
\node[box,right=of ceval] (dphi) {$\Delta\varphi_t$\\gain};
\node[box,below=of dphi] (gate) {ALLOW / BLOCK\\gate physique};
\node[box,below=of real] (ckg) {CKG + objectif\\contraintes / NV};
\draw[->] (q)--(qp);
\draw[->] (qp)--(sat);
\draw[->] (sat)--(real);
\draw[->] (real)--(ceval);
\draw[->] (ceval)--(dphi);
\draw[->] (dphi)--(gate);
\draw[->] (ckg)--(sat);
\draw[->] (ckg)--(real);
\draw[->] (ckg)--(ceval);
\end{tikzpicture}
''', encoding="utf-8")
    register("F01", f.name, "Chaîne conceptuelle MCAD", "formal manuscript + prototype contract", "MAIN", "CONCEPTUAL")

    f = dirs["fig"] / "F02_architecture_mcad.tex"
    f.write_text(r'''\begin{tikzpicture}[
node distance=6mm,
every node/.style={font=\scriptsize,align=center},
box/.style={draw,rounded corners=1mm,minimum width=35mm,minimum height=9mm,inner sep=3pt},
>=Stealth
]
\node[box] (ui) {Analyste / interface BI\\objectifs, requêtes, résultats};
\node[box,below=of ui] (mcad) {Couche MCAD\\QP $\rightarrow$ SAT $\rightarrow$ Real $\rightarrow$ $C_{\mathrm{eval}}$ $\rightarrow$ $\Delta\varphi$};
\node[box,below left=8mm and 12mm of mcad] (backend) {Backends analytiques\\SQL Direct / XMLA--Mondrian};
\node[box,below right=8mm and 12mm of mcad] (ckg) {CKG + objectifs\\contraintes, NV, évidence};
\node[box,below=of mcad] (audit) {Contrat de décision + audit\\provenance / replay};
\draw[->] (ui)--node[right]{requête}(mcad);
\draw[->] (mcad)--node[left]{ALLOW}(backend);
\draw[->] (backend)--node[below left]{résultats}(mcad);
\draw[<->] (mcad)--(ckg);
\draw[->] (mcad)--(audit);
\draw[->] (mcad)--node[right]{décision + explication}(ui);
\end{tikzpicture}
''', encoding="utf-8")
    register("F02", f.name, "Architecture du prototype MCAD", "prototype architecture + physical campaigns", "MAIN", "SYSTEM")

    f = dirs["fig"] / "F03_experimental_evidence_chain.tex"
    f.write_text(r'''\begin{tikzpicture}[
node distance=4mm and 4mm,
every node/.style={font=\scriptsize,align=center},
box/.style={draw,rounded corners=1mm,minimum width=21mm,minimum height=9mm,inner sep=2pt},
>=Stealth
]
\node[box] (q) {Q1--Q6\\trace E2E};
\node[box,right=of q] (abc) {A/B/C\\preuve physique};
\node[box,right=of abc] (rob) {Robustesse\\+ ablations};
\node[box,right=of rob] (sc) {Scalabilité\\structurelle};
\node[box,below=of abc] (ev) {Evidence\\usefulness};
\node[box,below=of rob] (sens) {Sensibilités\\4 facteurs};
\node[box,below=of sc] (pub) {Publication\\claims bornés};
\draw[->] (q)--(abc);
\draw[->] (abc)--(rob);
\draw[->] (rob)--(sc);
\draw[->] (abc)--(ev);
\draw[->] (rob)--(sens);
\draw[->] (sc)--(pub);
\draw[->] (ev)--(pub);
\draw[->] (sens)--(pub);
\end{tikzpicture}
''', encoding="utf-8")
    register("F03", f.name, "Chaîne de preuve expérimentale", "FINAL_PUBLICATION_ADOPTION", "MAIN", "PROVENANCE")

    _, qrows = read_csv(dirs["data"] / "q1_q6_canonical_trace.csv")
    qrows = sorted(qrows, key=lambda r: int(r["step"]))
    xs = [int(r["step"]) for r in qrows]
    phis = [float(r["phi_leq_t"]) for r in qrows]
    pgf_line(
        dirs["fig"] / "F04_q1_q6_coverage.tex",
        "Trace canonique Q1--Q6 : couverture cumulative",
        "Étape", r"$\varphi^{\leq t}(O)$",
        [("couverture", xs, phis)],
        xticks=xs, xticklabels=[f"Q{x}" for x in xs], ymin=0, ymax=1.05, legend_columns=1
    )
    register("F04", "F04_q1_q6_coverage.tex", "Couverture cumulative Q1–Q6", "data/q1_q6_canonical_trace.csv", "MAIN", "PRIMARY_PHYSICAL")

    decisions = [1 if r["decision"] == "ALLOW" else 0 for r in qrows]
    physical = [1 if boolish(r.get("physical_execution")) else 0 for r in qrows]
    pgf_grouped_bar(
        dirs["fig"] / "F05_q1_q6_gate_execution.tex",
        "Q1--Q6 : décision et exécution physique",
        "Indicateur binaire",
        [f"Q{x}" for x in xs],
        [("ALLOW", decisions), ("exécution physique", physical)],
        ymax=1.15,
    )
    register("F05", "F05_q1_q6_gate_execution.tex", "ALLOW/BLOCK et exécution Q1–Q6", "data/q1_q6_canonical_trace.csv", "MAIN", "PRIMARY_PHYSICAL")

    a = json.loads((dirs["data"] / "campaign_a_1000_summary.json").read_text(encoding="utf-8"))
    pgf_grouped_bar(
        dirs["fig"] / "F06_campaign_a_decisions.tex",
        "Campagne A : décisions sur 1000 sessions",
        "Nombre de décisions",
        ["Campagne A"],
        [("ALLOW", [a["allow_count"]]), ("BLOCK", [a["block_count"]])],
    )
    register("F06", "F06_campaign_a_decisions.tex", "Campagne A ALLOW/BLOCK", "data/campaign_a_1000_summary.json", "MAIN", "PRIMARY_PHYSICAL")

    reasons = sorted(a["decision_reason_counts"].items(), key=lambda kv: kv[1])
    pgf_xbar(
        dirs["fig"] / "F07_campaign_a_reasons.tex",
        "Campagne A : distribution des codes de décision",
        "Occurrences",
        [tex_escape(k) for k, _ in reasons],
        [v for _, v in reasons],
    )
    register("F07", "F07_campaign_a_reasons.tex", "Campagne A codes de décision", "data/campaign_a_1000_summary.json", "SUPPLEMENT", "PRIMARY_PHYSICAL")

    _, brows = read_csv(dirs["data"] / "campaign_b_summary.csv")
    b_groups = {}
    for r in brows:
        sid = r.get("scenario_id", "")
        if "foodmart" in sid.lower():
            name = "FoodMart"
        elif "adventureworks" in sid.lower():
            name = "AdventureWorks"
        elif "steelwheels" in sid.lower():
            name = "SteelWheels"
        else:
            name = sid[:18]
        g = b_groups.setdefault(name, {"allow": 0, "block": 0, "physical": 0})
        if r.get("decision") == "ALLOW":
            g["allow"] += 1
        else:
            g["block"] += 1
        if boolish(r.get("physical_execution")):
            g["physical"] += 1
    blabels = list(b_groups.keys())
    pgf_grouped_bar(
        dirs["fig"] / "F08_campaign_b_multidataset.tex",
        "Campagne B : transfert multi-dataset",
        "Nombre de requêtes",
        blabels,
        [
            ("ALLOW", [b_groups[x]["allow"] for x in blabels]),
            ("BLOCK", [b_groups[x]["block"] for x in blabels]),
            ("physiques", [b_groups[x]["physical"] for x in blabels]),
        ],
        legend_columns=3,
    )
    register("F08", "F08_campaign_b_multidataset.tex", "Campagne B multi-dataset", "data/campaign_b_summary.csv", "MAIN", "PRIMARY_PHYSICAL")

    _, crows = read_csv(dirs["data"] / "campaign_c_summary.csv")
    c_groups = {}
    for r in crows:
        name = "SQL Direct" if r.get("backend") == "sql_direct" else "XMLA"
        g = c_groups.setdefault(name, {"allow": 0, "block": 0, "physical": 0})
        if r.get("decision") == "ALLOW":
            g["allow"] += 1
        else:
            g["block"] += 1
        if boolish(r.get("physical_execution")):
            g["physical"] += 1
    clabels = ["SQL Direct", "XMLA"]
    pgf_grouped_bar(
        dirs["fig"] / "F09_campaign_c_backend_parity.tex",
        "Campagne C : parité backend appariée",
        "Nombre d'évaluations",
        clabels,
        [
            ("ALLOW", [c_groups[x]["allow"] for x in clabels]),
            ("BLOCK", [c_groups[x]["block"] for x in clabels]),
            ("physiques", [c_groups[x]["physical"] for x in clabels]),
        ],
        legend_columns=3,
    )
    register("F09", "F09_campaign_c_backend_parity.tex", "Campagne C portabilité backend", "data/campaign_c_summary.csv", "MAIN", "PRIMARY_PHYSICAL")

    _, rrows = read_csv(dirs["data"] / "robustness_by_scenario_type.csv")
    scenario_order = ["adversarial_sat", "adversarial_semantic", "noisy_borderline", "stress_long"]
    rseries = []
    for pol, label in [
        ("mcad", "MCAD"),
        ("baseline_naive", "naive"),
        ("baseline_measure_overlap", "measure overlap"),
        ("baseline_random_matched", "random matched"),
    ]:
        m = {r["scenario_type"]: float(r["mean_false_allow_rate"]) for r in rrows if r["policy"] == pol}
        rseries.append((label, list(range(4)), [m[x] for x in scenario_order]))
    pgf_line(
        dirs["fig"] / "F10_robustness_false_allow.tex",
        "Robustesse : false ALLOW",
        "Famille de scénarios", "Taux de false ALLOW",
        rseries,
        xticks=list(range(4)),
        xticklabels=[x.replace("_", r"\_") for x in scenario_order],
        ymin=0, ymax=1.0, legend_columns=2,
    )
    register("F10", "F10_robustness_false_allow.tex", "False ALLOW du freeze de robustesse", "data/robustness_by_scenario_type.csv", "MAIN", "FROZEN_PRIMARY_NON_TEMPORAL")

    _, exrows = read_csv(dirs["data"] / "robustness_explainability_summary.csv")
    pgf_grouped_bar(
        dirs["fig"] / "F11_robustness_explainability.tex",
        "Explicabilité système des BLOCK",
        "Taux de BLOCK explicables",
        [r["scenario_type"].replace("_", r"\_") for r in exrows],
        [("MCAD", [float(r["explainable_block_rate"]) for r in exrows])],
        ymax=1.08, legend_columns=1,
    )
    register("F11", "F11_robustness_explainability.tex", "Explicabilité système", "data/robustness_explainability_summary.csv", "MAIN", "FROZEN_PRIMARY_NON_TEMPORAL")

    _, srows = read_csv(dirs["data"] / "scalability_catalog_structural.csv")
    srows = sorted(srows, key=lambda r: int(r["scale_factor"]))
    sx = [int(r["scale_factor"]) for r in srows]
    pgf_line(
        dirs["fig"] / "F12_scalability_structural.tex",
        "Scalabilité structurelle du CKG",
        "Facteur d'échelle", "Taille structurelle",
        [
            ("nœuds", sx, [int(r["n_nodes"]) for r in srows]),
            ("arêtes", sx, [int(r["n_edges"]) for r in srows]),
            ("nœuds virtuels", sx, [int(r["n_virtual_nodes"]) for r in srows]),
        ],
        xticks=sx, ymin=0, legend_columns=3,
    )
    register("F12", "F12_scalability_structural.tex", "Croissance structurelle du CKG", "data/scalability_catalog_structural.csv", "MAIN", "STRUCTURAL_ONLY")

    evboot = json.loads((dirs["data"] / "evidence_bootstrap_secondary.json").read_text(encoding="utf-8"))
    objs = sorted({r["objective_id"] for r in evboot})
    vals_no = {r["objective_id"]: r for r in evboot if r["mode"] == "no_bootstrap"}
    vals_bo = {r["objective_id"]: r for r in evboot if r["mode"] == "bootstrap"}
    pgf_grouped_bar(
        dirs["fig"] / "F13_evidence_steps_to_full.tex",
        "Evidence reuse : étapes vers couverture complète",
        "Étapes",
        [x.replace("_", r"\_") for x in objs],
        [
            ("sans bootstrap", [vals_no[x]["steps_to_full"] for x in objs]),
            ("avec évidence", [vals_bo[x]["steps_to_full"] for x in objs]),
        ],
    )
    register("F13", "F13_evidence_steps_to_full.tex", "Réutilisation d'évidence : étapes vers couverture", "data/evidence_bootstrap_secondary.json", "MAIN", "QUALIFIED_SECONDARY")

    pgf_grouped_bar(
        dirs["fig"] / "F14_evidence_auc.tex",
        "Evidence reuse : AUC de couverture",
        "AUC",
        [x.replace("_", r"\_") for x in objs],
        [
            ("sans bootstrap", [vals_no[x]["auc_phi"] for x in objs]),
            ("avec évidence", [vals_bo[x]["auc_phi"] for x in objs]),
        ],
        ymax=1.08,
    )
    register("F14", "F14_evidence_auc.tex", "Réutilisation d'évidence : AUC", "data/evidence_bootstrap_secondary.json", "SUPPLEMENT", "QUALIFIED_SECONDARY")

    _, ccrows = read_csv(dirs["data"] / "sensitivity_constraint_count_stage20_intervals.csv")
    _, vnrows = read_csv(dirs["data"] / "sensitivity_virtual_node_count_stage10_intervals.csv")
    _, ocrows = read_csv(dirs["data"] / "sensitivity_objective_count_stage30_intervals.csv")

    def precision_lines(rows, filename, title, source_name):
        steps = sorted({int(r["step_index"]) for r in rows})
        series = []
        for step in steps:
            rr = sorted(
                [r for r in rows if int(r["step_index"]) == step],
                key=lambda r: float(r["factor_level"])
            )
            series.append(
                (f"étape {step}",
                 [float(r["factor_level"]) for r in rr],
                 [float(r["p95_relative_half_width"]) for r in rr])
            )
        pgf_line(
            dirs["fig"] / filename,
            title,
            "Niveau du facteur", "Demi-largeur relative IC p95",
            series,
            ymin=0,
            legend_columns=min(4, max(1, len(series))),
        )
        register(filename.split("_")[0], filename, title, f"data/{source_name}", "SUPPLEMENT", "PRECISION_DIAGNOSTIC_ONLY")

    precision_lines(
        ccrows, "F15_sensitivity_constraint_precision.tex",
        "Sensibilité constraint count : précision Stage-20",
        "sensitivity_constraint_count_stage20_intervals.csv"
    )
    precision_lines(
        vnrows, "F16_sensitivity_virtual_node_precision.tex",
        "Sensibilité virtual-node count : précision Stage-10",
        "sensitivity_virtual_node_count_stage10_intervals.csv"
    )

    pgf_line(
        dirs["fig"] / "F17_sensitivity_membership_density_precision.tex",
        "Sensibilité membership density : précision Stage-10",
        "Densité (%)", "Demi-largeur relative IC",
        [
            ("médiane", [float(r["factor_level"]) for r in md_rows], [float(r["median_relative_half_width"]) for r in md_rows]),
            ("p95", [float(r["factor_level"]) for r in md_rows], [float(r["p95_relative_half_width"]) for r in md_rows]),
        ],
        xticks=[25, 50, 75, 100], ymin=0,
    )
    register("F17", "F17_sensitivity_membership_density_precision.tex", "Membership density : précision", "data/sensitivity_membership_density_stage10_precision_cells.csv", "SUPPLEMENT", "PRECISION_DIAGNOSTIC_ONLY")

    pass_coords, fail_coords = [], []
    for r in ocrows:
        coord = (float(r["factor_level"]), int(r["step_index"]))
        (pass_coords if boolish(r["all_cell_targets_met"]) else fail_coords).append(coord)
    lines = [
        r"\begin{tikzpicture}",
        r"\begin{axis}[",
        r"width=\linewidth,height=0.66\linewidth,",
        r"title={Objective count Stage-30 : carte des 192 cellules de précision},",
        r"xlabel={Nombre d'objectifs},ylabel={Étape},grid=major,",
        r"legend style={font=\scriptsize,at={(0.5,-0.20)},anchor=north,legend columns=2}",
        r"]",
    ]
    if pass_coords:
        lines.append(r"\addplot+[only marks,mark=square*,mark size=2.3pt] coordinates {" +
                     " ".join(f"({x},{y})" for x, y in pass_coords) + "};")
        lines.append(r"\addlegendentry{cible atteinte}")
    if fail_coords:
        lines.append(r"\addplot+[only marks,mark=x,mark size=3pt] coordinates {" +
                     " ".join(f"({x},{y})" for x, y in fail_coords) + "};")
        lines.append(r"\addlegendentry{hors cible}")
    lines += [r"\end{axis}", r"\end{tikzpicture}", ""]
    (dirs["fig"] / "F18_objective_count_precision_cell_map.tex").write_text("\n".join(lines), encoding="utf-8")
    register("F18", "F18_objective_count_precision_cell_map.tex", "Objective count Stage-30 : 17/192 cellules hors cible", "data/sensitivity_objective_count_stage30_intervals.csv", "MAIN", "TERMINAL_PRECISION_LIMIT")

    def fail_count(rows):
        return sum(1 for r in rows if not boolish(r["all_cell_targets_met"])), len(rows)

    cc_fail, cc_total = fail_count(ccrows)
    vn_fail = int(vn_decision["failing_cell_count"])
    vn_total = int(vn_decision["precision_cell_count"])
    md_fail = int(md_decision["precision_decision"]["failing_cell_count"])
    md_total = int(md_decision["analysis_contract"]["inferential_cell_count"])
    oc_fail, oc_total = fail_count(ocrows)
    if oc_fail != 17 or oc_total != 192:
        raise RuntimeError(f"objective_count final cell gate mismatch: {oc_fail}/{oc_total}")

    pgf_grouped_bar(
        dirs["fig"] / "F19_sensitivity_failure_rates.tex",
        "Synthèse des cibles de précision",
        "Part de cellules hors cible",
        ["contraintes", "NV", "densité", "objectifs"],
        [("hors cible", [
            cc_fail / cc_total if cc_total else 0,
            vn_fail / vn_total,
            md_fail / md_total,
            oc_fail / oc_total,
        ])],
        ymax=1.0, legend_columns=1,
    )
    register("F19", "F19_sensitivity_failure_rates.tex", "Synthèse précision des quatre sensibilités", "four canonical sensitivity sources", "MAIN", "FINAL_SENSITIVITY_SOURCE_MAP")

    f = dirs["fig"] / "F20_provenance_pipeline.tex"
    f.write_text(r'''\begin{tikzpicture}[
node distance=4mm,
every node/.style={font=\scriptsize,align=center},
box/.style={draw,rounded corners=1mm,minimum width=18mm,minimum height=8mm,inner sep=2pt},
>=Stealth
]
\node[box] (a) {Audit};
\node[box,right=of a] (v) {Validation};
\node[box,right=of v] (f) {Freeze};
\node[box,right=of f] (ar) {Archive};
\node[box,right=of ar] (p) {Publication};
\draw[->] (a)--(v);
\draw[->] (v)--(f);
\draw[->] (f)--(ar);
\draw[->] (ar)--(p);
\node[below=5mm of f,font=\scriptsize,align=center] {manifeste + provenance + SHA-256\\source-map + claim-evidence map};
\end{tikzpicture}
''', encoding="utf-8")
    register("F20", f.name, "Pipeline de provenance", "campaign manifests + adoption + source map", "SUPPLEMENT", "PROVENANCE")

    # F21-F23: descriptive semantic-latency quantiles, inspired by legacy
    # manuscript performance visual grammar but recomputed from final canonical evidence.
    _, latency_rows = read_csv(dirs["data"] / "semantic_latency_quantiles_p50_p95_p99.csv")
    perf_specs = [
        ("constraint_count", "F21_latency_constraint_count.tex", "Latence sémantique — nombre de contraintes"),
        ("virtual_node_count", "F22_latency_virtual_node_count.tex", "Latence sémantique — nœuds virtuels"),
        ("membership_density", "F23_latency_membership_density.tex", "Latence sémantique — densité d'appartenance"),
    ]
    for factor, filename, title in perf_specs:
        rr = sorted(
            [r for r in latency_rows if r["factor"] == factor],
            key=lambda r: float(r["factor_level"])
        )
        xx = [float(r["factor_level"]) for r in rr]
        pgf_line(
            dirs["fig"] / filename,
            title,
            "Niveau du facteur", "Latence (ms)",
            [
                ("p50", xx, [float(r["p50_ms"]) for r in rr]),
                ("p95", xx, [float(r["p95_ms"]) for r in rr]),
                ("p99", xx, [float(r["p99_ms"]) for r in rr]),
            ],
            xticks=xx,
            ymin=0,
            legend_columns=3,
        )
        fid = filename.split("_")[0]
        register(
            fid, filename, title,
            "data/semantic_latency_quantiles_p50_p95_p99.csv",
            "MAIN",
            "DESCRIPTIVE_EXISTING_CANONICAL_MEASUREMENTS",
        )

    write_csv(
        dirs["visprov"] / "figure_source_map_v4.csv",
        ["figure_id", "file", "title", "source", "placement", "authority"],
        figmap,
    )
    (dirs["visprov"] / "FIGURE_PLAN_V4.json").write_text(
        json.dumps({"figure_count": len(figmap), "figures": figmap}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    p9_rows = [
        {"id":"CIT01","severity":"HIGH","location":"Abstract, novelty sentence","issue":"Absolute novelty statement.","action":"Use bounded literature-review conclusion and tie to Section II."},
        {"id":"CIT02","severity":"MEDIUM","location":"Section II positioning table","issue":"Categorical Non may imply exhaustive absence.","action":"Use non central / non ciblé / partiel where appropriate."},
        {"id":"CIT03","severity":"HIGH","location":"Section II XAI paragraph","issue":"Kostopoulos metadata incorrect in earlier V2.","action":"Correct authors and journal metadata."},
        {"id":"CIT04","severity":"HIGH","location":"Section II KG-OLAP paragraph","issue":"Schuetz KG-OLAP authors/issue/pages incorrect.","action":"Use verified 2021 Semantic Web metadata."},
        {"id":"CIT05","severity":"HIGH","location":"Section II descriptive analytics KG paragraph","issue":"Staudinger metadata incomplete/incorrect.","action":"Include Thomas Neuböck, DECISION 52(3), 285-306, DOI."},
        {"id":"CIT06","severity":"MEDIUM","location":"Section IV CKG relations","issue":"Generic sources were attached to MCAD-specific relation names.","action":"Separate literature motivation from MCAD vocabulary."},
        {"id":"CIT07","severity":"MEDIUM","location":"Query-language portability","issue":"Conceptual canonicalization conflated with implemented extraction support.","action":"Keep principle in IV, implementation in V, empirical scope in VII."},
    ]
    write_csv(
        dirs["bibprov"] / "P9_CLAIM_CITATION_AUDIT_v4.csv",
        ["id", "severity", "location", "issue", "action"],
        p9_rows,
    )

    ref_rows = [
        {
            "key":"KostopoulosXAIDSS2024",
            "status":"VERIFIED_PRIMARY",
            "correct_metadata":"Georgios Kostopoulos; Gregory Davrazos; Sotiris Kotsiantis. Electronics 13(14), 2842 (2024). DOI 10.3390/electronics13142842.",
            "verification_source":"MDPI / version of record",
            "verification_locator":"https://doi.org/10.3390/electronics13142842",
        },
        {
            "key":"SchuetzSerafiniBozzato2021",
            "status":"VERIFIED_PRIMARY",
            "correct_metadata":"Christoph G. Schuetz; Loris Bozzato; Bernd Neumayr; Michael Schrefl; Luciano Serafini. Semantic Web 12(4), 649-683 (2021). DOI 10.3233/SW-200419.",
            "verification_source":"JKU research portal / publisher DOI",
            "verification_locator":"https://doi.org/10.3233/SW-200419",
        },
        {
            "key":"StaudingerSchuetzSchrefl2025",
            "status":"VERIFIED_PRIMARY",
            "correct_metadata":"Simon Staudinger; Christoph G. Schuetz; Michael Schrefl; Thomas Neuböck. DECISION 52(3), 285-306 (2025). DOI 10.1007/s40622-025-00432-4.",
            "verification_source":"Springer Nature / version of record",
            "verification_locator":"https://doi.org/10.1007/s40622-025-00432-4",
        },
        {
            "key":"W3CSHACL2017",
            "status":"KEY_AND_STANDARD_DATE_NORMALIZED",
            "correct_metadata":"W3C, Shapes Constraint Language (SHACL), W3C Recommendation, 20 July 2017.",
            "verification_source":"W3C",
            "verification_locator":"https://www.w3.org/TR/shacl/",
        },
        {
            "key":"W3CPROVO2013",
            "status":"KEY_AND_STANDARD_DATE_NORMALIZED",
            "correct_metadata":"W3C, PROV-O: The PROV Ontology, W3C Recommendation, 30 April 2013.",
            "verification_source":"W3C",
            "verification_locator":"https://www.w3.org/TR/prov-o/",
        },
        {
            "key":"FarihaMeliou2019",
            "status":"KEY_PROPAGATION_FROM_PRIOR_VERIFIED_PACKAGE",
            "correct_metadata":"A. Fariha and A. Meliou, Example-driven query intent discovery: abductive reasoning using semantic similarity, PVLDB 12(11), 1262-1275 (2019).",
            "verification_source":"prior P9/P10 bibliography package",
            "verification_locator":"repository/library prior qualification",
        },
    ]
    write_csv(
        dirs["bibprov"] / "REFERENCE_CORRECTIONS_V4.csv",
        ["key", "status", "correct_metadata", "verification_source", "verification_locator"],
        ref_rows,
    )

    manuscript = v3_main.read_text(encoding="utf-8")
    manuscript, propagation_changes = patch_bibliography_and_claims(manuscript)

    manuscript = replace_once(
        manuscript,
        r"\input{article_update/paper_artifacts_final/sections/section_experimentale_finale_v3.tex}",
        r"\input{article_update/paper_artifacts_v4/sections/section_experimentale_finale_v4.tex}",
        "V4 experimental section input"
    )

    concept_repl = r'''\begin{figure*}[!t]
\centering
\resizebox{\textwidth}{!}{\input{article_update/paper_artifacts_v4/figures/F01_conceptual_chain.tex}}
\caption{Chaîne conceptuelle centrale de MCAD, de la requête à la décision et à la calculabilité stratégique.}
\label{fig:concept-chain}
\end{figure*}'''
    manuscript = replace_regex_once(
        manuscript,
        r"\\begin\{figure\}\[!t\].*?\\label\{fig:concept-chain\}\s*\\end\{figure\}",
        lambda m: concept_repl,
        "concept figure externalization"
    )

    arch_repl = r'''\begin{figure*}[!t]
\centering
\resizebox{\textwidth}{!}{\input{article_update/paper_artifacts_v4/figures/F02_architecture_mcad.tex}}
\caption{Architecture du prototype MCAD et séparation entre décision sémantique, exécution physique, CKG et audit.}
\label{fig:arch-mcad}
\end{figure*}'''
    manuscript = replace_regex_once(
        manuscript,
        r"\\begin\{figure\*\}\[!t\](?:(?!\\end\{figure\*\}).)*?\\label\{fig:arch-mcad\}\s*\\end\{figure\*\}",
        lambda m: arch_repl,
        "architecture figure externalization"
    )

    sec = v3_sec.read_text(encoding="utf-8")
    after_classes = "\\subsection{Trace canonique Q1--Q6}"
    evidence_fig = r'''\begin{figure*}[!t]
\centering
\resizebox{0.96\textwidth}{!}{\input{article_update/paper_artifacts_v4/figures/F03_experimental_evidence_chain.tex}}
\caption{Organisation de la chaîne de preuve expérimentale finale. Les différents blocs répondent à des questions distinctes et ne sont pas comptés comme des réplications indépendantes.}
\label{fig:v4-evidence-chain}
\end{figure*}

'''
    sec = replace_once(sec, after_classes, evidence_fig + after_classes, "experimental evidence chain injection")

    q_anchor = "Au total, la trace contient trois ALLOW et trois BLOCK,\navec trois exécutions physiques et trois arrêts avant backend."
    q_figs = r'''

\begin{figure*}[!t]
\centering
\begin{minipage}[t]{0.49\textwidth}
\centering
\input{article_update/paper_artifacts_v4/figures/F04_q1_q6_coverage.tex}
\end{minipage}\hfill
\begin{minipage}[t]{0.49\textwidth}
\centering
\input{article_update/paper_artifacts_v4/figures/F05_q1_q6_gate_execution.tex}
\end{minipage}
\caption{Trace canonique Q1--Q6 : (gauche) progression cumulative de la calculabilité stratégique; (droite) distinction entre décision ALLOW et exécution physique.}
\label{fig:v4-q1-q6}
\end{figure*}
'''
    sec = replace_once(sec, q_anchor, q_anchor + q_figs, "Q1-Q6 visual injection")

    a_anchor = "Aucune violation du contrat d'exécution physique n'a été\nobservée dans ce périmètre."
    a_fig = r'''

\begin{figure}[!t]
\centering
\input{article_update/paper_artifacts_v4/figures/F06_campaign_a_decisions.tex}
\caption{Campagne A : profondeur expérimentale sur 1000 sessions, avec séparation ALLOW/BLOCK.}
\label{fig:v4-campaign-a}
\end{figure}
'''
    sec = replace_once(sec, a_anchor, a_anchor + a_fig, "Campaign A visual injection")

    c_anchor = (
        "Cette observation soutient la préservation du contrat de\n"
        "décision sur ce scénario contrôlé; elle ne constitue ni une preuve\n"
        "d'invariance globale entre backends ni une comparaison de leurs\n"
        "performances."
    )
    bc_fig = r'''

\begin{figure*}[!t]
\centering
\begin{minipage}[t]{0.49\textwidth}
\centering
\input{article_update/paper_artifacts_v4/figures/F08_campaign_b_multidataset.tex}
\end{minipage}\hfill
\begin{minipage}[t]{0.49\textwidth}
\centering
\input{article_update/paper_artifacts_v4/figures/F09_campaign_c_backend_parity.tex}
\end{minipage}
\caption{Validation physique complémentaire : (gauche) Campagne B multi-dataset; (droite) Campagne C backend appariée.}
\label{fig:v4-campaign-bc}
\end{figure*}
'''
    sec = replace_once(sec, c_anchor, c_anchor + bc_fig, "Campaign B/C visual injection")

    sec = sec.replace(
        r"\input{article_update/paper_artifacts_final/figures/F_v3_robustness_false_allow.tex}",
        r"\input{article_update/paper_artifacts_v4/figures/F10_robustness_false_allow.tex}"
    )
    sec = sec.replace(
        r"\input{article_update/paper_artifacts_final/figures/F_v3_robustness_explainability.tex}",
        r"\input{article_update/paper_artifacts_v4/figures/F11_robustness_explainability.tex}"
    )
    sec = sec.replace(
        r"\input{article_update/paper_artifacts_final/figures/F_v3_scalability_structure.tex}",
        r"\input{article_update/paper_artifacts_v4/figures/F12_scalability_structural.tex}"
    )

    ev_anchor = r"\input{article_update/paper_artifacts_final/tables/T_v3_secondary_evidence.tex}"
    ev_fig = r'''

\begin{figure}[!t]
\centering
\input{article_update/paper_artifacts_v4/figures/F13_evidence_steps_to_full.tex}
\caption{Réutilisation contrôlée de l'évidence : nombre d'étapes nécessaires pour retrouver une couverture complète avec et sans amorçage par l'évidence persistée.}
\label{fig:v4-evidence-steps}
\end{figure}
'''
    sec = replace_once(sec, ev_anchor, ev_anchor + ev_fig, "Evidence usefulness visual injection")

    sens_anchor = (
        "Aucune réplication supplémentaire, aucun nouveau bootstrap et aucun\n"
        "Stage-40 ne sont autorisés."
    )
    sens_figs = r'''

\begin{figure*}[!t]
\centering
\begin{minipage}[t]{0.49\textwidth}
\centering
\input{article_update/paper_artifacts_v4/figures/F18_objective_count_precision_cell_map.tex}
\end{minipage}\hfill
\begin{minipage}[t]{0.49\textwidth}
\centering
\input{article_update/paper_artifacts_v4/figures/F19_sensitivity_failure_rates.tex}
\end{minipage}
\caption{Sensibilité et précision : (gauche) carte des 192 cellules du Stage-30 \texttt{objective\_count}, dont 17 hors cible; (droite) synthèse descriptive des cellules hors cibles pour les quatre facteurs canoniques.}
\label{fig:v4-sensitivity-terminal}
\end{figure*}
'''
    sec = replace_once(sec, sens_anchor, sens_anchor + sens_figs, "Sensitivity visual injection")
    performance_subsection = r"""

\subsection{Caractérisation des performances de la couche sémantique}

Les versions antérieures du manuscrit utilisaient déjà les quantiles
p50/p95/p99 comme lecture de la latence. Nous conservons cette structure
d'évaluation, mais pas leurs anciennes valeurs numériques : les résultats
V-1/V0/V1/V2 servent ici de précédent méthodologique et visuel, tandis que
les quantiles ci-dessous sont recalculés uniquement à partir des observations
canoniques déjà matérialisées et retenues dans le dépôt.

Le p50 décrit le comportement typique, alors que p95 et p99 rendent visible
la queue de distribution, essentielle pour un composant interactif
\cite{DeanBarroso2013}. Conformément aux bonnes pratiques de benchmarking,
les quantiles sont accompagnés du volume d'observations et rattachés à leur
source exacte plutôt qu'à une moyenne isolée \cite{KaliberaJones2013}.

La caractérisation porte sur trois facteurs pour lesquels des observations
canoniques existantes sont disponibles : nombre de contraintes, nombre de
nœuds virtuels et densité d'appartenance. Elle ne déclenche aucune nouvelle
exécution et aucun nouveau bootstrap. Le p99 est une statistique descriptive
calculée déterministement depuis les mesures existantes; aucune précision
inférentielle spécifique au p99 n'est revendiquée. Les facteurs d'amplification
p95/p50 et p99/p50 sont également matérialisés dans les données de publication.

\input{article_update/paper_artifacts_v4/tables/T_v4_semantic_latency_quantiles.tex}

\begin{figure*}[!t]
\centering
\begin{minipage}[t]{0.32\textwidth}
\centering
\input{article_update/paper_artifacts_v4/figures/F21_latency_constraint_count.tex}
\end{minipage}\hfill
\begin{minipage}[t]{0.32\textwidth}
\centering
\input{article_update/paper_artifacts_v4/figures/F22_latency_virtual_node_count.tex}
\end{minipage}\hfill
\begin{minipage}[t]{0.32\textwidth}
\centering
\input{article_update/paper_artifacts_v4/figures/F23_latency_membership_density.tex}
\end{minipage}
\caption{Quantiles descriptifs p50/p95/p99 de la latence de décision
sémantique sur les trois facteurs disposant d'observations canoniques
réutilisables. Ces courbes ne représentent pas la latence du backend.}
\label{fig:v4-semantic-latency-quantiles}
\end{figure*}

Le facteur \texttt{objective\_count} reste volontairement absent de cette
figure de performance absolue : son manifeste terminal Stage-30 fixe
\texttt{absolute\_timing\_magnitudes\_interpreted=false}. Il demeure donc
utilisé pour documenter la limite de précision terminale (17/192 cellules
hors cible), sans transformer ses magnitudes temporelles en revendication
de performance.
"""
    sec = replace_once(
        sec,
        "\n\\subsection{Portée des conclusions}",
        performance_subsection + "\n\\subsection{Portée des conclusions}",
        "semantic performance subsection injection",
    )

    # Compact article table generated from the same quantile CSV.
    dirs["tables"] = out / "tables"
    dirs["tables"].mkdir(parents=True, exist_ok=True)
    _, _perf_rows = read_csv(dirs["data"] / "semantic_latency_quantiles_p50_p95_p99.csv")
    grouped_perf = {}
    for row in _perf_rows:
        grouped_perf.setdefault(row["factor"], []).append(row)

    table_lines = [
        r"\begin{table*}[!t]",
        r"\centering",
        r"\caption{Caractérisation descriptive de la latence sémantique à partir des observations canoniques existantes.}",
        r"\label{tab:v4-semantic-latency}",
        r"\scriptsize",
        r"\begin{tabular}{@{}lrrrrrr@{}}",
        r"\toprule",
        r"Facteur & Niveau & $n$ & p50 (ms) & p95 (ms) & p99 (ms) & p99/p50 \\",
        r"\midrule",
    ]
    for factor in ("constraint_count", "virtual_node_count", "membership_density"):
        for row in sorted(grouped_perf.get(factor, []), key=lambda r: float(r["factor_level"])):
            table_lines.append(
                f"{tex_escape(factor)} & {row['factor_level']} & {row['observation_count']} & "
                f"{float(row['p50_ms']):.4f} & {float(row['p95_ms']):.4f} & "
                f"{float(row['p99_ms']):.4f} & {float(row['p99_over_p50']):.3f} \\\\"
            )
        table_lines.append(r"\addlinespace")
    table_lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\normalsize",
        r"\end{table*}",
        "",
    ]
    (dirs["tables"] / "T_v4_semantic_latency_quantiles.tex").write_text(
        "\n".join(table_lines), encoding="utf-8"
    )

    (dirs["sections"] / "section_experimentale_finale_v4.tex").write_text(sec, encoding="utf-8")

    supplement = r'''\section{Matériel expérimental supplémentaire V4}
\label{sec:v4-supplement}

\subsection{Distribution des codes de décision — Campagne A}
\begin{figure}[!t]
\centering
\input{article_update/paper_artifacts_v4/figures/F07_campaign_a_reasons.tex}
\caption{Répartition des codes de décision dans la Campagne A.}
\end{figure}

\subsection{Evidence usefulness — AUC}
\begin{figure}[!t]
\centering
\input{article_update/paper_artifacts_v4/figures/F14_evidence_auc.tex}
\caption{AUC de couverture dans le petit protocole contrôlé d'utilité de l'évidence.}
\end{figure}

\subsection{Diagnostics de précision des sensibilités}
Ces figures représentent des diagnostics de précision (demi-largeurs relatives
d'intervalles de confiance) et ne sont pas utilisées comme revendications de
latence backend ou de performance industrielle.

\begin{figure}[!t]
\centering
\input{article_update/paper_artifacts_v4/figures/F15_sensitivity_constraint_precision.tex}
\caption{Diagnostic de précision de la campagne \texttt{constraint\_count}, Stage-20.}
\end{figure}

\begin{figure}[!t]
\centering
\input{article_update/paper_artifacts_v4/figures/F16_sensitivity_virtual_node_precision.tex}
\caption{Diagnostic de précision de la campagne \texttt{virtual\_node\_count}, Stage-10.}
\end{figure}

\begin{figure}[!t]
\centering
\input{article_update/paper_artifacts_v4/figures/F17_sensitivity_membership_density_precision.tex}
\caption{Diagnostic de précision de la campagne \texttt{membership\_density}, Stage-10.}
\end{figure}

\subsection{Traçabilité}
\begin{figure}[!t]
\centering
\resizebox{\linewidth}{!}{\input{article_update/paper_artifacts_v4/figures/F20_provenance_pipeline.tex}}
\caption{Discipline de production des preuves : Audit $\rightarrow$ Validation $\rightarrow$ Freeze $\rightarrow$ Archive $\rightarrow$ Publication.}
\end{figure}
'''
    (dirs["supplement"] / "section_experimental_supplement_v4.tex").write_text(supplement, encoding="utf-8")

    stale_tokens = [
        "évaluation reproduite par annotations expertes",
        "comparaison experte externe",
        "human_validation_scores.png",
        "trois fichiers d'annotation externes",
        "pack compact de 30 items",
        r"\cite{SHACL2017}",
        r"\cite{PROVO2013}",
        r"\cite{TaramadIntent2022}",
    ]
    leaked = [x for x in stale_tokens if x in manuscript]
    if leaked:
        raise RuntimeError("stale manuscript tokens remain: " + ", ".join(leaked))

    (dirs["manuscript"] / "MCAD_audited_real_main_fr_v4.tex").write_text(manuscript, encoding="utf-8")

    prop_md = [
        "# Bibliography and claim propagation — V4",
        "",
        f"Source manuscript commit: `{EXPECTED_HEAD}`",
        "",
        "## Applied changes",
    ]
    for row in propagation_changes:
        prop_md.append(f"- **{row['id']}** — {row['location']}: {row['action']}")
    prop_md += [
        "",
        "## Evidence-policy propagation",
        "- Human/expert validation remains excluded.",
        "- Historical May timing remains excluded from final performance claims.",
        "- Phase-7 historical statistics are not adopted as-is.",
        "- Query-language independence is stated as a canonical-interface principle; implemented MDX/SQL/QP support is documented separately.",
        "- Objective-count Stage-30 negative precision limit is propagated into the conclusion.",
        "",
        "## Reproduction",
        "`python3 scripts/paper_artifacts/v4/generate_publication_artifacts_v4.py --repo-root .`",
        "",
    ]
    (dirs["bibprov"] / "BIBLIOGRAPHY_PROPAGATION_V4.md").write_text("\n".join(prop_md), encoding="utf-8")

    perfprov = out / "provenance" / "performance"
    perfprov.mkdir(parents=True, exist_ok=True)
    (perfprov / "PERFORMANCE_QUANTILE_PUBLICATION_AMENDMENT_V1.md").write_text(
        """# Performance quantile publication amendment

Date: 2026-08-14

Purpose: restore the p50/p95/p99 performance-evaluation structure used in
earlier manuscript versions without reusing their historical numerical values.

Rules:
- no scientific campaign rerun;
- no timing execution;
- no bootstrap rerun;
- p50/p95/p99 are deterministically derived from already-existing canonical
  wall_latency_ms observations for constraint_count, virtual_node_count and
  membership_density;
- p99 is descriptive only; no p99 confidence-interval/precision claim is made;
- objective_count Stage-30 absolute timing remains excluded because its
  terminal execution manifest states absolute_timing_magnitudes_interpreted=false;
- semantic-decision latency must never be conflated with backend SQL/XMLA latency;
- old V-1/V0/V1/V2 numbers are methodological/visual precedents only.
""",
        encoding="utf-8",
    )

    source_rows = [
        {"artifact":"data/q1_q6_canonical_trace.csv","source":"article_update/paper_artifacts_final/data/q1_q6_canonical_trace.csv","authority":"PRIMARY_PHYSICAL"},
        {"artifact":"data/campaign_a_1000_summary.json","source":"article_update/paper_artifacts_final/data/campaign_a_1000_summary.json","authority":"PRIMARY_PHYSICAL"},
        {"artifact":"data/campaign_b_summary.csv","source":"article_update/paper_artifacts_final/data/campaign_b_summary.csv","authority":"PRIMARY_PHYSICAL"},
        {"artifact":"data/campaign_c_summary.csv","source":"article_update/paper_artifacts_final/data/campaign_c_summary.csv","authority":"PRIMARY_PHYSICAL"},
        {"artifact":"data/robustness_by_scenario_type.csv","source":"article_update/paper_artifacts_final/data/robustness_by_scenario_type.csv","authority":"FROZEN_PRIMARY_NON_TEMPORAL"},
        {"artifact":"data/robustness_explainability_summary.csv","source":"article_update/paper_artifacts_final/data/robustness_explainability_summary.csv","authority":"FROZEN_PRIMARY_NON_TEMPORAL"},
        {"artifact":"data/scalability_catalog_structural.csv","source":"article_update/paper_artifacts_final/data/scalability_catalog_structural.csv","authority":"STRUCTURAL_ONLY"},
        {"artifact":"data/evidence_bootstrap_secondary.json","source":"article_update/paper_artifacts_final/data/evidence_bootstrap_secondary.json","authority":"QUALIFIED_SECONDARY"},
        {"artifact":"data/sensitivity_constraint_count_stage20_intervals.csv","source":cc_meta["archive"] + "::" + cc_meta["member"],"authority":"FROZEN_CANONICAL_STAGE20"},
        {"artifact":"data/sensitivity_virtual_node_count_stage10_intervals.csv","source":vn_decision["analysis"]["intervals_csv_path"],"authority":"PRECISION_TARGET_MET_STAGE10"},
        {"artifact":"data/sensitivity_membership_density_stage10_precision_cells.csv","source":sensitivity_map["sources"]["membership_density"]["decision"]["path"],"authority":"PRECISION_DECISION_PASS_STAGE10"},
        {"artifact":"data/sensitivity_objective_count_stage30_intervals.csv","source":sensitivity_map["sources"]["objective_count"]["intervals"]["path"],"authority":"TERMINAL_PRECISION_LIMIT_STAGE30"},
        {"artifact":"data/semantic_latency_quantiles_p50_p95_p99.csv","source":"existing canonical observations for constraint_count/virtual_node_count/membership_density","authority":"POST_HOC_DESCRIPTIVE_NO_NEW_EXECUTION"},
        {"artifact":"objective_count absolute timing","source":sensitivity_map["sources"]["objective_count"]["execution_manifest"]["path"],"authority":"EXCLUDED_ABSOLUTE_TIMING_MAGNITUDES_NOT_INTERPRETED"},
    ]
    write_csv(dirs["prov"] / "publication_data_source_map_v4.csv", ["artifact", "source", "authority"], source_rows)

    manifest = {
        "schema_version": "mcad-publication-artifacts-v4",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_head": EXPECTED_HEAD,
        "scientific_execution_performed": False,
        "experiment_rerun_performed": False,
        "statistical_execution_performed": False,
        "bootstrap_execution_performed": False,
        "backend_execution_performed": False,
        "publication_transformation_only": True,
        "figure_count": len(figmap),
        "bibliography_propagation_applied": True,
        "performance_quantile_characterization": {
            "enabled": True,
            "quantiles": ["p50", "p95", "p99"],
            "source": "existing canonical observations only",
            "new_timing_execution": False,
            "new_bootstrap_execution": False,
            "p99_inferential_precision_claim": False,
            "objective_count_absolute_timing_included": False,
        },
        "campaign_family_count": 15,
        "sensitivity_factor_count": 4,
        "evidence_usefulness_accounted_for": True,
        "phase7_may_as_is_adopted": False,
        "historical_may_timing_publication_authorized": False,
        "human_validation_claims_authorized": False,
        "objective_count_terminal": {
            "stage": 30,
            "cell_count": oc_total,
            "failing_cell_count": oc_fail,
            "rerun_forbidden": True,
            "stage40_authorized": False,
        },
        "manuscript": "manuscript/MCAD_audited_real_main_fr_v4.tex",
        "experimental_section": "sections/section_experimentale_finale_v4.tex",
        "supplement": "supplement/section_experimental_supplement_v4.tex",
    }
    (dirs["manifest"] / "PUBLICATION_V4_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    combined = manuscript + "\n" + sec
    missing = []
    for raw in re.findall(r"\\input\{([^}]+)\}", combined):
        candidate = repo / (raw if Path(raw).suffix else raw + ".tex")
        if not candidate.exists() and raw.startswith("article_update/paper_artifacts_v4/"):
            rel = raw.replace("article_update/paper_artifacts_v4/", "", 1)
            candidate = out / (rel if Path(rel).suffix else rel + ".tex")
        if not candidate.exists():
            missing.append(raw)
    if missing:
        raise RuntimeError("unresolved TeX inputs: " + ", ".join(missing))

    cited = set()
    for group in re.findall(r"\\cite\{([^}]+)\}", manuscript):
        cited.update(x.strip() for x in group.split(","))
    bibkeys = set(re.findall(r"\\bibitem\{([^}]+)\}", manuscript))
    missing_bib = sorted(cited - bibkeys)
    if missing_bib:
        raise RuntimeError("missing bibliography keys: " + ", ".join(missing_bib))

    checks = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            checks.append(f"{sha256_file(p)}  {p.relative_to(out).as_posix()}")
    (out / "SHA256SUMS").write_text("\n".join(checks) + "\n", encoding="utf-8")

    print("publication_v4_generation=PASS")
    print(f"source_head={EXPECTED_HEAD}")
    print(f"figure_count={len(figmap)}")
    print("bibliography_propagation_applied=true")
    print("performance_quantiles=p50,p95,p99")
    print("semantic_latency_quantiles_materialized=true")
    print("p99_inferential_precision_claim=false")
    print("objective_count_absolute_timing_included=false")
    print("citation_key_closure=PASS")
    print("campaign_family_count=15")
    print("sensitivity_factor_count=4")
    print("objective_count_cells=192")
    print("objective_count_failing_cells=17")
    print("evidence_usefulness_accounted_for=true")
    print("human_validation_claims_authorized=false")
    print("historical_may_timing_publication_authorized=false")
    print("phase7_may_as_is_adopted=false")
    print("scientific_execution_performed=false")
    print("experiment_rerun_performed=false")
    print("statistical_execution_performed=false")
    print("bootstrap_execution_performed=false")
    print("backend_execution_performed=false")
    print("NEXT=STATIC_REVIEW_COMMIT_THEN_FINAL_PDF")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--output-root", default="article_update/paper_artifacts_v4")
    args = ap.parse_args()
    repo = Path(args.repo_root)
    out = repo / args.output_root
    main(repo, out)
