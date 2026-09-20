"""Pure data projection for the frozen Delian mapping; no execution occurs."""

from __future__ import annotations

import copy
from typing import Any, Mapping

from projection import validate_observation_frame

DELIAN_PROVENANCE = {
    "repository": "https://github.com/DAINTINESS-Group/DelianCubeEngine",
    "source_ref": "606f94afe88767665ce185566ca8357a56f736d2",
    "publication_reference": "doi:10.1016/j.is.2024.102381",
}
_MEASURES = {
    "pre_result": ["DirectNovelty", "PartialSyntacticAveragePeculiarity"],
    "post_result": ["IndirectNovelty", "PartialDetailedExtensionalRelevance", "LabelSurprise"],
}
_METHODS = {"pre_result": "delian_pre", "post_result": "delian_post"}


def describe_delian(frame: Mapping[str, Any]) -> dict[str, Any]:
    """Return JSON-compatible invocation data, never an executable invocation."""
    validate_observation_frame(frame)
    stage = frame["observation_stage"]
    return {
        "descriptor_version": "phase2b3b.delian.v1",
        "method_id": _METHODS[stage],
        "observation_stage": stage,
        "measures": list(_MEASURES[stage]),
        "auxiliary_query": None,
        "execution": "not_authorized",
        "provenance": copy.deepcopy(DELIAN_PROVENANCE),
        "observation": copy.deepcopy(dict(frame)),
    }
