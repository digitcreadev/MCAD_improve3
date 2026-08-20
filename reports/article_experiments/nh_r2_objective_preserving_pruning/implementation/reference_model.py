from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, FrozenSet, Mapping, Sequence, Set, Tuple

Evidence = FrozenSet[str]
Support = FrozenSet[str]
SupportFamily = Tuple[Support, ...]
Spec = Mapping[str, SupportFamily]

INADMISSIBLE = "INADMISSIBLE"
IMMEDIATE = "IMMEDIATE_CONTRIBUTOR"
DEFERRED = "DEFERRED_SUPPORT_CONTRIBUTOR"
REDUNDANT = "REDUNDANT_DISPENSABLE"
DISTRACTOR = "DISTRACTOR_DISPENSABLE"
SAFE_CLASSES = frozenset({INADMISSIBLE, REDUNDANT, DISTRACTOR})

@dataclass(frozen=True)
class Query:
    query_id: str
    sat: bool
    real: Evidence


def computable_constraints(spec: Spec, evidence: Evidence) -> FrozenSet[str]:
    out = set()
    for c, supports in spec.items():
        if any(S.issubset(evidence) for S in supports):
            out.add(c)
    return frozenset(out)


def phi(spec: Spec, evidence: Evidence) -> float:
    if not spec:
        return 1.0
    return len(computable_constraints(spec, evidence)) / len(spec)


def residual_frontier(spec: Spec, evidence: Evidence) -> Evidence:
    """U(E): every still-missing atom in every support of unresolved constraints."""
    resolved = computable_constraints(spec, evidence)
    frontier: Set[str] = set()
    for c, supports in spec.items():
        if c in resolved:
            continue
        for S in supports:
            frontier.update(S.difference(evidence))
    return frozenset(frontier)


def classify(spec: Spec, evidence: Evidence, q: Query) -> Dict[str, object]:
    before = computable_constraints(spec, evidence)
    frontier = residual_frontier(spec, evidence)
    if not q.sat:
        return {
            "class": INADMISSIBLE,
            "safe_to_prune": True,
            "reason": "SAT_FALSE",
            "novel": frozenset(),
            "frontier": frontier,
            "frontier_gain": frozenset(),
            "delta_phi": 0.0,
            "before": before,
            "after": before,
        }
    novel = q.real.difference(evidence)
    after_e = frozenset(set(evidence).union(q.real))
    after = computable_constraints(spec, after_e)
    delta = (len(after) - len(before)) / len(spec) if spec else 0.0
    gain = frozenset(novel.intersection(frontier))
    if delta > 0:
        cls = IMMEDIATE
        reason = "NEWLY_COMPUTES_AT_LEAST_ONE_CONSTRAINT"
    elif gain:
        cls = DEFERRED
        reason = "ADVANCES_RESIDUAL_SUPPORT_WITHOUT_IMMEDIATE_COMPLETION"
    elif not novel:
        cls = REDUNDANT
        reason = "NO_NOVEL_EVIDENCE"
    else:
        cls = DISTRACTOR
        reason = "NOVEL_EVIDENCE_OUTSIDE_UNRESOLVED_SUPPORT_FRONTIER"
    return {
        "class": cls,
        "safe_to_prune": cls in SAFE_CLASSES,
        "reason": reason,
        "novel": frozenset(novel),
        "frontier": frontier,
        "frontier_gain": gain,
        "delta_phi": delta,
        "before": before,
        "after": after,
    }


def execute_if_kept(evidence: Evidence, q: Query, keep: bool) -> Evidence:
    if not keep or not q.sat:
        return evidence
    return frozenset(set(evidence).union(q.real))


def strict_immediate_keep(spec: Spec, evidence: Evidence, q: Query) -> bool:
    r = classify(spec, evidence, q)
    return q.sat and float(r["delta_phi"]) > 0


def safe_pruning_keep(spec: Spec, evidence: Evidence, q: Query) -> bool:
    return not bool(classify(spec, evidence, q)["safe_to_prune"])


def run_sequence(spec: Spec, initial: Evidence, queries: Sequence[Query], policy: str) -> Dict[str, object]:
    e = initial
    trace = []
    for q in queries:
        r = classify(spec, e, q)
        if policy == "PERMISSIVE":
            keep = q.sat
        elif policy == "STRICT_IMMEDIATE":
            keep = strict_immediate_keep(spec, e, q)
        elif policy == "SAFE_PRUNING":
            keep = safe_pruning_keep(spec, e, q)
        else:
            raise ValueError(policy)
        e2 = execute_if_kept(e, q, keep)
        trace.append({"query_id": q.query_id, "class": r["class"], "keep": keep, "phi_before": phi(spec,e), "phi_after": phi(spec,e2)})
        e = e2
    return {"final_evidence": e, "final_phi": phi(spec,e), "trace": trace}

def operational_prune_decision(spec: Spec, evidence: Evidence, q: Query, semantic_contract_valid: bool = True) -> Dict[str, object]:
    """Policy wrapper. Semantic dispensability pruning fails open when proof assumptions are not validated."""
    r = classify(spec, evidence, q)
    if r["class"] == INADMISSIBLE:
        return {**r, "operational_action": "REJECT_INADMISSIBLE", "proof_status": "SAT_SEPARATE"}
    if not semantic_contract_valid:
        return {**r, "safe_to_prune": False, "operational_action": "EXECUTE_FAIL_OPEN", "proof_status": "UNPROVEN_SEMANTIC_CONTRACT"}
    if r["class"] in (REDUNDANT, DISTRACTOR):
        return {**r, "operational_action": "PRUNE", "proof_status": "PROVEN_UNDER_R1_ASSUMPTIONS"}
    return {**r, "operational_action": "EXECUTE", "proof_status": "RETAINED_CONTRIBUTOR"}
