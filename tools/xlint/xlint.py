#!/usr/bin/env python3
"""xlint — the repository's style checker.

Package entry point and public API. The implementation lives in the
sibling modules; this file is the orchestrator: it makes the package
importable both as a module and when run directly, imports each sibling
once, and re-exposes the public (non-underscore) API through wrapper
functions so their parameters are visible here. Private helpers stay
accessible via their submodules (e.g. xlint._io._libc).
"""

import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
	sys.path.insert(0, str(_here))

if __package__ is None:
	_repo_root = str(Path(__file__).resolve().parents[2])
	if _repo_root not in sys.path:
		sys.path.insert(0, _repo_root)
	__package__ = "tools.xlint"

# Sibling modules, imported once (private; access their public names via wrappers below).
from . import _io,_checks,_markdown,_python,_js,_html,_personal,_banned_git,_c,_watch,_cli,_repo_rules

# Public constants.
NAME = _io.NAME

# Public API: wrapper functions with explicit parameters.
def find_exclusion_chain(start):
	return _io.find_exclusion_chain(start)

def find_exclusion_roots(start):
	return _io.find_exclusion_roots(start)

def find_checkout_root(start):
	return _io.find_checkout_root(start)

def exclusion_reason(path, exclusions=None):
	return _io.exclusion_reason(path, exclusions)

def is_ignored(path, exclusions=None):
	return _io.is_ignored(path, exclusions)

def excluded_paths(paths, exclusions=None):
	return _io.excluded_paths(paths, exclusions)

def lint_files(paths, exclusions=None):
	return _io.lint_files(paths, exclusions)

def stamp(path):
	return _io.stamp(path)

def check_double_blank(lines):
	return _checks.check_double_blank(lines)

def check_space_indent(lines):
	return _checks.check_space_indent(lines)

def check_space_indent_exempt(lines, exempt):
	return _checks.check_space_indent_exempt(lines, exempt)

def check_trailing_whitespace(lines, is_md=False):
	return _checks.check_trailing_whitespace(lines, is_md)

def check_double_space(lines, is_py):
	return _checks.check_double_space(lines, is_py)

def check_absolute_paths(lines, exempt_lines, path):
	return _checks.check_absolute_paths(lines, exempt_lines, path)

def check_trailing_blank(lines):
	return _checks.check_trailing_blank(lines)

def check_final_newline(lines):
	return _checks.check_final_newline(lines)

def check_leading_blank(lines):
	return _checks.check_leading_blank(lines)

def check_file(path, args):
	return _checks.check_file(path, args)

def check_def_one_line(lines):
	return _python.check_def_one_line(lines)

def check_def_comment(lines):
	return _python.check_def_comment(lines)

def check_imports(lines):
	return _python.check_imports(lines)

def check_js_trailing_whitespace(lines):
	return _js.check_js_trailing_whitespace(lines)

def check_js_double_blank(lines):
	return _js.check_js_double_blank(lines)

def check_js_space_indent(lines, exempt):
	return _js.check_js_space_indent(lines, exempt)

def check_js_final_newline(lines):
	return _js.check_js_final_newline(lines)

def check_js_trailing_blank(lines):
	return _js.check_js_trailing_blank(lines)

def make_watcher(rules):
	return _watch.make_watcher(rules)

def draw(snapshot, skipped=(), notices=(), repo=(), error=None, output=None):
	return _watch.draw(snapshot, skipped, notices, repo, error, output)

def watch(rules, args):
	return _watch.watch(rules, args)

def main():
	return _cli.main()

if __name__ == "__main__":
	sys.exit(main())
