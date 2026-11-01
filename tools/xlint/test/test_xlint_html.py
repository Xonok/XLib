"""Tests for xlint.py — html."""

import argparse,sys,tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
sys.path.insert(0, str(REPO))

import xtest
from tools.xlint import _html,xlint

def messages(problems):
	return sorted(item[-1] for item in problems)

def html_messages(lines, rule):
	"""The messages one html rule reports, so a test asserts on a rule and not on the file."""
	return messages(_html.check_html(lines)[rule])

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

def _messages(text):
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "sample.html"
		path.write_text(text, encoding="utf-8")
		return messages(xlint.check_file(path, _every_check_on()))

# --- TestHtmlTags ---

"""Every non-void tag is closed, and a closer that should not be there is reported.

The rules are the ones the human ruled on 2026-10-19 (epi `YFJZRYC`): the
unclosed rule is strict, and a closing tag that should not be there is a
finding in all three of its readings.
"""

def test_a_well_formed_document_is_clean():
	lines = ["<html>", "\t<body>", "\t\t<div>text</div>", "\t</body>", "</html>"]
	xtest.equal(html_messages(lines, "unclosed"), [])
	xtest.equal(html_messages(lines, "bad_closer"), [])

def test_an_unclosed_tag_is_reported_at_the_line_it_was_opened():
	lines = ["<div>", "\t<span>text</span>"]
	xtest.equal(html_messages(lines, "unclosed"), ["unclosed tag <div>"])

def test_a_void_element_needs_no_closer():
	# The one reading of "every tag is closed" that is not a rule: a void
	# element has no end.
	lines = ["<div>", "\t<br>", "</div>"]
	xtest.equal(html_messages(lines, "unclosed"), [])
	xtest.equal(html_messages(lines, "bad_closer"), [])

def test_a_closer_for_a_void_element_is_reported():
	lines = ["<div>", "\t</br>", "</div>"]
	xtest.equal(html_messages(lines, "bad_closer"), ["closing tag </br> for a void element"])

def test_a_closer_with_no_matching_open_is_reported():
	lines = ["<div>text</div>", "</span>"]
	xtest.equal(html_messages(lines, "bad_closer"), ["closing tag </span> with no matching open tag"])

def test_a_closer_that_does_not_match_the_innermost_open_is_reported():
	# The `</div>` closes the div and the span on the way, so the `</span>`
	# after it is a closer with no matching open: two findings, two problems.
	lines = ["<div>", "\t<span>", "\t</div>", "\t</span>"]
	xtest.equal(html_messages(lines, "bad_closer"), ["closing tag </div> does not match the open <span>", "closing tag </span> with no matching open tag"])

def test_a_mis_nested_closer_closes_what_it_names():
	# The elements above the match are closed on the way, so they are not
	# reported as unclosed as well: one problem, one finding.
	lines = ["<div>", "\t<span>", "\t</div>"]
	xtest.equal(html_messages(lines, "bad_closer"), ["closing tag </div> does not match the open <span>"])
	xtest.equal(html_messages(lines, "unclosed"), [])

def test_a_commented_out_tag_opens_and_closes_nothing():
	# The trap the corpus holds: a file with sixty lines of commented-out
	# markup, where a tokenizer that reads the comment as markup reports
	# dozens of unclosed tags that are not there.
	lines = ["<div>", "\t<!-- <span> -->", "\t<!-- </span> -->", "\t<span>text</span>", "</div>"]
	xtest.equal(html_messages(lines, "unclosed"), [])
	xtest.equal(html_messages(lines, "bad_closer"), [])

def test_the_content_of_a_script_is_text_not_markup():
	lines = ["<script>", "\tif (a < b) { c(\"</div>\"); }", "</script>"]
	xtest.equal(html_messages(lines, "unclosed"), [])
	xtest.equal(html_messages(lines, "bad_closer"), [])

