#!/usr/bin/env python3
"""xlint — the repository's style checker.

Package entry point and public API. The implementation lives in the
sibling modules; this file is the orchestrator: it makes the package
importable both as a module and when run directly, imports each sibling
once, and re-exposes the public (non-underscore) API through wrapper
functions so their parameters are visible here. Private helpers stay
accessible via their submodules (e.g. xlint._io._libc).
"""

import argparse,signal,sys
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
from . import _io,_checks,_markdown,_python,_js,_html,_personal,_banned_git,_c,_watch,_repo_rules
_finding_text = _watch._finding_text
_finding_key = _watch._finding_key
_write_output = _watch._write_output

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
	parser = argparse.ArgumentParser(description="Check Python, Markdown, JavaScript/TypeScript, HTML and C files against XLib style rules")
	parser.add_argument("paths", nargs="*", type=Path, default=[Path(".")])
	parser.add_argument("--watch", action="store_true", help="stay running, redraw the issue list when files change")
	parser.add_argument("--output", "-o", type=Path, default=None, metavar="FILE", help="write the report to FILE (empty when clean)")
	parser.add_argument("--no-repo-rules", action="store_true", help="do not load the checkout's repo rules")
	parser.add_argument("--no-double-blank", action="store_true", help="disable double blank line check")
	parser.add_argument("--no-space-indent", action="store_true", help="disable space indentation check")
	parser.add_argument("--no-trailing", action="store_true", help="disable trailing whitespace check")
	parser.add_argument("--no-def-one-line", action="store_true", help="disable one-line function definition check")
	parser.add_argument("--no-def-comment", action="store_true", help="disable the check for a comment on a def line")
	parser.add_argument("--no-final-newline", action="store_true", help="disable final newline and trailing blank line checks")
	parser.add_argument("--no-leading-blank", action="store_true", help="disable the empty-leading-line check")
	parser.add_argument("--no-imports", action="store_true", help="disable import style check")
	parser.add_argument("--no-double-space", action="store_true", help="disable mid-line double space check")
	parser.add_argument("--no-absolute-paths", action="store_true", help="disable absolute system path check in Markdown")
	parser.add_argument("--no-personal", action="store_true", help="disable the personal identifier check in tracked files")
	parser.add_argument("--no-banned-git", action="store_true", help="disable the banned git command check in tracked files")
	parser.add_argument("--no-js-double-blank", action="store_true", help="disable JS/TS double blank line check")
	parser.add_argument("--no-js-space-indent", action="store_true", help="disable JS/TS space indentation check")
	parser.add_argument("--no-js-trailing", action="store_true", help="disable JS/TS trailing whitespace check")
	parser.add_argument("--no-js-final-newline", action="store_true", help="disable JS/TS final newline and trailing blank line checks")
	parser.add_argument("--no-html-double-blank", action="store_true", help="disable html double blank line check")
	parser.add_argument("--no-html-space-indent", action="store_true", help="disable html space indentation check")
	parser.add_argument("--no-html-trailing", action="store_true", help="disable html trailing whitespace check")
	parser.add_argument("--no-html-final-newline", action="store_true", help="disable html final newline and trailing blank line checks")
	parser.add_argument("--no-html-unclosed", action="store_true", help="disable the html unclosed tag check")
	parser.add_argument("--no-html-bad-closer", action="store_true", help="disable the html closing tag check")
	parser.add_argument("--no-html-depth", action="store_true", help="disable the html indentation depth check")
	args = parser.parse_args()

	for entry in args.paths:
		if not entry.exists():
			parser.error(f"not found: {entry}")

	rules = _repo_rules._Rules(args.paths, repo_rules = not args.no_repo_rules)
	_repo_rules._apply_disabled_to_args(args, rules)
	skipped = rules.skipped()

	if args.watch:
		signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
		try:
			_watch.watch(rules, args)
		except KeyboardInterrupt:
			pass
		return 0

	files = rules.files()
	try:
		repo = rules.repo_problems(files)
	except _repo_rules._RepoRuleError as error:
		print(f"{NAME}: {error}", file = sys.stderr)
		return 1
	problems = []
	for path in files:
		for line, rule, msg in check_file(path, args):
			problems.append((path, line, rule, msg))
	for entry, reason in skipped:
		print(f"{entry}: excluded by {reason} — nothing checked")
	if not problems and not repo:
		print("nothing checked" if skipped else "clean")
		if args.output is not None:
			_write_output(args.output, "")
		return 0
	ordered = sorted(problems + repo, key=_finding_key)
	for path, line, rule, msg in ordered:
		print(_finding_text(path, line, msg, rule))
	print(f"{len(problems) + len(repo)} problem(s)")
	if args.output is not None:
		_write_output(args.output, "".join(_finding_text(path, line, msg, rule) + "\n" for path, line, rule, msg in ordered))
	return 1

if __name__ == "__main__":
	sys.exit(main())
