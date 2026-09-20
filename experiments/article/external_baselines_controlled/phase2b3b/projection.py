"""Deterministic, execution-neutral construction of observation frames."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

FRAME_VERSION = "phase2b3b.observation_frame.v1"
PROJECTION_VERSION = "phase2b3b.projection.v1"
FORBIDDEN_NORMALIZED_KEYS = frozenset(
    {
        "oracle", "oracle_allow", "oracle_ceval", "expected_decision",
        "mcad_decision", "allow", "block", "safe_to_prune",
        "contribution_label", "ground_truth", "target", "class_label",
    }
)


def normalize_key(key: str) -> str:
    """Normalize common key spellings to lowercase snake case."""
    camel_split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key.strip())
    separated = re.sub(r"[^A-Za-z0-9]+", "_", camel_split)
    return separated.strip("_").lower()


def reject_leakage(value: Any, path: str = "$") -> None:
    """Reject forbidden evaluation/decision keys at every nesting depth."""
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError(f"non-string object key at {path}")
            if normalize_key(key) in FORBIDDEN_NORMALIZED_KEYS:
                raise ValueError(f"forbidden evaluation field at {path}.{key}")
            reject_leakage(nested, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, nested in enumerate(value):
            reject_leakage(nested, f"{path}[{index}]")


def query_digest(canonical_text: str) -> str:
    if not isinstance(canonical_text, str):
        raise TypeError("canonical query text must be a string")
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    """Return the stable UTF-8 JSON representation used by this phase."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def validate_observation_frame(frame: Mapping[str, Any]) -> None:
    """Enforce semantic constraints not expressible portably in JSON Schema."""
    reject_leakage(frame)
    required = {
        "frame_version", "case_id", "dataset_id", "objective_id", "session_id",
        "step_idx", "observation_stage", "query", "history", "current_result", "provenance",
    }
    if set(frame) != required:
        raise ValueError("observation frame top-level fields do not match the frozen contract")
    step_idx = frame["step_idx"]
    if not isinstance(step_idx, int) or isinstance(step_idx, bool) or step_idx < 0:
        raise ValueError("step_idx must be a non-negative integer")
    query = frame["query"]
    if query["canonical_digest"] != query_digest(query["canonical_text"]):
        raise ValueError("canonical query digest mismatch")
    previous = -1
    for entry in frame["history"]:
        history_step = entry["step_idx"]
        if history_step >= step_idx:
            raise ValueError("history must contain prior steps only")
        if history_step <= previous:
            raise ValueError("history steps must be strictly ordered")
        if entry["canonical_digest"] != query_digest(entry["canonical_text"]):
            raise ValueError("history query digest mismatch")
        previous = history_step
    result = frame["current_result"]
    if frame["observation_stage"] == "pre_result":
        if result != {"available": False, "digest": None, "payload": None, "shape": None}:
            raise ValueError("pre-result frame cannot contain current-result content")
    elif frame["observation_stage"] == "post_result":
        if result.get("available") is not True or not isinstance(result.get("digest"), str) or not result["digest"]:
            raise ValueError("post-result frame requires an available, non-empty digest")
    else:
        raise ValueError("unknown observation stage")


def build_observation_frame(*, case_id: str, dataset_id: str, objective_id: str,
                            session_id: str, step_idx: int, observation_stage: str,
                            canonical_text: str, query_spec: Mapping[str, Any],
                            history: Sequence[Mapping[str, Any]], current_result: Mapping[str, Any],
                            source_kind: str, source_identifiers: Mapping[str, Any],
                            source_digests: Mapping[str, str]) -> dict[str, Any]:
    """Build a copied, deterministic frame without inventing query semantics."""
    frame = {
        "frame_version": FRAME_VERSION,
        "case_id": case_id, "dataset_id": dataset_id, "objective_id": objective_id,
        "session_id": session_id, "step_idx": step_idx, "observation_stage": observation_stage,
        "query": {"canonical_text": canonical_text, "canonical_digest": query_digest(canonical_text),
                  "query_spec": copy.deepcopy(dict(query_spec))},
        "history": copy.deepcopy(list(history)),
        "current_result": copy.deepcopy(dict(current_result)),
        "provenance": {"projection_version": PROJECTION_VERSION, "source_kind": source_kind,
                       "source_identifiers": copy.deepcopy(dict(source_identifiers)),
                       "source_digests": dict(sorted(source_digests.items()))},
    }
    validate_observation_frame(frame)
    return frame
