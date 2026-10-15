#!/usr/bin/env python3
"""
Tests for `statements(text)` — D1, D16 and the field names proposed in the
second pass-1 review.

Run with: python3 -m unittest tools.pybundle.test.test_bundler_source -v

**Two of these field names are mine, not the spec's.** The human settled that the
entries are dictionaries and asked for names to be proposed; these are the
proposal, and they are documented as such in `doc/reviews/pybundle-tests-pass1-2.md`
so they get written back into the spec:

- `text` — the statement's source text, its first line's indentation included,
  and no trailing newline.
- `indent` — that same leading whitespace, as a string. D2 compares by column,
  which is what the tokenizer's own INDENT and DEDENT tokens give.

Everything else here counts entries rather than reading fields, because counting
is derivable from D16 saying the return is a list, and reading a field is not.
"""

import unittest
from tools.pybundle.bundler_source import statements

class TestStatementShapeD16(unittest.TestCase):
	"""D16, as amended: a list of dictionaries."""

	def test_statements_is_a_list(self):
		self.assertIsInstance(statements("a = 1\n"), list)

	def test_each_statement_is_a_dictionary(self):
		self.assertIsInstance(statements("a = 1\n")[0], dict)

	def test_a_statement_carries_its_text(self):
		self.assertEqual(statements("a = 1\n")[0]["text"], "a = 1")

	def test_a_statement_carries_the_indentation_of_its_first_line(self):
		self.assertEqual(statements("if True:\n\tcount = 1\n")[1]["indent"], "\t")

	def test_a_statement_at_the_left_margin_has_no_indentation(self):
		self.assertEqual(statements("a = 1\n")[0]["indent"], "")

	def test_the_text_of_a_multiline_statement_carries_every_line(self):
		# R7 — the text is unchanged, so all of it is kept.
		self.assertEqual(statements("a = {\n\t1: 2,\n}\n")[0]["text"], "a = {\n\t1: 2,\n}")

	def test_the_indent_of_a_multiline_statement_is_its_first_line(self):
		# D1 — "Indentation is taken from the first physical line."
		self.assertEqual(statements("if True:\n\ta = [\n\t\t1,\n\t]\n")[1]["indent"], "\t")

class TestStatementBoundariesD1(unittest.TestCase):
	"""D1: a statement is a logical line, not a physical one."""

	def test_two_separate_lines_are_two_statements(self):
		self.assertEqual(len(statements("a = 1\nb = 2\n")), 2)

	def test_a_single_line_is_one_statement(self):
		self.assertEqual(len(statements("a = 1\n")), 1)

	def test_the_final_newline_does_not_open_a_statement(self):
		self.assertEqual(len(statements("a = 1")), 1)

	def test_a_dict_literal_spanning_lines_is_one_statement(self):
		self.assertEqual(len(statements("a = {\n\t1: 2,\n}\n")), 1)

	def test_a_list_literal_spanning_lines_is_one_statement(self):
		self.assertEqual(len(statements("a = [\n\t1,\n\t2,\n]\n")), 1)

	def test_a_multiline_string_is_one_statement(self):
		self.assertEqual(len(statements('a = """\ndef b():\n\tpass\n"""\n')), 1)

	def test_a_function_header_and_its_body_are_two_statements(self):
		self.assertEqual(len(statements("if True:\n\ta = 1\n")), 2)

	def test_a_backslash_continuation_is_one_statement(self):
		self.assertEqual(len(statements("a = 1 + \\\n\t2\n")), 1)

class TestNonCodeLinesAreKeptD18(unittest.TestCase):
	"""R7, settled: an empty line and a comment-only line are carried through.
	They do not change what a statement *is* — they are not bound names and they
	do not open blocks — so nothing here counts them."""

	def test_a_comment_is_present_in_the_statement_text(self):
		texts = [statement["text"] for statement in statements("a = 1\n# keep me\n")]
		self.assertIn("# keep me", texts)

	def test_an_empty_line_is_present_in_the_statement_text(self):
		texts = [statement["text"] for statement in statements("a = 1\n\nb = 2\n")]
		self.assertIn("", texts)

	def test_a_comment_line_carries_no_indentation_of_its_own(self):
		texts = [statement["text"] for statement in statements("a = 1\n\t# indented note\n")]
		self.assertIn("\t# indented note", texts)

class TestEmptyInput(unittest.TestCase):
	"""An edge of the contract that the fixtures above never reach."""

	def test_empty_text_is_no_statements(self):
		self.assertEqual(len(statements("")), 0)

if __name__ == "__main__":
	unittest.main()
