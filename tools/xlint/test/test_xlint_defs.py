"""Tests for xlint.py — the checks, not the CLI (definitions)."""

import sys,tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
sys.path.insert(0, str(REPO))

import xtest
from tools.xlint import xlint

def messages(problems):
	return sorted(item[-1] for item in problems)

# --- TestOneLineDefinition ---

"""The three states of a `def` signature, which the check used to conflate into one.

1YPFZYH measured 74 findings in this repo, every one of them a single-line `def`
carrying a trailing comment: a 100% false-positive rate in the check enforcing the
signature houserule, all of it invisible because those files sit in a `test/` folder
that AK633QC covers.
"""

def test_a_trailing_comment_is_not_a_spill():
	# The whole of 1YPFZYH: `def ok(a, b):` is on one line whatever follows the colon.
	xtest.equal(xlint.check_def_one_line(["def ok(a, b):  # why", "\treturn a"]), [])

def test_a_plain_single_line_definition_is_clean():
	xtest.equal(xlint.check_def_one_line(["def ok(a, b):", "\treturn a"]), [])

def test_an_async_single_line_definition_is_clean():
	xtest.equal(xlint.check_def_one_line(["async def ok(a):", "\treturn a"]), [])

def test_the_permitted_multiline_shape_is_clean():
	lines = ["def ok(", "\talpha,", "\tbeta,", "):", "\treturn alpha"]
	xtest.equal(xlint.check_def_one_line(lines), [])

def test_the_permitted_shape_nests_by_one_tab_inside_a_class():
	lines = ["class C:", "\tdef ok(", "\t\talpha,", "\t):", "\t\treturn alpha"]
	xtest.equal(xlint.check_def_one_line(lines), [])

def test_a_spill_aligned_to_the_open_paren_is_reported():
	# The shape the ruling bans: alignment breaks when a parameter is renamed.
	lines = ["def ok(alpha,", "\t\tbeta):", "\treturn alpha"]
	xtest.equal(messages(xlint.check_def_one_line(lines)), ["function definition split across lines"])

def test_two_arguments_on_one_line_inside_a_spill_are_reported():
	lines = ["def ok(", "\talpha, beta,", "):", "\treturn alpha"]
	xtest.equal(messages(xlint.check_def_one_line(lines)), ["function definition split across lines"])

def test_a_permitted_shape_whose_closing_paren_is_misindented_is_reported():
	lines = ["def ok(", "\talpha,", "\t\t):", "\treturn alpha"]
	xtest.equal(messages(xlint.check_def_one_line(lines)), ["function definition split across lines"])

def test_a_spilled_return_annotation_is_a_spill():
	# The rule is that the definition stays on one line, so a header whose return
	# annotation wraps is split across lines whatever the shape of its parameters.
	lines = ["def ok(a) -> dict[", "\tstr,", "\tint,", "]:", "\treturn {}"]
	xtest.equal(messages(xlint.check_def_one_line(lines)), ["function definition split across lines"])

def test_an_unparseable_file_reports_nothing():
	# When the file has a SyntaxError, ast.parse fails and we cannot reliably
	# distinguish real function definitions from ones inside strings/comments.
	# The fallback regex approach was buggy (it triggered on strings/comments
	# and on valid functions after an unmatched quote). Skip the check instead.
	lines = ["def ok(a, b):  # why", "\treturn a", "def broken("]
	xtest.equal(messages(xlint.check_def_one_line(lines)), [])

def test_a_paren_inside_a_default_string_is_not_a_signature_end():
	xtest.equal(xlint.check_def_one_line(["def ok(pattern=r')'):", "\treturn pattern"]), [])

# --- TestDefLineComment ---

"""A comment on a `def` or `class` line is its own finding, per HRCQSV4.

It was previously reported as a split signature, which 1YPFZYH fixed — so the 74
sites it names are now reported under a name that means what it says. The fix is
different too: the comment moves up a line, rather than the signature joining up.
"""

def test_a_comment_on_a_def_line_is_reported():
	problems = xlint.check_def_comment(["def ok(a, b):  # why", "\treturn a"])
	xtest.equal(messages(problems), ["comment on a def line"])

def test_a_comment_on_a_class_line_is_reported():
	# Never checked before: the one-line check's regex matches `def` and `async def`
	# only, so no class line had ever been examined.
	problems = xlint.check_def_comment(["class C(Base):  # why", "\tpass"])
	xtest.equal(messages(problems), ["comment on a def line"])

def test_a_comment_on_the_line_above_a_def_is_clean():
	xtest.equal(xlint.check_def_comment(["# why", "def ok(a, b):", "\treturn a"]), [])

def test_a_hash_inside_a_string_on_a_def_line_is_not_a_comment():
	# `f"  #{name}"` is report layout, and no comment was written on that line.
	lines = ["def render(name):", '\treturn f"  #{name}"']
	xtest.equal(xlint.check_def_comment(lines), [])

def test_a_comment_on_an_ordinary_code_line_is_clean():
	xtest.equal(xlint.check_def_comment(["x = 1  # why"]), [])

def test_an_unparseable_file_reports_nothing():
	# Unlike the signature check this one has no text fallback: deciding whether a
	# line is a `def` needs the parse, and guessing is what produced the 74.
	xtest.equal(xlint.check_def_comment(["def ok(a):  # why", "\treturn a", "def broken("]), [])
