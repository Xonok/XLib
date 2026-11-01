"""Tests for xlint.py — exclusions."""

import contextlib,io,sys,tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
sys.path.insert(0, str(REPO))

import xtest
from tools.xlint import xlint

def messages(problems):
	return sorted(item[-1] for item in problems)

def _worktree(folder):
	"""An outer repository holding one worktree, and the two paths that matter."""
	outer = Path(folder) / "outer"
	work = outer / ".work" / "ticket"
	work.mkdir(parents=True)
	(outer / ".git").mkdir()
	(outer / ".xlintignore").write_text(".work/\n", encoding="utf-8")
	(work / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
	return outer, work

# --- TestExclusions ---

"""The per-repo `.xlintignore` file and the built-in defaults, per AK633QC."""

def test_builtin_defaults_exclude_vendored_directories():
	# The four "not our code" names are hard-coded.
	xtest.true(xlint.is_ignored(Path("__pycache__/x.py")))
	xtest.true(xlint.is_ignored(Path(".git/config")))
	xtest.true(xlint.is_ignored(Path("node_modules/x.py")))
	xtest.true(xlint.is_ignored(Path("xlib_legacy/x.py")))

def test_test_is_no_longer_a_builtin_exclusion():
	# The bug: "test" was in the built-in set, so every test/ folder was skipped.
	# The ruling drops it; tests must be linted like any other code.
	xtest.true(not xlint.is_ignored(Path("test/x.py")))
	xtest.true(not xlint.is_ignored(Path("tools/taskview/test/x.py")))

def test_xlintignore_excludes_fixtures_and_scratch():
	# The repo's .xlintignore explicitly excludes the pybundle fixtures and .agents/.
	excl = xlint._Exclusions(xlint.find_exclusion_roots(Path(".")))
	xtest.true(xlint.is_ignored(Path("tools/pybundle/test/fixtures/alias/main.py"), excl))
	xtest.true(xlint.is_ignored(Path("tools/pybundle/test/fixtures/alias/util.py"), excl))
	xtest.true(xlint.is_ignored(Path(".agents/agent-notes-x.md"), excl))
	xtest.true(xlint.is_ignored(Path(".work/xlint-improvements/xlint.py"), excl))

def test_xlintignore_does_not_exclude_siblings():
	# A pattern for a directory excludes that directory and its contents, but
	# not its siblings.
	excl = xlint._Exclusions(xlint.find_exclusion_roots(Path(".")))
	xtest.true(xlint.is_ignored(Path("tools/pybundle/test/fixtures"), excl))
	xtest.true(not xlint.is_ignored(Path("tools/taskview/test/x.py"), excl))

def test_lint_files_respects_xlintignore():
	# Explicit file arguments also respect the exclusion file.
	excl = xlint._Exclusions(xlint.find_exclusion_roots(Path(".")))
	xtest.equal(xlint.lint_files([Path("tools/pybundle/test/fixtures/alias/main.py")], excl), [])
	xtest.equal(xlint.lint_files([Path(".agents/agent-notes-x.md")], excl), [])
	# But a non-excluded file is returned.
	found = xlint.lint_files([Path("tools/xlint/xlint.py")], excl)
	xtest.equal(len(found), 1)

def test_lint_files_directory_walk_skips_ignored():
	# Walking a directory skips ignored subtrees entirely. The fixtures directory
	# is ignored, but other files in the same parent are not.
	excl = xlint._Exclusions(xlint.find_exclusion_roots(Path(".")))
	found = xlint.lint_files([Path("tools/pybundle/test/fixtures")], excl)
	xtest.equal(found, [])

# --- TestWorktreeExclusions ---

"""A worktree is a separate checkout of the same repository, not a subdirectory of it.

The defect these pin: the outer repository's `.xlintignore` lists the worktrees it
contains, the rule reached into the worktree, and every file in it was excluded. A
lint run there checked nothing and said `clean`.
"""

def test_the_ignore_walk_stops_at_the_checkout_that_owns_the_path():
	# The outer repository's ignore file does not govern the worktree's contents.
	with tempfile.TemporaryDirectory() as folder:
		outer, work = _worktree(folder)
		xtest.equal(xlint.find_exclusion_roots(work), [])
		xtest.equal(xlint.find_exclusion_roots(outer), [outer])

def test_a_worktree_keeps_its_own_ignore_file():
	# The worktree holds its own copy of the ignore file, and that copy is the one
	# that applies to it.
	with tempfile.TemporaryDirectory() as folder:
		outer, work = _worktree(folder)
		(work / ".xlintignore").write_text("scratch/\n", encoding="utf-8")
		excl = xlint._Exclusions(xlint.find_exclusion_roots(work))
		xtest.true(xlint.is_ignored(work / "scratch" / "note.py", excl))
		xtest.true(not xlint.is_ignored(work / "code.py", excl))

def test_the_files_in_a_worktree_are_linted():
	# The bug itself: the run over a worktree found nothing and reported clean.
	with tempfile.TemporaryDirectory() as folder:
		outer, work = _worktree(folder)
		(work / "code.py").write_text("x = 1\n", encoding="utf-8")
		excl = xlint._Exclusions(xlint.find_exclusion_roots(work))
		found = xlint.lint_files([work], excl)
		xtest.equal([path.name for path in found], ["code.py"])

def test_the_outer_repository_still_excludes_the_worktrees_it_holds():
	# The rule keeps its purpose from the other side: the worktrees the outer
	# repository contains are not linted twice.
	with tempfile.TemporaryDirectory() as folder:
		outer, work = _worktree(folder)
		excl = xlint._Exclusions(xlint.find_exclusion_roots(outer))
		xtest.true(xlint.is_ignored(work / "code.py", excl))
		xtest.true(not xlint.is_ignored(outer / "code.py", excl))

# --- TestExcludedPaths ---

"""A run that checks nothing must not look like a run that found nothing."""

def test_an_excluded_path_is_reported_with_the_rule_that_excluded_it():
	excl = xlint._Exclusions(xlint.find_exclusion_roots(Path(".")))
	skipped = xlint.excluded_paths([Path(".agents/agent-notes-x.md")], excl)
	xtest.equal([str(path) for path, reason in skipped], [".agents/agent-notes-x.md"])
	xtest.equal([reason for path, reason in skipped], [".xlintignore"])

def test_a_path_that_is_not_excluded_is_not_reported():
	excl = xlint._Exclusions(xlint.find_exclusion_roots(Path(".")))
	xtest.equal(xlint.excluded_paths([Path("tools/xlint/xlint.py")], excl), [])

def test_a_run_that_checks_nothing_does_not_say_clean():
	out = io.StringIO()
	with contextlib.redirect_stdout(out):
		xlint.draw({}, skipped=[(Path("."), ".xlintignore")])
	xtest.contains("nothing checked", out.getvalue())
	xtest.not_contains("clean", out.getvalue())

def test_a_run_that_finds_nothing_still_says_clean():
	out = io.StringIO()
	with contextlib.redirect_stdout(out):
		xlint.draw({})
	xtest.contains("clean", out.getvalue())
