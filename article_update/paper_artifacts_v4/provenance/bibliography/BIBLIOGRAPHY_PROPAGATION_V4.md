# Bibliography and claim propagation — V4

Source manuscript commit: `922815488832ecf20d6f31008da044bd3e1c02b0`

## Applied changes
- **CIT01** — Résumé: absolute novelty -> bounded literature conclusion
- **CIT01-PROP** — Introduction: propagate bounded novelty wording
- **KEY-SHACL** — Section II: \cite{SHACL2017} -> \cite{W3CSHACL2017}
- **KEY-PROVO** — Section II: \cite{PROVO2013} -> \cite{W3CPROVO2013}
- **KEY-INTENT** — Section II: \cite{TaramadIntent2022} -> \cite{FarihaMeliou2019}
- **CIT02** — Section II / tableau de positionnement: categorical absence softened
- **CIT06** — Section IV / CKG: generic literature separated from MCAD relation vocabulary
- **CIT07** — Section IV: conceptual canonicalization separated from implemented parsers/evidence
- **CIT07-PROP** — Section V: implemented parser scope made explicit
- **BIB-SchuetzSerafiniBozzato2021** — Bibliographie: verified metadata correction
- **BIB-StaudingerSchuetzSchrefl2025** — Bibliographie: verified metadata correction
- **BIB-KostopoulosXAIDSS2024** — Bibliographie: verified metadata correction
- **BIB-PERFORMANCE-METHOD** — Bibliographie + Section VII: add tail-latency and rigorous benchmarking methodology references
- **PROP-CONCLUSION** — Conclusion: human/timing stale claims removed; final evidence gates propagated

## Evidence-policy propagation
- Human/expert validation remains excluded.
- Historical May timing remains excluded from final performance claims.
- Phase-7 historical statistics are not adopted as-is.
- Query-language independence is stated as a canonical-interface principle; implemented MDX/SQL/QP support is documented separately.
- Objective-count Stage-30 negative precision limit is propagated into the conclusion.

## Reproduction
`python3 scripts/paper_artifacts/v4/generate_publication_artifacts_v4.py --repo-root .`
