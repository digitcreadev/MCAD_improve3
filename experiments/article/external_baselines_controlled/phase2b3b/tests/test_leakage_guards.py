import copy

import pytest

from projection import FORBIDDEN_NORMALIZED_KEYS, reject_leakage, validate_observation_frame


@pytest.mark.parametrize("key", sorted(FORBIDDEN_NORMALIZED_KEYS))
def test_every_forbidden_key_is_rejected_recursively(pre_frame, key):
    frame = copy.deepcopy(pre_frame)
    frame["query"]["query_spec"]["nested"] = [{key: "leak"}]
    with pytest.raises(ValueError, match="forbidden evaluation field"):
        validate_observation_frame(frame)


@pytest.mark.parametrize("variant", ["GroundTruth", "safe-to-prune", "MCAD Decision", "CLASS_LABEL"])
def test_key_normalization_closes_spelling_variants(variant):
    with pytest.raises(ValueError):
        reject_leakage({"outer": [{variant: 1}]})
