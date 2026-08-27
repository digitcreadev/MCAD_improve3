# MCAD NH-MANUSCRIPT-DELTA-0c - Section-by-section semantic patch specification

**Mode:** NO EDIT / READ-ONLY SPECIFICATION

**A8 parent:** `MCAD_FR_V8_7_6.tex` — `c013a6f1e3f84a2e6e898a07106c5e5f4bb0cd9227e3b6763caf6e2186c2060c`
**Current experimental checkpoint:** `e9b48f5f7fab90932d428ff0277c1454c7e5dc05` (R3-E8)

## Global semantic boundary
A8 remains immutable. The new paper is a post-A8 descendant whose scientific authority is distributed across A8 core/provenance, A45/NH-R0, NH-R1/NH-R2, NH-RW-Delta-2/R3-A2, R3-D4, and R3-E8. Pending R3-E/R3-F/NH-R4 results remain placeholders only.

## Current formal contract
- O and objective-defined analytical basis
- G_O objective-constraint-support/evidence graph
- typed CKG plus session evidence state
- Canonical Query Profile (CQP) as objective-relative reasoning interface
- semantic admissibility pre-NVAC distinct from evidence realizability
- probe/realizability evidence distinct from acquired evidence
- computability/contribution distinct from action
- NONCONTRIBUTIVE_NOW != SAFE_TO_PRUNE
- residual objective frontier + sufficient safe-pruning condition + fail-open
- time_to_analytical_objective_completion_ms as normative completion-time metric
- MCAD correctness != decision correctness

## Section-by-section patch map
### 1. Title — A8 lines 34 — **REWRITE**
- Keep: MCAD name/acronym; OLAP/decision-analytics context if still useful
- Remove/avoid: title centered only on query contribution to strategic calculability
- Add: objective-relative analytical completeness/safe dispensability focus; system/resource angle only at level supported by R3-D4
- Authority: A45/NH-R0; R3-A2; R3-D4
- Boundary: Do not promise universal system benefit or completed XMLA confirmation.

### 2. Abstract — A8 lines 42-46 — **REWRITE**
- Keep: session-relative context; objective/constraints/supports; separation contribution vs action; no human-value claim
- Remove/avoid: A8 evaluation summary as if it were the current evidentiary ceiling; semantic-core p50/p99 as headline system result
- Add: safe-pruning preservation result NH-R1; deferred multi-query evidence NH-R2; confirmatory SQL Direct R3-D4: 6/8 primary endpoints confirmed; two I/O-byte endpoints non-confirmed; R3-E/XMLA measured confirmation pending
- Authority: NH-R1; NH-R2; R3-D4; R3-E8
- Boundary: No global system-benefit sentence; no measured XMLA result.

### 3. IEEEkeywords — A8 lines 48-50 — **REWRITE**
- Keep: data warehouses; OLAP; business intelligence; strategic objectives; knowledge graph
- Remove/avoid: keywords implying human decision-quality validation
- Add: safe pruning; analytical completeness; session evidence; canonical query profile; resource-aware analytical control
- Authority: R3-A2; NH-R1/NH-R2; R3-D4
- Boundary: Use system/semantic terms, not psychological outcome terms.

### 4. Introduction — A8 lines 52-89 — **REWRITE**
- Keep: problem that executable != analytically useful for active objective; session-relative state; admissibility != contribution; action policy separate from semantic reasoning
- Remove/avoid: four-contribution block as current final contribution list; framing where Delta phi is the main discriminator for pruning
- Add: decision problem -> objective formalization -> objective-defined analytical basis -> cumulative session computability -> safe dispensability -> pre-backend suppression; CQP as enabling contribution; safe-pruning preservation and deferred contribution; end-to-end resource estimand and D4 result; human decision making explicitly outside claim
- Authority: A45/NH-R0; NH-R1; NH-R2; RW-Delta-2; R3-A2; R3-D4
- Boundary: NONCONTRIBUTIVE_NOW must not be equated with SAFE_TO_PRUNE.

