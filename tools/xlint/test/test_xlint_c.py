"""Tests for xlint.py — C language."""

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

def _messages(text, suffix=".c"):
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / ("sample" + suffix)
		path.write_text(text, encoding="utf-8")
		return messages(xlint.check_file(path, _every_check_on()))

# --- TestCLanguage ---

"""C and header files carry the shared whitespace checks, under the generic flags."""

def test_a_leading_blank_line_is_reported():
	xtest.contains("empty line at start of file", _messages("\nint x;\n"))

def test_a_clean_file_is_clean():
	xtest.equal(_messages("int x;\n"), [])

def test_a_double_blank_line_is_reported():
	xtest.contains("double blank line", _messages("int x;\n\n\nint y;\n"))

def test_trailing_whitespace_is_reported():
	xtest.contains("trailing whitespace", _messages("int x; \n"))

def test_a_missing_final_newline_is_reported():
	xtest.contains("missing final newline", _messages("int x;"))

def test_a_header_file_is_linted():
	xtest.contains("empty line at start of file", _messages("\nint x;\n", ".h"))
