#!/usr/bin/env python3
"""
Tests for `renamed(name, prefix)` and `translate(statements, renames, resolved)`
— R3, D3, D16, D22.

Run with: python3 -m unittest tools.pybundle.test.test_bundler_names -v

`renamed` is the only pure function in the set — D4 calls it that, and "the one
most worth testing on its own" — so its tests are direct by choice. `translate`
joins the suite now that D16 fixes its return: a single string, statements joined
with newlines, no trailing newline.

**`renamed` prefixes whatever it is given, including a name that already carries a
prefix.** D20's exemption is for the rebind statements `translate` emits, which
are written out after the rename pass rather than translated by it, so putting the
exemption in `renamed` would break a name that genuinely starts with its own
prefix. That is what `test_name_carrying_an_existing_prefix_is_prefixed_again`
pins, and it is why D20's rebind-LHS tests live in `test_bundler.py`: they need a
`resolved` value, and D8 fixes what `imports` returns without naming the fields.

Only the cases needing no filesystem are here; everything that does is driven
through `main` in `test_bundler.py`, because R1.2 makes locality a question about
location on disk.
"""

import unittest
from tools.pybundle.bundler_names import renamed,translate
from tools.pybundle.bundler_source import statements

class TestPrefixApplied(unittest.TestCase):
	"""R3: a file's globals are prefixed with its path below the root folder."""

	def test_global_name_gets_the_file_prefix(self):
		self.assertEqual(renamed("run", "helper__"), "helper__run")

	def test_nested_path_prefix_is_flattened_with_double_underscore(self):
		self.assertEqual(renamed("run", "py__command__api__"), "py__command__api__run")

	def test_name_carrying_an_existing_prefix_is_prefixed_again(self):
		self.assertEqual(renamed("helper__run", "client__"), "client__helper__run")

class TestRootIsTheEmptyPrefix(unittest.TestCase):
	"""D3: the root exception is one expression, and renaming is its identity."""

	def test_empty_prefix_returns_the_name_unchanged(self):
		self.assertEqual(renamed("run", ""), "run")

	def test_empty_prefix_moves_leading_underscores_to_a_no_op(self):
		self.assertEqual(renamed("_run", ""), "_run")

class TestLeadingUnderscores(unittest.TestCase):
	"""R3: leading underscores move in front of the prefix, so a private name
	still reads as private in the bundle."""

	def test_single_leading_underscore_moves_in_front_of_the_prefix(self):
		self.assertEqual(renamed("_foo", "helper__"), "_helper__foo")

	def test_two_leading_underscores_both_move_in_front(self):
		self.assertEqual(renamed("__foo", "helper__"), "_helper____foo")

	def test_three_leading_underscores_all_move_in_front(self):
		self.assertEqual(renamed("___foo", "helper__"), "___helper__foo")

	def test_name_of_only_underscores_keeps_them_all_in_front(self):
		self.assertEqual(renamed("___", "helper__"), "___helper__")

	def test_underscore_inside_the_name_is_left_where_it_is(self):
		self.assertEqual(renamed("foo_bar", "helper__"), "helper__foo_bar")

class TestPrefixBeginningWithAnUnderscore(unittest.TestCase):
	"""R3: a prefix that begins with an underscore already carries the private
	marker, so the name keeps its own underscores behind it. Moving them in
	front would produce `__types__foo`, which python reads as class-private
	inside a class body and mangles."""

	def test_private_name_keeps_its_underscore_behind_the_prefix(self):
		self.assertEqual(renamed("_foo", "_types__"), "_types___foo")

	def test_public_name_is_unchanged_by_the_rule(self):
		self.assertEqual(renamed("foo", "_types__"), "_types__foo")

class TestNonAsciiNames(unittest.TestCase):
	"""A non-ASCII name is an ordinary python identifier, so it renames like
	any other."""

	def test_non_ascii_name_gets_the_prefix(self):
		self.assertEqual(renamed("функция", "helper__"), "helper__функция")

class TestTranslateD16(unittest.TestCase):
	"""D16: `translate` returns one string — statements joined with newlines, and
	no trailing newline. `inline` composes the comments and separators around it.

	`resolved` is empty in every test here, which is what `imports` returns for a
	file that has no imports.
	"""

	def test_statements_come_back_joined_by_newlines(self):
		result = translate(statements("a = 1\nb = 2\n"), {}, [])
		self.assertEqual(result, "a = 1\nb = 2")

	def test_no_trailing_newline_is_added(self):
		result = translate(statements("a = 1\n"), {}, [])
		self.assertFalse(result.endswith("\n"))

	def test_a_name_in_the_rename_table_is_replaced(self):
		result = translate(statements("count = 1\n"), {"count": "helper__count"}, [])
		self.assertEqual(result, "helper__count = 1")

	def test_a_name_absent_from_the_rename_table_is_left_alone(self):
		result = translate(statements("count = 1\n"), {}, [])
		self.assertEqual(result, "count = 1")

	def test_indentation_of_a_statement_is_kept(self):
		result = translate(statements("if True:\n\tcount = 1\n"), {}, [])
		self.assertEqual(result, "if True:\n\tcount = 1")

if __name__ == "__main__":
	unittest.main()