### 5. Travaux connexes et voisinage scientifique — A8 lines 90-152 — **HEAVY_REWRITE**
- Keep: OLAP/summarizability; goal/KPI engineering; intentional analytics/ASSESS; KG/provenance where still in final selection
- Remove/avoid: A8 comparison matrix as sufficient prior-art audit; references/families explicitly superseded by RW-Delta-2 selection decisions; first/only language
- Add: F1 goal/objective formalization; F2 contextual KG; F3 canonical query IR: Calcite/Substrait boundary; F4 personalization; F5 intentional analytics/query assessment; F6 session/multi-query; F7 semantic query optimization; F8 empty/non-empty query analysis; F9 provenance/summarizability; F10 workload/admission control; F11 data skipping/physical pruning/reuse; F12 decision support vs decision making
- Authority: NH-RW-Delta-2; A44 as editorial pool only
- Boundary: Novelty = integrated objective/evidence/session/safe-preexecution chain, not novelty of each primitive.

### 6. Vue d ensemble de MCAD — A8 lines 153-208 — **EXTEND_RESTRUCTURE**
- Keep: semantic layer between analyst and warehouse; CKG role; canonicalization concept; objective constraints/supports
- Remove/avoid: overview chain ending directly in Delta phi -> policy as if safe pruning followed from marginal contribution
- Add: G_O explicitly; typed CKG; CQP; semantic admissibility pre-NVAC; evidence realizability vs acquired evidence; safe-pruning proof gate; fail-open branch
- Asset actions: `figures/fr/F01_conceptual_chain.tex`=REPLACE; `figures/fr/F_contribution_hierarchy.tex`=REPLACE_OR_HEAVY_REWRITE
- Authority: R3-A2; NH-R1/NH-R2
- Boundary: The overview must distinguish probe interaction from full backend execution.

### 7. Contexte de l analyse décisionnelle et CKG — A8 lines 216-247 — **KEEP_EXTEND**
- Keep: multidimensional warehouse notation; decision-analysis context components; CKG as explicit relational representation
- Remove/avoid: notation collision where E_t denotes both CKG edges and acquired evidence
- Add: typed node/edge partition compatible with G_O; separate symbols for graph edges and evidence state; explicit frozen-vs-session-evolving components
- Authority: R3-A2
- Boundary: Do not make automatic CKG construction an implemented result.

### 8. Objectifs stratégiques, contraintes et nœuds virtuels — A8 lines 248-277 — **REWRITE**
- Keep: O and KPI/constraint distinction; virtual/analytical evidence atom concept
- Remove/avoid: wording that treats one N(c) set as universally necessary when alternative sufficient supports exist
- Add: G_O tripartite objective-constraint-support/evidence representation; Supp(c) as alternative sufficient supports; UNRESOLVED/PARTIALLY_SUPPORTED/COMPUTABLE state semantics; ACTIVE_REQUIRED/SATISFIED_INACTIVE mask if retained by contract
- Authority: R3-A2
- Boundary: Sufficiency and necessity must not be conflated.

### 9. Plans canoniques et validité contextuelle — A8 lines 278-335 — **HEAVY_REWRITE**
- Keep: canonical semantic representation idea; grain/aggregation/unit/slicer/time checks; language-independent extraction interface
- Remove/avoid: nvac_ok inside SAT; DAX presented as if experimentally validated
- Add: rename/promote CQP; required CQP fidelity/completeness contract; semantic admissibility PRE-NVAC; NOVC/NVAC as separate evidence-realizability/probe gate; EXECUTE_FAIL_OPEN when canonicalization/proof insufficient; SQL/MDX demonstrated; DAX architectural/future
- Authority: R3-A2; RW-Delta-2
- Boundary: Non-vacuity is not semantic contribution and not a novelty claim by itself.

### 10. Évidence réalisable, contraintes calculables et masque contextuel — A8 lines 336-415 — **HEAVY_REWRITE**
- Keep: alternative sufficient support semantics; E_t monotone acquired evidence idea; partial-support concept only if clearly secondary
- Remove/avoid: Real(QP) language that can blur probe-confirmed realizability with evidence actually acquired; any rule where probe success advances E_t
- Add: evidence realizability separate from acquired evidence; probe receipts do not become full session evidence; after PRUNE: E_{t+1}=E_t; after successful full execution: acquired_evidence may update E_t; residual objective frontier U(E_t)
- Authority: R3-A2; NH-R1; NH-R2
- Boundary: Do not credit backend probes as if the analytical result had been acquired.

