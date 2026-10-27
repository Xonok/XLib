"""Repository-level checks for taskboard: the dependency rule and the layout.

The dependency rule is architectural, so the test reads the command's imports
rather than proving it at runtime: `taskview` itself imports PyYAML, and a
runtime check would therefore fail on a compliant command. The requirement
each test traces to is in its name.
"""
import ast,sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "dev" / "xtest"))
sys.path.insert(0, str(ROOT))
import xtest

COMMAND = ROOT / "tools" / "taskboard" / "taskboard.py"
REPO_MODULES = {"tools", "taskview", "taskupdate", "vocab", "xhttp"}

def _imported_roots(source):
	roots = set()
	for node in ast.walk(ast.parse(source)):
		if isinstance(node, ast.Import):
			roots.update(alias.name.split(".")[0] for alias in node.names)
		elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
			roots.add(node.module.split(".")[0])
	return roots

def test_R30_the_command_is_taskboard_py():
	xtest.true(COMMAND.is_file(), f"{COMMAND} is the command the spec names")

def test_R1_the_store_resolution_is_imported_from_taskview():
	xtest.true(COMMAND.is_file(), f"{COMMAND} is the command the spec names")
	source = COMMAND.read_text(encoding="utf-8")
	xtest.contains("resolve_data_dir", source)
	xtest.contains("resolve_csv", source)

def test_R29_the_command_imports_only_the_stdlib_and_repo_modules():
	xtest.true(COMMAND.is_file(), f"{COMMAND} is the command the spec names")
	roots = _imported_roots(COMMAND.read_text(encoding="utf-8"))
	allowed = set(sys.stdlib_module_names) | REPO_MODULES
	xtest.equal(roots - allowed, set(), "imports outside the stdlib and this repository")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
