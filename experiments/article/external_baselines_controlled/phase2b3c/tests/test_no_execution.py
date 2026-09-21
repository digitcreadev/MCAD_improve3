import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_python_has_no_execution_facilities():
    forbidden_imports = {"subprocess", "socket", "requests", "urllib", "http", "docker", "pymysql", "mysql", "sqlalchemy"}
    forbidden_calls = {"system", "popen", "exec", "eval", "compile"}
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [n.name.split(".")[0] for n in node.names] if isinstance(node, ast.Import) else [(node.module or "").split(".")[0]]
                assert forbidden_imports.isdisjoint(names), (path, names)
            if isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
                assert name not in forbidden_calls, (path, name)


def test_only_contract_artifacts_exist():
    suffixes = {p.suffix for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    assert suffixes <= {".md", ".json", ".py"}
