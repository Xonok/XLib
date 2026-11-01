"""Tests for xlint.py — trailing blank lines."""

import argparse,sys,tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
sys.path.insert(0, str(REPO))

import xtest
from tools.xlint import xlint

def messages(problems):
	return sorted(item[-1] for item in problems)

def _every_check_on():
	"""The CLI's default state, as `check_file` sees it.

	Named explicitly rather than read off the parser, so that adding a flag without
	deciding what Markdown does with it fails here instead of passing quietly.
	"""
	flags = [
		"no_double_blank", "no_space_indent", "no_trailing", "no_def_one_line",
		"no_def_comment", "no_final_newline", "no_imports", "no_double_space",
		"no_absolute_paths", "no_js_double_blank", "no_js_space_indent",
		"no_js_trailing", "no_js_final_newline", "no_html_double_blank",
		"no_html_space_indent", "no_html_trailing", "no_html_final_newline",
		"no_html_unclosed", "no_html_bad_closer", "no_html_depth",
		"no_personal", "no_leading_blank", "no_banned_git",
	]
	return argparse.Namespace(**{flag: False for flag in flags})

# --- TestTrailingBlankLine ---

"""A file ends with exactly one newline, after real content — the other half of BX56XRY.

Neither existing check covered this: `import os\\n\\n` has the final newline, and has
no double blank line, so both passed. Together the pair was meant to state one rule
and stated two halves of it without either.
"""

def test_one_trailing_blank_line_is_reported():
	problems = xlint.check_trailing_blank(["import os", ""])
	xtest.equal(messages(problems), ["trailing blank line at end of file"])

def test_no_trailing_blank_line_is_clean():
	xtest.equal(xlint.check_trailing_blank(["import os"]), [])

def test_two_trailing_blank_lines_are_left_to_the_double_blank_check():
	# One finding per file, naming one problem: naming both at the same lines is noise.
	xtest.equal(xlint.check_trailing_blank(["import os", "", ""]), [])

def test_a_whitespace_only_file_is_clean():
	# The three pybundle fixtures that are a single newline are bundler input, not
	# a file that happens to end in a blank line.
	xtest.equal(xlint.check_trailing_blank([""]), [])

def test_an_empty_file_is_clean():
	xtest.equal(xlint.check_trailing_blank([]), [])

def test_a_trailing_blank_line_keeps_the_final_newline_check_passing():
	# The pair has to be read together, so this is the input that used to slip past both.
	lines = ["import os\n", "\n"]
	xtest.equal(xlint.check_final_newline(lines), [])
	xtest.equal(messages(xlint.check_trailing_blank(["import os", ""])), ["trailing blank line at end of file"])

# --- TestBlankLinesAtEndOfFile ---

"""What a file ends with is checked the same way whatever language it is in, per 4JMY5S0.

`check_trailing_blank` hands a pair of trailing blank lines to the double-blank
check on purpose, so one file yields one finding rather than two. The Markdown
branch of `check_file` never made that call, so a Markdown file ending in two
blank lines was reported by neither: the warning vanished the moment a second
blank line was added, while the same file in Python or JavaScript was reported.

These drive `check_file` rather than the check functions, because every check
function was individually correct and the defect was in which ones a Markdown
file is routed to. A test of `check_double_blank` alone passes either way.
"""

def _messages(text, suffix=".md"):
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / ("sample" + suffix)
		path.write_text(text, encoding="utf-8")
		return messages(xlint.check_file(path, _every_check_on()))

def test_a_single_trailing_newline_is_clean():
	xtest.equal(_messages("content\n"), [])

def test_one_trailing_blank_line_is_reported():
	xtest.equal(_messages("content\n\n"), ["trailing blank line at end of file"])

def test_two_trailing_blank_lines_are_reported():
	xtest.equal(_messages("content\n\n\n"), ["double blank line"])

def test_a_missing_final_newline_is_reported():
	xtest.equal(_messages("content"), ["missing final newline"])

def test_two_trailing_blank_lines_are_reported_in_markdown():
	xtest.equal(_messages("content\n\n\n", ".md"), ["double blank line"])

def test_two_trailing_blank_lines_are_reported_in_python():
	xtest.equal(_messages("content\n\n\n", ".py"), ["double blank line"])

def test_two_trailing_blank_lines_are_reported_in_javascript():
	xtest.equal(_messages("content\n\n\n", ".js"), ["double blank line"])
