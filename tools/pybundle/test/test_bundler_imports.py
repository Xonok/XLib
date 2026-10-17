#!/usr/bin/env python3
"""
Tests for `imports(statements, modpath, root)` — D8, D16 and D20.

Run with: python3 -m unittest tools.pybundle.test.test_bundler_imports -v

D8 fixes what an entry carries — the statement, its kind, its targets, whether it
was relative — and D16 fixed the *other* leaf's two field names but not these four.
So every test here counts entries and nothing reads a field: the count is fixed by
D8's "**one entry per import statement, in source order**" and by D16's
"**every import statement yields an entry**", and both are observable without
inventing a name. Source *order* is not observable this way, and is left to the
block-order assertions in `test_bundler.py`.

**Why this file exists at all.** The suite is split by module, `imports` is the one
function in D12's table that no file tested directly, and its return shape is the
one the spec fixes most concretely — so the count it mandates was untested.
"""

import tempfile,unittest
from pathlib import Path
from tools.pybundle.bundler_imports import imports
from tools.pybundle.bundler_source import statements

class ImportsTestCase(unittest.TestCase):
	"""A throwaway folder, so local and non-local are questions about disk."""

	MODPATH = "client"

	def setUp(self):
		tmpdir = tempfile.TemporaryDirectory()
		self.addCleanup(tmpdir.cleanup)
		self.root = Path(tmpdir.name)

	def write(self, name, text):
		(self.root / name).write_text(text, encoding="utf-8", newline="")

	def resolve(self, source, modpath=None):
		"""`imports` over `source`, as a file at `modpath` in the throwaway folder."""
		modpath = self.MODPATH if modpath is None else modpath
		return imports(statements(source), modpath, str(self.root))

class TestOneEntryPerStatement(unittest.TestCase):
	"""D8's headline and D16's resolved ambiguity: *every* import statement yields
	an entry, so a non-local one yields something to be left in place rather than
	nothing to leave."""

	def test_a_file_with_no_imports_yields_no_entries(self):
		self.assertEqual(imports(statements("count = 1\n"), "client", "."), [])

	def test_two_import_statements_yield_two_entries(self):
		self.assertEqual(len(imports(statements("import os\nimport sys\n"), "client", ".")), 2)

	def test_a_mixed_statement_is_one_entry_and_not_one_per_target(self):
		# `import os, sys` is one statement with two targets. D8's mixed-statement
		# rule is stated per statement, so the count follows the statement too.
		self.assertEqual(len(imports(statements("import os, sys\n"), "client", ".")), 1)

	def test_a_non_local_statement_still_yields_an_entry(self):
		# D16 — the ambiguity D8 left was whether a non-local statement yields an
		# entry or nothing. It yields one; what happens to it is D20's business.
		result = imports(statements("import os\n"), "client", "/nonexistent-root")
		self.assertEqual(len(result), 1)

class TestLocalStatementsAreCounted(ImportsTestCase):
	"""The same count, for the statements the bundler acts on: an inlined module's
	statement is removed (D8), so an entry is what tells `translate` to remove it."""

	def test_a_local_module_import_yields_one_entry(self):
		self.write("helper.py", "count = 1\n")
		self.assertEqual(len(self.resolve("import helper\n")), 1)

	def test_a_name_import_yields_one_entry(self):
		# D20 turned `from x import name` from a reported error into supported
		# syntax, so its statement yields an entry like any other import's.
		self.write("helper.py", "count = 1\n")
		self.assertEqual(len(self.resolve("from helper import count\n")), 1)

	def test_a_star_import_yields_one_entry(self):
		self.write("helper.py", "count = 1\n")
		self.assertEqual(len(self.resolve("from helper import *\n")), 1)

	def test_a_relative_import_yields_one_entry(self):
		# D8 requires the entry to record that a statement was relative, because
		# D15's RELATIVE_IMPORT_IN_ROOT check reads that flag. The flag's field name
		# is unfixed, so only the count is pinned here.
		self.write("sub/api.py", "count = 1\n")
		result = imports(statements("from . import api\n"), "sub/client", str(self.root))
		self.assertEqual(len(result), 1)

if __name__ == "__main__":
	unittest.main()
