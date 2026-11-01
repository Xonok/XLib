"""Tests for xlint.py — banned git."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
sys.path.insert(0, str(REPO))

import xtest
from tools.xlint import xlint

def messages(problems):
	return sorted(item[-1] for item in problems)

# --- TestBannedGit ---

"""Banned git commands must not appear in a tracked file.

The working-tree rules forbid `git checkout`, `git reset --hard` and
`git reset --merge`. The check is the durable half of that ban: a command
written into a tracked file is copy-pasted again, so it is flagged.
"""

def test_git_checkout_is_reported():
	problems = xlint._banned_git.check(["git " + "checkout foo"])
	xtest.equal(len(problems), 1)

def test_git_reset_hard_is_reported():
	problems = xlint._banned_git.check(["git " + "reset --hard"])
	xtest.equal(len(problems), 1)

def test_git_reset_merge_is_reported():
	problems = xlint._banned_git.check(["git " + "reset --merge"])
	xtest.equal(len(problems), 1)

def test_a_clean_file_is_clean():
	xtest.equal(xlint._banned_git.check(["git switch foo", "git restore bar"]), [])

def test_one_finding_per_line():
	problems = xlint._banned_git.check(["git " + "checkout a", "git " + "checkout b"])
	xtest.equal(len(problems), 2)
