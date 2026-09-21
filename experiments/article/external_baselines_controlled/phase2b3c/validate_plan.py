"""Pure local-data validation for the Phase 2B-3C1 contract (not a runner)."""

import json
from pathlib import Path

from tests.schema_subset import validate_schema_subset

ROOT = Path(__file__).resolve().parent


def load_json(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def validate():
    plan = load_json("delian_native_smoke_plan.json")
    schema = load_json("execution_plan.schema.json")
    validate_schema_subset(plan, schema)
    assertions = load_json("native_assertions.json")
    if assertions["source_commit"] != plan["source"]["commit"]:
        raise ValueError("native assertion source does not match plan source")
    return plan


if __name__ == "__main__":
    validate()
    print("Phase 2B-3C1 contract is internally consistent; nothing was executed.")
