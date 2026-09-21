import json
from pathlib import Path

from schema_subset import validate_schema_subset

ROOT = Path(__file__).resolve().parents[1]


def test_plan_matches_schema(plan):
    schema = json.loads((ROOT / "execution_plan.schema.json").read_text())
    validate_schema_subset(plan, schema)


def test_authority_and_source(plan):
    base = json.loads((ROOT / "provenance/base_freeze_reference.json").read_text())
    assert base["phase2b3b_head"] == "f38807edcafde2547c177d79ce5b0d78891b3491"
    assert base["phase2b3b_tree"] == "9bfc5077f54bab353b4a1a9cc7d1f7e618d85e59"
    assert base["phase2b2_a7_evidence_sha256"] == "7c64b62b6549fffe8fe5b5ca5595d676ed7cbf164e0ff1031e8c7094303e912f"
    assert base["phase2b2_a9_final_freeze_sha256"] == "40c4ede02a919765f8baf15d71978df183001c882a46019ee7204456aabac9df"
    assert plan["source"] == {"repository": "https://github.com/DAINTINESS-Group/DelianCubeEngine", "commit": "606f94afe88767665ce185566ca8357a56f736d2", "publication": "doi:10.1016/j.is.2024.102381"}


def test_environment(plan):
    env = plan["environment"]
    assert env["mysql_image"] == "mysql:8.0.33"
    assert env["dumps"] == {
        "adult_backup.sql": "a898803ba45d45b9d0d12c8333f3d08f4b490fb58a617cf3db5fdc167de250a2",
        "pkdd99_backup.sql": "6651a2ebe21011629dc3e17a4b03c5eb4ec07f3e439b42f0b1778740ed9fbcd9",
        "pkdd99_star_backup.sql": "8454ce68a5a7d7c15c3a45ad8806fdff528296b4f257081ca20231617f691916"}
    assert env["schemas"] == {"adult_no_dublic": {"a7_table_count": 17}, "pkdd99": {"a7_table_count": 6, "loan_row_count": 682}, "pkdd99_star": {"a7_table_count": 6}}
    assert len(env["history_fixtures"]) == 2


def test_tracks(plan):
    pre, post = plan["tracks"]["PRE_NATIVE_SMOKE"], plan["tracks"]["POST_NATIVE_SMOKE"]
    assert pre["junit_classes"] == ["DirectNoveltyTest", "PartialSyntacticAveragePeculiarityTest"]
    assert post["junit_classes"] == ["IndirectNoveltyTest", "PartialDetailedExtensionalRelevanceTest", "LabelSurpriseTest"]
    assert (pre["expected_test_method_count"], post["expected_test_method_count"]) == (2, 5)
    assert pre["timeout_seconds"] == post["timeout_seconds"] == 300
