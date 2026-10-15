#!/usr/bin/env python3
"""
Tests for `renamed(name, prefix)` — R3, D3.

Run with: python3 -m unittest tools.pybundle.test.test_bundler_names -v

`renamed` is the only function in the set whose signature and return the spec
fixes exactly — D4 calls it "the only pure function" and "the one most worth
testing on its own" — so it is the only one tested directly here. Everything
else is tested through the bundle `main` produces, in `test_bundler.py`,
because the shapes the other three functions hand back are not settled by the
spec (flaws F1-F3 in `doc/reviews/pybundle-tests-pass1.md`).
"""

import unittest
from tools.pybundle.bundler_names import renamed

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

class TestNonAsciiNames(unittest.TestCase):
	"""A non-ASCII name is an ordinary python identifier, so it renames like
	any other."""

	def test_non_ascii_name_gets_the_prefix(self):
		self.assertEqual(renamed("функция", "helper__"), "helper__функция")

if __name__ == "__main__":
	unittest.main()
