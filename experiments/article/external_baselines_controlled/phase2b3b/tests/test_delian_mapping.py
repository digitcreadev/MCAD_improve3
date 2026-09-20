from delian_mapping import DELIAN_PROVENANCE, describe_delian


def test_pre_descriptor_is_exact_data(pre_frame):
    descriptor = describe_delian(pre_frame)
    assert descriptor["method_id"] == "delian_pre"
    assert descriptor["measures"] == ["DirectNovelty", "PartialSyntacticAveragePeculiarity"]
    assert descriptor["auxiliary_query"] is None
    assert descriptor["execution"] == "not_authorized"


def test_post_descriptor_is_exact_data(post_frame):
    descriptor = describe_delian(post_frame)
    assert descriptor["method_id"] == "delian_post"
    assert descriptor["measures"] == ["IndirectNovelty", "PartialDetailedExtensionalRelevance", "LabelSurprise"]
    assert "FamilyBasedRelevance" not in descriptor["measures"]


def test_provenance_is_frozen(post_frame):
    assert describe_delian(post_frame)["provenance"] == DELIAN_PROVENANCE == {
        "repository": "https://github.com/DAINTINESS-Group/DelianCubeEngine",
        "source_ref": "606f94afe88767665ce185566ca8357a56f736d2",
        "publication_reference": "doi:10.1016/j.is.2024.102381",
    }
