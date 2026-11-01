"""Tests for xlint.py — markdown fences."""

import sys,tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
sys.path.insert(0, str(REPO))

import xtest
from tools.xlint import xlint

def messages(problems):
	return sorted(item[-1] for item in problems)

def fenced(lines):
	return xlint.check_space_indent_exempt(lines, xlint._fence_exempt(lines))

# --- TestMarkdownFences ---

"""A fence is a fence wherever it sits, per QN1N82Y.

The spec this reverses said an indented fence line stays a violation. The cost was
that a fence nested in a list item could never be lint-clean, and the only remedy
was to edit inside the code block — `agent-notes-a4.md` had its content converted
to tabs to dodge the check.
"""

def test_a_top_level_fence_exempts_its_space_indented_body():
	xtest.equal(fenced(["```json", '  {"a": 1}', "```"]), [])

def test_a_fence_nested_in_a_list_item_is_a_fence():
	lines = ["1. Do the thing:", "", "\t```sh", "\t  echo hi", "\t```"]
	xtest.equal(fenced(lines), [])

def test_a_fence_nested_two_deep_is_a_fence():
	lines = ["1. Outer:", "", "\t1. Inner:", "", "\t\t```python", "\t\tx = 1", "\t\t```"]
	xtest.equal(fenced(lines), [])

def test_a_four_space_indented_code_block_is_still_reported():
	# What the rule was really for: Markdown's indented-code syntax requires spaces,
	# so a space-indented line opening no fence is the signal, and it survives.
	xtest.equal(messages(fenced(["    echo hi"])), ["indented with spaces"])

def test_a_tilde_fence_nested_in_a_list_item_is_a_fence():
	lines = ["1. Item:", "", "\t~~~python", "\tx = 1", "\t~~~"]
	xtest.equal(fenced(lines), [])

def test_prose_indented_with_spaces_is_still_reported():
	xtest.equal(messages(fenced(["text", "  more text"])), ["indented with spaces"])

def test_a_backtick_fence_is_not_closed_by_tildes():
	lines = ["1. Item:", "", "\t```sh", "\t~~~", "\t  echo hi", "\t```"]
	xtest.equal(fenced(lines), [])

def test_frontmatter_is_still_exempt():
	lines = ["---", "key:   value", "---", "body"]
	xtest.equal(xlint.check_space_indent_exempt(lines, xlint._frontmatter_exempt(lines)), [])
