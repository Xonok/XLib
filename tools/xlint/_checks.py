import argparse,ast,contextlib,ctypes,errno,importlib.util,io,itertools,os,re,select,signal,struct,sys,tempfile,termios,time,tokenize,tomllib,types,subprocess
from pathlib import Path
try:
	from ._io import *
except ImportError:
	from _io import *
try:
	from . import _html, _personal, _banned_git
except ImportError:
	import _html, _personal, _banned_git
try:
	from ._python import *
except ImportError:
	from _python import *
try:
	from ._markdown import *
except ImportError:
	from _markdown import *
try:
	from ._js import *
except ImportError:
	from _js import *
try:
	from ._repo_rules import _disabled_canonical
except ImportError:
	from _repo_rules import _disabled_canonical
def check_double_blank(lines):
	report = []
	for index, (prev, current) in enumerate(zip(lines, lines[1:]), start=2):
		if prev == "" and current == "":
			report.append((index, "double blank line"))
	return report
def check_space_indent(lines):
	report = []
	for index, line in enumerate(lines, start=1):
		if _SPACE_INDENT_RE.match(line):
			report.append((index, "indented with spaces"))
	return report
def check_space_indent_exempt(lines, exempt):
	report = []
	for index, line in enumerate(lines, start=1):
		if index in exempt:
			continue
		if _SPACE_INDENT_RE.match(line):
			report.append((index, "indented with spaces"))
	return report
def check_trailing_whitespace(lines, is_md=False):
	report = []
	for index, line in enumerate(lines, start=1):
		if line != line.rstrip() and line.strip():
			trailing = len(line) - len(line.rstrip())
			if is_md and trailing == 2:
				# Markdown hard break: two trailing spaces is intentional <br>
				continue
			report.append((index, "trailing whitespace"))
	return report
def check_double_space(lines, is_py):
	"""Report a mid-line double space — two or more spaces between non-space characters.

	Exempt regions are skipped:
	- Python: string literals and comments (via tokenize)
	- Markdown: fenced code, frontmatter, inline code spans (backtick-delimited)

	The ruling is general: any mid-line double space is a typo unless it lives in
	exempt content. The BSFQYPF ruling removes the aligned-comment exemption,
	so aligned comment columns are now violations.
	"""
	report = []
	if is_py:
		exempt = _python_exempt_spans(lines)
	else:
		exempt = _markdown_exempt_spans(lines)
	for index, line in enumerate(lines, start=1):
		spans = exempt.get(index, [])
		if spans:
			# Replace each exempt span with a single non-space placeholder
			# This prevents double spaces from forming or hiding at the boundary
			# between exempt and non-exempt content.
			chars = list(line)
			for start, end in sorted(spans, reverse=True):
				chars[start:end] = ["·"]
			line = "".join(chars)
		if _DOUBLE_SPACE_RE.search(line):
			report.append((index, "mid-line double space"))
	return report
def _line_has_double_space(line, spans):
	"""True when `line` contains a mid-line double space outside `spans`.

	`spans` is a list of (start, end) column pairs that are exempt.
	The check is done on the non-exempt segments only.
	"""
	if not spans:
		return _DOUBLE_SPACE_RE.search(line) is not None
	spans = sorted(spans)
	last = 0
	for start, end in spans:
		if start > last:
			segment = line[last:start]
			if _DOUBLE_SPACE_RE.search(segment):
				return True
		last = end
	if last < len(line):
		segment = line[last:]
		if _DOUBLE_SPACE_RE.search(segment):
			return True
	return False
def check_absolute_paths(lines, exempt_lines, path):
	"""Report absolute system paths in tracked Markdown files.

	Flags tokens starting with `/storage/`, `/home/<user>/` or `/root/` that
	are not in exempt lines. **`~/` is not flagged**: the rule is that a
	tracked file must not carry *one machine's* layout, and `~/` is the
	portable form — `os.path.expanduser("~/.local/share/taskview")` is correct
	on every machine, while `/home/someone/...` is correct on one. Flagging
	`~/` would have meant rewriting correct code to point at a machine-info
	file, which is a rule that makes the code worse.

	Known exempt paths (AGENTS.md, plans/) are skipped entirely at the file
	level.
	"""
	# File-level exemptions: known paths where absolute paths are the content
	path_str = str(path)
	if path_str == "AGENTS.md" or path_str.startswith("plans/") or path_str.startswith("doc/plans/"):
		return []

	report = []
	for index, line in enumerate(lines, start=1):
		if index in exempt_lines:
			continue
		for match in _ABSOLUTE_PATH_RE.finditer(line):
			report.append((index, "absolute system path in tracked file — use a repo-relative path or point at .agents/machine-info.md"))
	return report
