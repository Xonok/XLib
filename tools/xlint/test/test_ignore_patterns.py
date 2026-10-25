"""The `.xlintignore` pattern language, and the globstar's place in it.

`**` was compiled to a piece that already ended in a separator, and the pieces
were then joined with another one, so a globstar in the middle of a pattern
(`a/**/b`) became `a/(?:.*/)?/b` and matched nothing. An exclusion that matches
nothing is the quietest failure the tool has: the tree it was meant to spare is
linted, and the file saying what to spare is the only thing that looks right.

These tests pin the language a pattern is written in, not only the pattern that
exposed the defect: a leading, middle and trailing globstar each match whole
segments, zero or more of them, and a negation still overrides.
"""
import sys,tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
sys.path.insert(0, str(REPO))

import xtest
from tools.xlint import xlint

def _exclusions(folder, text):
	"""One `.xlintignore` in a fresh checkout, and the rules loaded from it."""
	root = Path(folder)
	(root / ".xlintignore").write_text(text, encoding="utf-8")
	return xlint._Exclusions([root]), root

def test_a_middle_globstar_matches_zero_segments():
	with tempfile.TemporaryDirectory() as folder:
		rules, root = _exclusions(folder, "a/**/b/\n")
		xtest.true(xlint.is_ignored(root / "a" / "b" / "code.py", rules),
			"a/**/b/ excludes a/b/ itself")

def test_a_middle_globstar_matches_one_segment():
	with tempfile.TemporaryDirectory() as folder:
		rules, root = _exclusions(folder, "a/**/b/\n")
		xtest.true(xlint.is_ignored(root / "a" / "x" / "b" / "code.py", rules),
			"a/**/b/ excludes a/x/b/")

def test_a_middle_globstar_matches_nested_segments():
	with tempfile.TemporaryDirectory() as folder:
		rules, root = _exclusions(folder, "a/**/b/\n")
		xtest.true(xlint.is_ignored(root / "a" / "x" / "y" / "b" / "code.py", rules),
			"a/**/b/ excludes a/x/y/b/")

def test_a_middle_globstar_does_not_exclude_a_sibling():
	with tempfile.TemporaryDirectory() as folder:
		rules, root = _exclusions(folder, "a/**/b/\n")
		xtest.equal(xlint.is_ignored(root / "a" / "x" / "c" / "code.py", rules), False,
			"a/**/b/ leaves a/x/c/ alone")

def test_a_leading_globstar_matches_a_directory_at_the_root():
	with tempfile.TemporaryDirectory() as folder:
		rules, root = _exclusions(folder, "**/state/\n")
		xtest.true(xlint.is_ignored(root / "state" / "model.py", rules),
			"**/state/ excludes state/")

def test_a_leading_globstar_matches_a_directory_below_one():
	with tempfile.TemporaryDirectory() as folder:
		rules, root = _exclusions(folder, "**/state/\n")
		xtest.true(xlint.is_ignored(root / "run" / "state" / "model.py", rules),
			"**/state/ excludes run/state/")

def test_a_trailing_globstar_matches_everything_below_the_directory():
	with tempfile.TemporaryDirectory() as folder:
		rules, root = _exclusions(folder, "a/**\n")
		xtest.true(xlint.is_ignored(root / "a" / "x" / "code.py", rules),
			"a/** excludes a/x/code.py")

def test_a_trailing_globstar_does_not_reach_a_sibling():
	with tempfile.TemporaryDirectory() as folder:
		rules, root = _exclusions(folder, "a/**\n")
		xtest.equal(xlint.is_ignored(root / "b" / "code.py", rules), False,
			"a/** leaves b/ alone")

def test_the_retained_run_state_pattern_matches_its_directory_at_any_depth():
	# The pattern the Agents workspace writes for the retained benchmark output:
	# `library/ai/models/traces/**/state/`. It used to compile to nothing.
	with tempfile.TemporaryDirectory() as folder:
		rules, root = _exclusions(folder, "library/ai/models/traces/**/state/\n")
		xtest.true(xlint.is_ignored(
			root / "library" / "ai" / "models" / "traces" / "run-1" / "state" / "model.py",
			rules), "the pattern excludes a run's retained state")

def test_a_negation_after_a_middle_globstar_re_includes_the_named_directory():
	with tempfile.TemporaryDirectory() as folder:
		rules, root = _exclusions(folder, "a/**/b/\n!a/keep/b/\n")
		xtest.equal(xlint.is_ignored(root / "a" / "keep" / "b" / "code.py", rules), False,
			"the later rule puts a/keep/b/ back in scope")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