def test_a_bracket_inside_a_quoted_attribute_does_not_end_the_tag():
	lines = ["<a title=\"a > b\">text</a>"]
	xtest.equal(html_messages(lines, "unclosed"), [])
	xtest.equal(html_messages(lines, "bad_closer"), [])

def test_a_doctype_is_not_a_tag():
	lines = ["<!DOCTYPE html>", "<html>", "</html>"]
	xtest.equal(html_messages(lines, "unclosed"), [])
	xtest.equal(html_messages(lines, "bad_closer"), [])

# --- TestHtmlDepth ---

"""A line sits at the depth the nesting gives it, measured in the file's own unit."""

def test_a_document_at_the_right_depth_is_clean():
	lines = ["<html>", "\t<body>", "\t\t<div>", "\t\t\t<span>text</span>", "\t\t</div>", "\t</body>", "</html>"]
	xtest.equal(html_messages(lines, "depth"), [])

def test_a_line_one_level_too_deep_is_reported():
	lines = ["<html>", "\t<body>", "\t\t<div>", "\t\t\t\t<span>text</span>", "\t\t</div>", "\t</body>", "</html>"]
	xtest.equal(html_messages(lines, "depth"), ["indentation depth mismatch: expected 3, got 4"])

def test_a_closing_tag_one_level_too_shallow_is_reported():
	# What the corpus's own main.html has: two closers at the same depth
	# where the inner belongs one deeper. No tabs-versus-spaces rule sees it.
	lines = ["<div>", "\t<div>", "</div>", "</div>"]
	xtest.equal(html_messages(lines, "depth"), ["indentation depth mismatch: expected 1, got 0"])

def test_the_depth_is_measured_in_the_file_own_unit():
	# A space-indented file is measured in its own spaces: counting tabs
	# there reports a depth where the real finding is the unit.
	lines = ["<div>", "    <span>", "        <em>text</em>", "    </span>", "</div>"]
	xtest.equal(html_messages(lines, "depth"), [])

def test_a_space_indented_file_at_the_wrong_depth_is_reported():
	lines = ["<div>", "    <span>text</span>", "        <em>text</em>", "</div>"]
	xtest.equal(html_messages(lines, "depth"), ["indentation depth mismatch: expected 1, got 2"])

def test_a_line_of_text_is_not_placed_by_the_nesting():
	# The prose in an element is written at the element's own level or one
	# deeper, and the nesting does not say which.
	lines = ["<p>", "text", "</p>"]
	xtest.equal(html_messages(lines, "depth"), [])

def test_a_commented_out_block_is_not_placed_by_the_nesting():
	lines = ["<div>", "\t<!-- <span>", "\t\t\tcommented out markup", "\t-->", "\t<span>text</span>", "</div>"]
	xtest.equal(html_messages(lines, "depth"), [])

# --- TestHtmlFiles ---

"""An .html file is routed to the html rules, and the flags switch them off."""

def test_a_clean_html_file_is_clean():
	xtest.equal(_messages("<div>\n\t<span>text</span>\n</div>\n"), [])

def test_an_unclosed_tag_is_reported():
	xtest.equal(_messages("<div>\n</div>\n<span>text\n"), ["unclosed tag <span>"])

def test_a_space_indented_html_file_is_reported():
	xtest.equal(_messages("<div>\n    <span>text</span>\n</div>\n"), ["indented with spaces"])

def test_the_html_flags_switch_the_html_rules_off():
	flags = _every_check_on()
	flags.no_html_unclosed = True
	flags.no_html_depth = True
	flags.no_html_space_indent = True
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "sample.html"
		path.write_text("<div>\n    <span>text</span>\n", encoding="utf-8")
		xtest.equal(messages(xlint.check_file(path, flags)), [])

def test_lint_files_finds_html_files():
	with tempfile.TemporaryDirectory() as folder:
		(Path(folder) / "sample.html").write_text("<div></div>\n", encoding="utf-8")
		found = xlint.lint_files([Path(folder)])
		xtest.equal([path.name for path in found], ["sample.html"])
