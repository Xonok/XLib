"""Tests for xlint.py — absolute paths."""

import subprocess,sys,tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
sys.path.insert(0, str(REPO))

import xtest
from tools.xlint import xlint

def messages(problems):
	return sorted(item[-1] for item in problems)

# --- TestAbsolutePaths ---

"""The rule is that a tracked file must not carry one machine's layout.

`check_absolute_paths` ran in the Markdown branch only, so a tracked `.py`
file could name this machine's path and the linter would say nothing — which
is how `tools/tool_schema_cache.py:14` carried one for months.
"""

def test_a_machine_path_is_reported():
	problems = xlint.check_absolute_paths(['x = "/home/someone/x"'], set(), "a.py")
	xtest.equal(len(problems), 1)

def test_a_storage_path_is_reported():
	problems = xlint.check_absolute_paths(['x = "/storage/GitHub/Fun/XLib/a.py"'], set(), "a.py")
	xtest.equal(len(problems), 1)

def test_a_home_relative_path_is_not_reported():
	# `~/` is the portable form: correct on every machine, where
	# `/home/someone/...` is correct on one.
	lines = ['x = os.path.expanduser("~/.local/share/taskview")']
	xtest.equal(xlint.check_absolute_paths(lines, set(), "a.py"), [])

def test_no_tracked_python_file_carries_a_machine_path():
	# The end-to-end version, over the repository's own files. The check
	# only runs on tracked files, so a temporary file cannot stand in for
	# one — and the defect it exists for was a tracked file.
	root = Path(__file__).resolve().parents[3]
	names = subprocess.run(["git", "ls-files", "*.py"], cwd=str(root),
		capture_output=True, text=True).stdout.split()
	offenders = []
	for name in names:
		lines = (root / name).read_text(encoding="utf-8").splitlines()
		exempt = xlint._python_string_lines(lines) - xlint._python_docstring_lines(lines)
		if xlint.check_absolute_paths(lines, exempt, name):
			offenders.append(name)
	xtest.equal(offenders, [], f"tracked .py files naming a machine path: {offenders}")