def check_trailing_blank(lines):
	"""Report a file whose last line is empty, after real content.

	The other half of the final-newline rule, and neither check could stand in for the
	other: `import os\\n\\n` has the final newline, so that check passes, and has no
	double blank line, so the other passes. Only one finding per file — a file ending in
	two or more blank lines is already reported as a double blank line, and naming both
	problems at the same lines is noise.
	"""
	if len(lines) < 2 or lines[-1].strip():
		return []
	if lines[-2].strip():
		return [(len(lines), "trailing blank line at end of file")]
	return []
def check_final_newline(lines):
	if lines and not lines[-1].endswith("\n"):
		return [(len(lines), "missing final newline")]
	return []
def check_leading_blank(lines):
	"""Report a file whose first line is empty.

	An empty line at the start of a file is never intended: it pushes every
	line number down by one and serves no formatting purpose. The check is
	language-agnostic, so every language xlint checks gets it.
	"""
	if lines and not lines[0].strip():
		return [(1, "empty line at start of file")]
	return []
def check_file(path, args):
	try:
		lines = path.read_text().splitlines(keepends=True)
	except (OSError, UnicodeDecodeError):
		return []
	text_lines = [line.rstrip("\n") for line in lines]
	problems = []
	disabled = _disabled_canonical(args)
	if path.suffix == ".py":
		if not (args.no_leading_blank or "leading-blank" in disabled):
			problems.extend((line, "leading-blank", msg) for line, msg in check_leading_blank(text_lines))
		if not (args.no_double_blank or "double-blank" in disabled):
			problems.extend((line, "double-blank", msg) for line, msg in check_double_blank(text_lines))
		if not (args.no_space_indent or "space-indent" in disabled):
			string_lines = _python_string_lines(text_lines)
			problems.extend((line, "space-indent", msg) for line, msg in check_space_indent_exempt(text_lines, string_lines))
		if not (args.no_trailing or "trailing" in disabled):
			problems.extend((line, "trailing", msg) for line, msg in check_trailing_whitespace(text_lines))
		if not (args.no_def_one_line or "def-one-line" in disabled):
			problems.extend((line, "def-one-line", msg) for line, msg in check_def_one_line(text_lines))
		if not (args.no_def_comment or "def-comment" in disabled):
			problems.extend((line, "def-comment", msg) for line, msg in check_def_comment(text_lines))
		if not (args.no_final_newline or "final-newline" in disabled):
			problems.extend((line, "final-newline", msg) for line, msg in check_trailing_blank(text_lines))
			problems.extend((line, "final-newline", msg) for line, msg in check_final_newline(lines))
		if not (args.no_imports or "imports" in disabled):
			problems.extend((line, "imports", msg) for line, msg in check_imports(text_lines))
		if not (args.no_double_space or "double-space" in disabled):
			problems.extend((line, "double-space", msg) for line, msg in check_double_space(text_lines, True))
		if not (args.no_absolute_paths or "absolute-paths" in disabled) and _is_tracked_file(path):
			# A path in a string literal is a value; a path in a docstring is a
			# statement about where this file is. The check wants the second.
			exempt = _python_string_lines(text_lines) - _python_docstring_lines(text_lines)
			problems.extend((line, "absolute-paths", msg) for line, msg in check_absolute_paths(text_lines, exempt, path))
	elif path.suffix == ".md":
		if not (args.no_leading_blank or "leading-blank" in disabled):
			problems.extend((line, "leading-blank", msg) for line, msg in check_leading_blank(text_lines))
		if not (args.no_double_blank or "double-blank" in disabled):
			# The target of `check_trailing_blank`'s deferral. Without it a Markdown file
			# ending in two blank lines is reported by neither check and passes clean.
			problems.extend((line, "double-blank", msg) for line, msg in check_double_blank(text_lines))
		if not _is_tracked_file(path):
			# Untracked files are not subject to the absolute-path rule
			pass
		else:
			exempt = _frontmatter_exempt(text_lines)
			exempt.update(_fence_exempt(text_lines))
			exempt.update(_blockquote_exempt(text_lines))
			if not (args.no_absolute_paths or "absolute-paths" in disabled):
				problems.extend((line, "absolute-paths", msg) for line, msg in check_absolute_paths(text_lines, exempt, path))
		if not (args.no_space_indent or "space-indent" in disabled):
			exempt = _frontmatter_exempt(text_lines)
			exempt.update(_fence_exempt(text_lines))
			problems.extend((line, "space-indent", msg) for line, msg in check_space_indent_exempt(text_lines, exempt))
		if not (args.no_trailing or "trailing" in disabled):
			problems.extend((line, "trailing", msg) for line, msg in check_trailing_whitespace(text_lines, True))
		if not (args.no_final_newline or "final-newline" in disabled):
			problems.extend((line, "final-newline", msg) for line, msg in check_trailing_blank(text_lines))
			problems.extend((line, "final-newline", msg) for line, msg in check_final_newline(lines))
		if not (args.no_double_space or "double-space" in disabled):
			problems.extend((line, "double-space", msg) for line, msg in check_double_space(text_lines, False))
	elif path.suffix in _JS_SUFFIXES:
		if not (args.no_leading_blank or "leading-blank" in disabled):
			problems.extend((line, "leading-blank", msg) for line, msg in check_leading_blank(text_lines))
		if not (args.no_js_double_blank or "js-double-blank" in disabled):
			problems.extend((line, "js-double-blank", msg) for line, msg in check_js_double_blank(text_lines))
		if not (args.no_js_space_indent or "js-space-indent" in disabled):
			exempt = _js_exempt_lines(text_lines)
			problems.extend((line, "js-space-indent", msg) for line, msg in check_js_space_indent(text_lines, exempt))
		if not (args.no_js_trailing or "js-trailing" in disabled):
			problems.extend((line, "js-trailing", msg) for line, msg in check_js_trailing_whitespace(text_lines))
		if not (args.no_js_final_newline or "js-final-newline" in disabled):
			problems.extend((line, "js-final-newline", msg) for line, msg in check_js_trailing_blank(text_lines))
			problems.extend((line, "js-final-newline", msg) for line, msg in check_js_final_newline(lines))
	elif path.suffix in _HTML_SUFFIXES:
		if not (args.no_leading_blank or "leading-blank" in disabled):
			problems.extend((line, "leading-blank", msg) for line, msg in check_leading_blank(text_lines))
		if not (args.no_html_double_blank or "html-double-blank" in disabled):
			problems.extend((line, "html-double-blank", msg) for line, msg in check_double_blank(text_lines))
		if not (args.no_html_space_indent or "html-space-indent" in disabled):
			problems.extend((line, "html-space-indent", msg) for line, msg in check_space_indent(text_lines))
		if not (args.no_html_trailing or "html-trailing" in disabled):
			problems.extend((line, "html-trailing", msg) for line, msg in check_trailing_whitespace(text_lines))
		if not (args.no_html_final_newline or "html-final-newline" in disabled):
			problems.extend((line, "html-final-newline", msg) for line, msg in check_trailing_blank(text_lines))
			problems.extend((line, "html-final-newline", msg) for line, msg in check_final_newline(lines))
		html_problems = _html.check_html(text_lines)
		if not (args.no_html_unclosed or "html-unclosed" in disabled):
			problems.extend((line, "html-unclosed", msg) for line, msg in html_problems["unclosed"])
		if not (args.no_html_bad_closer or "html-bad-closer" in disabled):
			problems.extend((line, "html-bad-closer", msg) for line, msg in html_problems["bad_closer"])
		if not (args.no_html_depth or "html-depth" in disabled):
			problems.extend((line, "html-depth", msg) for line, msg in html_problems["depth"])
	elif path.suffix in _C_SUFFIXES:
		if not (args.no_leading_blank or "leading-blank" in disabled):
			problems.extend((line, "leading-blank", msg) for line, msg in check_leading_blank(text_lines))
		if not (args.no_double_blank or "double-blank" in disabled):
			problems.extend((line, "double-blank", msg) for line, msg in check_double_blank(text_lines))
		if not (args.no_space_indent or "space-indent" in disabled):
			problems.extend((line, "space-indent", msg) for line, msg in check_space_indent(text_lines))
		if not (args.no_trailing or "trailing" in disabled):
			problems.extend((line, "trailing", msg) for line, msg in check_trailing_whitespace(text_lines))
		if not (args.no_final_newline or "final-newline" in disabled):
			problems.extend((line, "final-newline", msg) for line, msg in check_trailing_blank(text_lines))
			problems.extend((line, "final-newline", msg) for line, msg in check_final_newline(lines))
	if not (args.no_personal or "personal" in disabled) and _is_tracked_file(path):
		# A tracked file is published with the repository, and this repository is
		# public. The check asks for the personal identifiers to stay out of it.
		problems.extend((line, "personal", msg) for line, msg in _personal.check(text_lines))
	if not (args.no_banned_git or "banned-git" in disabled) and _is_tracked_file(path):
		# Files whose subject is the ban legitimately quote it.
		_posix = path.as_posix()
		_exempt_paths = ("AGENTS.md", "doc/working-tree.md", "tools/xlint/xlint.py", "tools/xlint/_banned_git.py", "tools/xlint/test/test_xlint.py")
		if not any(_posix == candidate or _posix.endswith("/" + candidate) for candidate in _exempt_paths):
			problems.extend((line, "banned-git", msg) for line, msg in _banned_git.check(text_lines))
	return problems

__all__ = ['check_double_blank', 'check_space_indent', 'check_space_indent_exempt', 'check_trailing_whitespace', 'check_double_space', '_line_has_double_space', 'check_absolute_paths', 'check_trailing_blank', 'check_final_newline', 'check_leading_blank', 'check_file']
