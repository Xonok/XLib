#!/usr/bin/env python3
"""
Tests for the enforced structure — R6 and D4.

Run with: python3 -m unittest tools.pybundle.test.test_bundler_structure -v

SPEC.md's goal section says structure is a requirement here and not an
implementation preference, so these tests read the sources rather than the
behaviour. They are the only tests in the suite that do: a source test is only
worth writing where the spec has forbidden or named something.
"""

import re,sys,unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pybundle import bundler,bundler_imports,bundler_names,bundler_source

PACKAGE = ROOT / "tools" / "pybundle"
MODULES = sorted(PACKAGE.glob("*.py"))
ENTRY = "bundler.py"
PLACEMENT = {
	"statements": "bundler_source.py",
	"imports": "bundler_imports.py",
	"renamed": "bundler_names.py",
	"translate": "bundler_names.py",
	"inline": "bundler.py",
	"main": "bundler.py",
}

def _imports(module_name, imported_name):
	"""True when a module carries an import statement naming that module."""
	source = (PACKAGE / module_name).read_text(encoding="utf-8")
	pattern = re.compile(rf"^\s*(?:import\s+{imported_name}\b|from\s+\S+\s+import\s+.*\b{imported_name}\b)")
	return any(pattern.match(line) for line in source.splitlines())

def _placement():
	"""The file each public function of the set is defined in."""
	found = {}
	for module in (bundler, bundler_imports, bundler_names, bundler_source):
		for name in dir(module):
			if name.startswith("_"):
				continue
			value = getattr(module, name)
			if callable(value) and getattr(value, "__module__", "").startswith("tools.pybundle"):
				found[name] = Path(value.__module__).name
	return found

class TestNoParseTreeR6(unittest.TestCase):
	"""R6.1: import detection, scope detection and definition scanning are
	statement-based, and `ast` is not used."""

	def test_no_module_of_the_bundler_imports_ast(self):
		offenders = [path.name for path in MODULES if _imports(path.name, "ast")]
		self.assertEqual(offenders, [])

class TestEntryModuleIsImportedByNothingR6(unittest.TestCase):
	"""R6.3: the bundler's own modules do not import the entry file."""

	def test_only_the_entry_module_imports_the_other_modules(self):
		offenders = [path.name for path in MODULES if path.name != ENTRY and _imports(path.name, "bundler")]
		self.assertEqual(offenders, [])

class TestFunctionPlacementD4(unittest.TestCase):
	"""D4: six functions, each in the file the table names."""

	def test_each_function_of_the_set_lives_in_the_file_the_table_names(self):
		placement = _placement()
		self.assertEqual({name: placement.get(name) for name in PLACEMENT}, PLACEMENT)

if __name__ == "__main__":
	unittest.main()
