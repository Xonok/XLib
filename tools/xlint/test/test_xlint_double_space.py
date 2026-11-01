"""Tests for xlint.py — double space."""

import sys,tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
sys.path.insert(0, str(REPO))

import xtest
from tools.xlint import xlint

def messages(problems):
	return sorted(item[-1] for item in problems)

# --- TestDoubleSpace ---

"""A mid-line double space is a typo — whether Python or Markdown.

The check uses tokenize for Python (exempting string literals and comments) and
regex for Markdown (exempting fenced code, frontmatter, and inline code spans).
The ruling is general: any mid-line double space is a typo outside exempt content.
"""

def test_python_double_space_between_tokens_is_reported():
	problems = xlint.check_double_space(["x = 1  + 2"], True)
	xtest.equal(messages(problems), ["mid-line double space"])

def test_python_double_space_in_string_is_exempt():
	xtest.equal(xlint.check_double_space(['s = "a  b"'], True), [])

def test_python_double_space_in_comment_is_exempt():
	# The double space INSIDE the comment is exempt; the one before the comment
	# is a violation (aligned comments are bad taste per BSFQYPF).
	problems = xlint.check_double_space(["x = 1  # comment  here"], True)
	xtest.equal(len(problems), 1)
	xtest.equal(problems[0][1], "mid-line double space")

def test_python_multiple_double_spaces_are_reported():
	# One finding per line, like all other checks.
	problems = xlint.check_double_space(["x = 1  +  2"], True)
	xtest.equal(len(problems), 1)

def test_markdown_double_space_in_prose_is_reported():
	problems = xlint.check_double_space(["Sentence one.  Sentence two."], False)
	xtest.equal(messages(problems), ["mid-line double space"])

def test_markdown_double_space_in_fenced_code_is_exempt():
	problems = xlint.check_double_space(["```", "x = 1  + 2", "```"], False)
	xtest.equal(problems, [])

def test_markdown_double_space_in_frontmatter_is_exempt():
	problems = xlint.check_double_space(["---", "key:  value", "---"], False)
	xtest.equal(problems, [])

def test_markdown_double_space_in_inline_code_is_exempt():
	problems = xlint.check_double_space(["Use `x  y` here."], False)
	xtest.equal(problems, [])

def test_markdown_table_alignment_is_reported():
	problems = xlint.check_double_space(["| a  | b |", "| --- | --- |", "| 1  | 2 |"], False)
	xtest.equal(messages(problems), ["mid-line double space", "mid-line double space"])

def test_python_aligned_comments_are_reported():
	# BSFQYPF removes the aligned-comment exemption; a lone inline comment
	# on ordinary code is a violation.
	problems = xlint.check_double_space(["x = 1  # why"], True)
	xtest.equal(messages(problems), ["mid-line double space"])
