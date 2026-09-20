import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
ADAPTERS = ROOT / "adapters"
FORBIDDEN_IMPORTS = {"docker", "psycopg", "psycopg2", "pymssql", "pyodbc", "requests", "subprocess"}
PROTECTED_FRAGMENTS = (
    "frozen_campaigns",
    "run_baselines_and_ablations.py",
    "bi-stack/mcad-proxy/execution/adapters",
)


def test_adapter_code_has_no_external_execution_imports_or_protected_paths():
    for path in ADAPTERS.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert imported.isdisjoint(FORBIDDEN_IMPORTS)
        assert all(fragment not in source for fragment in PROTECTED_FRAGMENTS)


def test_tests_contain_no_workload_launch_primitives():
    for path in Path(__file__).parent.glob("test_*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        assert calls.isdisjoint({"system", "popen", "run", "call", "check_call", "check_output"})