### 11. Mesures de contribution, progression de session et complexité — A8 lines 416-482 — **HEAVY_REWRITE_EXTEND**
- Keep: evidence-based cumulative computability; phi as objective-level completion descriptor where compatible; historical A1/A2 equivalence result as bounded legacy lemma
- Remove/avoid: using Delta phi=0 as sufficient pruning criterion; complexity discussion as substitute for end-to-end cost
- Add: NONCONTRIBUTIVE_NOW != SAFE_TO_PRUNE; deferred support contribution; safe-pruning preservation theorem/condition; fail-open; time_to_analytical_objective_completion_ms; separate semantic-core complexity from end-to-end gate/probe/backend cost
- Authority: NH-R1; NH-R2; R3-A2; R3-D0/D4
- Boundary: No universal optimality/minimality theorem unless separately proved.

### 12. Indicateur de contribution et politique d action — A8 lines 483-508 — **REWRITE**
- Keep: semantic reasoning separate from deployment action
- Remove/avoid: strict policy = block all admissible Delta phi zero candidates
- Add: SAFE_PRUNING decision class based on proof obligation; STRICT_IMMEDIATE as semantic baseline only; PERMISSIVE_GATED and UNGATED_EXECUTE_ADMISSIBLE as causal system baselines; fail-open execute when safety proof unavailable
- Authority: NH-R1/NH-R2; R3-A2; R3-A1/D0
- Boundary: A policy baseline is not part of MCAD semantics.

### 13. Abstraction canonique et indépendance langage — A8 lines 509-525 — **EXTEND_REWRITE**
- Keep: reasoner consumes canonical representation rather than raw syntax
- Remove/avoid: broad language-independence interpretation
- Add: CQP contract and fidelity requirement; SQL and MDX/XMLA demonstrated paths; DAX/future language adapters = architectural possibility only
- Authority: R3-A2; RW-Delta-2; R3-E8 boundary
- Boundary: Do not use R3-E static preparation as measured cross-language confirmation.

### 14. Architecture du prototype et flux de travail — A8 lines 526-573 — **REWRITE_EXTEND**
- Keep: layer separation; adapter/canonical representation; session memory; configurable action policy
- Remove/avoid: old fixed QP->SAT->Real->C_eval->phi workflow as current runtime contract
- Add: CQP -> semantic admissibility -> NVAC/NOVC probe -> evidence realizability -> safe-prune proof -> PRUNE or full execute -> acquired-evidence update; measurement boundary where gate probes count as backend requests; PRUNE != zero backend interaction
- Asset actions: `figures/fr/fig_mcad_architecture_v8_2_singlecol.pdf`=REPLACE
- Authority: R3-A2; R3-B/C/D methods
- Boundary: Historical protected runtime details belong to reproducibility/provenance, not the conceptual architecture figure.

### 15. Évaluation expérimentale — A8 lines 574-700 — **REBUILD**
- Keep: historical Q1-Q6/A/B/C/robustness/scalability evidence as legacy evidence block; explicit limitations on semantic-core latency; component-sensitivity interpretation of ablations
- Remove/avoid: six old RQs as the final evaluation architecture; phrase mechanism causal at session level; historical semantic-core timing as end-to-end performance proof
- Add: evaluation authority ladder: inherited evidence -> NH-R1 -> NH-R2 -> R3-B DEV -> R3-C validation -> R3-D confirmatory; pre-registered baselines SAFE/PERMISSIVE/UNGATED and STRICT_IMMEDIATE semantic baseline; R3-D 300 sessions/900 arms and 8-primary-endpoint Holm family; report 6/8 confirmed, 2 I/O-byte endpoints not confirmed; R3-C negative break-even evidence vs UNGATED; R3-E status placeholder: statically ready through E8, measured replication pending
- Asset actions: `Q1-Q6 UI/F04/F05`=KEEP_BUT_DEMOTE_TO_HISTORICAL_EVIDENCE; `F08/F09 multi-dataset/backend parity`=KEEP_AS_LEGACY_PORTABILITY_EVIDENCE; `F10 robustness`=KEEP_AS_CONTROLLED_SEMANTIC_EVIDENCE; `F12/F21/F22/F23`=KEEP_WITH_CORE_ONLY_SCALABILITY_LATENCY_LABEL; `new R3-D table/figure`=ADD_FROM_FROZEN_D4_ONLY
- Authority: A8 historical evidence; NH-R1; NH-R2; R3-B2m; R3-C; R3-D0/D3/D4; R3-E8
- Boundary: No new R3-E numeric result; no D4 recomputation; no global system-benefit claim.

