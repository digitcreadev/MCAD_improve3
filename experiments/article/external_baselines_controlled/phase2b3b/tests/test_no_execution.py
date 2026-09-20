import ast
import json
from pathlib import Path

from conftest import PHASE_ROOT


def test_runtime_modules_have_no_execution_or_io_imports():
    forbidden = {"subprocess", "socket", "requests", "urllib", "http", "docker", "sqlalchemy"}
    for name in ("projection.py", "delian_mapping.py"):
        tree = ast.parse((PHASE_ROOT / name).read_text())
        imports = set()
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module: imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call): calls.append(node)
        assert imports.isdisjoint(forbidden)
        assert not any(isinstance(call.func, ast.Name) and call.func.id in {"exec", "eval", "open"} for call in calls)


def test_registry_defers_non_delian_runtime_mappings():
    registry = json.loads((PHASE_ROOT / "mapping_registry.json").read_text())
    assert registry["deferred"]["djedaini"] == {"status": "NATIVE_REPRODUCTION_BLOCKED_STRUCTURAL", "executable_mapping": None}
    assert registry["deferred"]["assess"] == {"status": "RELEASE_1_0_0_TESTCLASSES_PASS_WITH_EXACT_SOURCE_DEPENDENCY_RECONSTRUCTION", "runtime_mapping": None}
