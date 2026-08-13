# MCAD — registre maître des sources expérimentales de publication

- Base git : `4214bd3a072179b0aba921535b28d31167c7f052`
- Branche : `paper/publication-artifact-pipeline-20260813T124125Z`
- Généré : `2026-08-13T12:52:07Z`
- Mode : résolution de sources et provenance uniquement.
- Exécution scientifique : **non**.

| Bloc | Classe de preuve | Résolution | Sources de contrôle | Runners |
|---|---|---|---:|---:|
| UI / trace canonique Q1-Q6 | `physical_end_to_end` | `DISCOVERED_REQUIRES_CANONICAL_SELECTION` | 0 | 10 |
| Campagne A — profondeur expérimentale FoodMart | `physical_consolidated` | `CANONICAL_ANCHOR_IDENTIFIED` | 2 | 10 |
| Campagne B — validation physique multi-dataset | `physical_multidataset` | `CANONICAL_ANCHOR_IDENTIFIED` | 1 | 2 |
| Campagne C — portabilité backend contrôlée | `physical_paired_backend` | `CANONICAL_ANCHOR_IDENTIFIED` | 1 | 0 |
| Baselines contrôlées | `controlled_replay` | `DISCOVERED_REQUIRES_CANONICAL_SELECTION` | 3 | 1 |
| Ablations SAT / Real / Ceval | `controlled_ablation` | `DISCOVERED_REQUIRES_CANONICAL_SELECTION` | 0 | 3 |
| Robustesse | `controlled_robustness` | `CANONICAL_ANCHOR_IDENTIFIED` | 8 | 4 |
| Scalabilité structurelle du CKG | `controlled_scalability` | `DISCOVERED_REQUIRES_CANONICAL_SELECTION` | 0 | 1 |
| Evidence usefulness | `controlled_treatment_control` | `DISCOVERED_REQUIRES_CANONICAL_SELECTION` | 0 | 1 |
| Sensibilité — constraint_count | `controlled_sensitivity_timing` | `CANONICAL_ANCHOR_IDENTIFIED` | 8 | 10 |
| Sensibilité — virtual_node_count | `controlled_sensitivity_timing` | `CANONICAL_ANCHOR_IDENTIFIED` | 8 | 10 |
| Sensibilité — membership_density | `controlled_sensitivity_timing` | `CANONICAL_ANCHOR_IDENTIFIED` | 8 | 10 |
| Sensibilité — objective_count | `controlled_sensitivity_timing` | `CANONICAL_ANCHOR_IDENTIFIED` | 8 | 10 |
| Validation humaine / experts | `optional_human_validation` | `DISCOVERED_REQUIRES_CANONICAL_SELECTION` | 0 | 2 |

## Contrat de publication

Un nombre, tableau, graphique ou claim ne doit être publié que s'il peut être relié à une source canonique/gelée, à sa provenance et à un checksum.

Les anciens manuscrits servent à reconstruire la structure éditoriale et les questions scientifiques ; ils ne constituent pas des sources numériques autoritaires.

Les classes de preuves physiques, replay/benchmark et sensibilité/timing restent distinctes.

## Étape suivante

Résoudre exclusivement les campagnes marquées `DISCOVERED_REQUIRES_CANONICAL_SELECTION` à partir des bundles `locked` ou `frozen`, sans relancer les expériences. Les extracteurs publication-ready seront ensuite construits sur les sources sélectionnées.
