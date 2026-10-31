import argparse,ast,contextlib,ctypes,errno,importlib.util,io,itertools,os,re,select,signal,struct,sys,tempfile,termios,time,tokenize,tomllib,types,subprocess
from pathlib import Path
try:
	from ._io import *
except ImportError:
	from _io import *
try:
	from ._checks import check_file
except ImportError:
	from _checks import check_file
try:
	from ._watch import watch, _finding_text, _finding_key, _write_output
except ImportError:
	from _watch import watch, _finding_text, _finding_key, _write_output
try:
	from ._repo_rules import _Rules, _apply_disabled_to_args, _RepoRuleError
except ImportError:
	from _repo_rules import _Rules, _apply_disabled_to_args, _RepoRuleError
def main():
	parser = argparse.ArgumentParser(description="Check Python, Markdown, JavaScript/TypeScript and HTML files against XLib style rules")
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

	rules = _Rules(args.paths, repo_rules = not args.no_repo_rules)
	_apply_disabled_to_args(args, rules)
	skipped = rules.skipped()

	if args.watch:
		signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
		try:
			watch(rules, args)
		except KeyboardInterrupt:
			pass
		return 0

	files = rules.files()
	try:
		repo = rules.repo_problems(files)
	except _RepoRuleError as error:
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

__all__ = ['main']