### 16. Discussion, limites et perspectives — A8 lines 701-738 — **REWRITE**
- Keep: construct validity limits; business-oracle dependence; human value out of scope; external superiority not established; automatic CKG construction future
- Remove/avoid: claims that end-to-end latency/backend cost is wholly unmeasured; future-work statement that multi-query support assembly is untested
- Add: 6/8 confirmatory endpoint interpretation; I/O bytes not confirmed; no global system-benefit claim; SAFE can lose time vs UNGATED despite backend savings; R3-E measured confirmation pending; NH-R4 concurrency/scale/tail-latency/memory/break-even pending; distinguish structural semantic-core scalability from future end-to-end scalability
- Authority: A9 boundary audit; NH-R2; R3-C; R3-D4; R3-E8
- Boundary: Negative/non-confirmed results must remain visible.

### 17. Conclusion — A8 lines 739-747 — **REWRITE**
- Keep: objective/constraints/supports; canonical representation; session-relative reasoning; action policy separate
- Remove/avoid: conclusion centered on Delta phi contribution indicator; general statements stronger than endpoint-specific D4 evidence
- Add: safe objective-relative dispensability; preservation/deferred-contribution evidence; confirmatory SQL Direct 6/8 summary; explicit pending XMLA/R4 boundaries
- Authority: NH-R1/NH-R2; R3-A2; R3-D4; R3-E8
- Boundary: No universal backend/language/scalability generalization.

### 18. Appendices and bibliography — A8 lines 751-757 — **KEEP_EXTEND_AUDIT**
- Keep: formal proof appendix where still valid; FoodMart historical formalization; pinned bibliography as A8 baseline
- Remove/avoid: proofs whose premises conflict with updated safe-pruning formalism without re-validation
- Add: new safe-pruning/deferred-support formal material if not already externalized; RW-Delta-2 additions and exclusions; new R3 protocol/reproducibility references only if publication style permits
- Authority: NH-R1; NH-RW-Delta-2; R3-A2
- Boundary: Bibliographic expansion must not silently reintroduce references excluded by the later selection audit.

## Claim ledger
| Claim | Status | Authority / boundary |
|---|---|---|
| Objective-relative analytical computability/completeness is the semantic target | ALLOWED | R3-A2 + A8 core |
| Safe pruning preserves objective completion under frozen assumptions | ALLOWED_BOUNDED | NH-R1/NH-R2 |
| Deferred multi-query contribution is empirically exercised | ALLOWED_BOUNDED | NH-R2 |
| SQL Direct SAFE vs PERMISSIVE resource/time reductions | ALLOWED_ENDPOINT_SPECIFIC | R3-D4; 6/8 primary endpoints confirmed |
| SQL Server I/O read/write byte reductions | NOT_CONFIRMED | R3-D4 |
| Global system benefit | FORBIDDEN | R3-D4 contract |
| SAFE universally faster than UNGATED | FORBIDDEN | R3-C negative break-even evidence |
| R3 XMLA/eMondrian measured confirmation | PENDING_NOT_CLAIMABLE | R3-E8 |
| End-to-end concurrency/industrial scalability | PENDING_NOT_CLAIMABLE | NH-R4 pending |
| Human decision quality improvement | OUT_OF_SCOPE | A45/NH-R0 + R3-A2 |
| First/only objective-aware/session-aware/pruning mechanism | FORBIDDEN_WITHOUT_NEW_AUDIT | NH-RW-Delta-2 |

## D4 frozen endpoint summary
| Metric | SAFE-PERMISSIVE mean diff | Holm p | Confirmed |
|---|---:|---:|---|
| `backend_request_count_including_gate_probes` | -16.2 | 7.99992e-05 | yes |
| `full_backend_execution_count` | -16.2 | 7.99992e-05 | yes |
| `client_wall_ms` | -913.321858403 | 7.99992e-05 | yes |
| `sqlserver_cpu_usage_usec_delta` | -771626.43 | 7.99992e-05 | yes |
| `response_bytes` | -150731.476667 | 7.99992e-05 | yes |
| `time_to_analytical_objective_completion_ms` | -202.580846887 | 7.99992e-05 | yes |
| `sqlserver_io_rbytes_delta` | -94126.08 | 0.429436 | no |
| `sqlserver_io_wbytes_delta` | -2416.64 | 0.429436 | no |

## No-edit exit rule
Acceptance of DELTA-0c authorizes only preparation of a new descendant branch/worktree. It does not authorize editing A8 in place, recomputing D4, rerunning historical campaigns, or inventing pending XMLA/R4 results.
