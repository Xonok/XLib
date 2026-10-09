#!/usr/bin/env python3
"""
Tests for xlint.py — the checks, not the CLI.

Run with: python3 -m unittest tools.xlint.test.test_xlint -v

xlint had no test file at all until DDRBHD5, and the gap was not cosmetic:
`check_imports` could demand a merge that cannot be written, and nothing noticed,
because a rule that is wrong on every input it ever saw looks exactly like a rule
that is right. The unsatisfiable input below is the case that pinned it.

The checks take a list of lines (without newlines, as `str.splitlines` gives them)
and return `(line_number, message)` pairs, so a test is a list in and a verdict out.
No file is written and no process is started, which is what keeps these fast enough
to run on every edit.
"""

import unittest
from tools.xlint import xlint

def messages(problems):
	"""The messages alone, so a test asserts on what is reported and not on its order."""
	return sorted(message for _, message in problems)

class TestPlainImports(unittest.TestCase):
	"""Plain imports are comma-joined; dotted and aliased names each get their own line."""

	def test_consecutive_plain_imports_are_reported_as_unmerged(self):
		problems = xlint.check_imports(["import json", "import collections"])
		self.assertEqual(messages(problems), ["consecutive plain imports not merged"])

	def test_merged_plain_imports_are_clean(self):
		self.assertEqual(xlint.check_imports(["import json,collections"]), [])

	def test_an_aliased_import_is_not_reported_as_unmerged(self):
		problems = xlint.check_imports(["import json", "import math as m"])
		self.assertEqual(problems, [])

	def test_a_plain_import_after_an_aliased_one_is_clean(self):
		problems = xlint.check_imports(["import math as m", "import collections"])
		self.assertEqual(problems, [])

	def test_an_aliased_import_does_not_propagate_to_the_next_line(self):
		# The input DDRBHD5 is about: with the old classifier, lines 2 and 3 were both
		# reported and no rewrite made the file clean. The alias breaks the plain run,
		# so only the genuine pair before it survives.
		problems = xlint.check_imports(["import json", "import collections", "import math as m"])
		self.assertEqual(messages(problems), ["consecutive plain imports not merged"])

	def test_an_aliased_import_between_two_plain_ones_breaks_the_run(self):
		problems = xlint.check_imports(["import json", "import math as m", "import collections"])
		self.assertEqual(problems, [])

	def test_an_aliased_dotted_import_is_clean(self):
		self.assertEqual(xlint.check_imports(["import json", "import a.b as c"]), [])

	def test_an_alias_sharing_a_line_with_other_names_is_reported(self):
		problems = xlint.check_imports(["import json,math as m"])
		self.assertEqual(messages(problems), ["aliased import on a shared line"])

class TestFromImports(unittest.TestCase):
	"""Names from one module are comma-joined; the module's own name carries the check."""

	def test_two_imports_from_the_same_module_are_reported(self):
		problems = xlint.check_imports(["from util import ping", "from util import connect"])
		self.assertEqual(messages(problems), ["same module imported on separate lines"])

	def test_merged_names_from_one_module_are_clean(self):
		self.assertEqual(xlint.check_imports(["from util import connect,ping"]), [])

	def test_a_space_after_a_comma_is_reported(self):
		problems = xlint.check_imports(["from util import connect, ping"])
		self.assertEqual(messages(problems), ["space after comma in import"])

	def test_a_wildcard_import_is_reported(self):
		self.assertEqual(messages(xlint.check_imports(["from util import *"])), ["wildcard import"])

class TestImportBlocks(unittest.TestCase):
	"""The block-level rules: one statement per line, no blank line inside the block."""

	def test_a_blank_line_between_imports_is_reported(self):
		problems = xlint.check_imports(["import json", "", "import collections"])
		self.assertEqual(messages(problems), ["blank line between imports"])

	def test_two_statements_on_one_line_are_reported(self):
		problems = xlint.check_imports(["import json; import collections"])
		self.assertEqual(messages(problems), ["multiple statements on one line"])

	def test_a_dotted_name_is_clean_beside_a_plain_one(self):
		self.assertEqual(xlint.check_imports(["import json", "import os.path"]), [])

class TestOneLineDefinition(unittest.TestCase):
	"""The three states of a `def` signature, which the check used to conflate into one.

	1YPFZYH measured 74 findings in this repo, every one of them a single-line `def`
	carrying a trailing comment: a 100% false-positive rate in the check enforcing the
	signature houserule, all of it invisible because those files sit in a `test/` folder
	that AK633QC covers.
	"""

	def test_a_trailing_comment_is_not_a_spill(self):
		# The whole of 1YPFZYH: `def ok(a, b):` is on one line whatever follows the colon.
		self.assertEqual(xlint.check_def_one_line(["def ok(a, b):  # why", "\treturn a"]), [])

	def test_a_plain_single_line_definition_is_clean(self):
		self.assertEqual(xlint.check_def_one_line(["def ok(a, b):", "\treturn a"]), [])

	def test_an_async_single_line_definition_is_clean(self):
		self.assertEqual(xlint.check_def_one_line(["async def ok(a):", "\treturn a"]), [])

	def test_the_permitted_multiline_shape_is_clean(self):
		lines = ["def ok(", "\talpha,", "\tbeta,", "):", "\treturn alpha"]
		self.assertEqual(xlint.check_def_one_line(lines), [])

	def test_the_permitted_shape_nests_by_one_tab_inside_a_class(self):
		lines = ["class C:", "\tdef ok(", "\t\talpha,", "\t):", "\t\treturn alpha"]
		self.assertEqual(xlint.check_def_one_line(lines), [])

	def test_a_spill_aligned_to_the_open_paren_is_reported(self):
		# The shape the ruling bans: alignment breaks when a parameter is renamed.
		lines = ["def ok(alpha,", "\t\tbeta):", "\treturn alpha"]
		self.assertEqual(messages(xlint.check_def_one_line(lines)), ["function definition split across lines"])

	def test_two_arguments_on_one_line_inside_a_spill_are_reported(self):
		lines = ["def ok(", "\talpha, beta,", "):", "\treturn alpha"]
		self.assertEqual(messages(xlint.check_def_one_line(lines)), ["function definition split across lines"])

	def test_a_permitted_shape_whose_closing_paren_is_misindented_is_reported(self):
		lines = ["def ok(", "\talpha,", "\t\t):", "\treturn alpha"]
		self.assertEqual(messages(xlint.check_def_one_line(lines)), ["function definition split across lines"])

	def test_a_spilled_return_annotation_is_a_spill(self):
		# The rule is that the definition stays on one line, so a header whose return
		# annotation wraps is split across lines whatever the shape of its parameters.
		lines = ["def ok(a) -> dict[", "\tstr,", "\tint,", "]:", "\treturn {}"]
		self.assertEqual(messages(xlint.check_def_one_line(lines)), ["function definition split across lines"])

	def test_an_unparseable_file_falls_back_to_the_text_check(self):
		# ast is unavailable for a file mid-edit; the rule still has to hold, and a
		# trailing comment still must not read as a spill.
		lines = ["def ok(a, b):  # why", "\treturn a", "def broken("]
		self.assertEqual(messages(xlint.check_def_one_line(lines)), ["function definition split across lines"])

	def test_a_paren_inside_a_default_string_is_not_a_signature_end(self):
		self.assertEqual(xlint.check_def_one_line(["def ok(pattern=r')'):", "\treturn pattern"]), [])

if __name__ == "__main__":
	unittest.main()
