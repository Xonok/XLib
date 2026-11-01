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
class _Check:
	"""One entry in a language's check list.

	`attr`/`name` are the disable flag attribute and canonical rule name;
	`rule` is the rule id reported; `produce` returns (line, message) pairs.
	"""

	__slots__ = ("attr", "name", "rule", "tracked_only", "produce")

	def __init__(self, attr, name, rule, produce, tracked_only=False):
		self.attr = attr
		self.name = name
		self.rule = rule
		self.tracked_only = tracked_only
		self.produce = produce

def _py_checks():
	return [
		_Check("no_leading_blank", "leading-blank", "leading-blank", lambda lines, text, path, tracked: check_leading_blank(text)),
		_Check("no_double_blank", "double-blank", "double-blank", lambda lines, text, path, tracked: check_double_blank(text)),
		_Check("no_space_indent", "space-indent", "space-indent", lambda lines, text, path, tracked: check_space_indent_exempt(text, _python_string_lines(text))),
		_Check("no_trailing", "trailing", "trailing", lambda lines, text, path, tracked: check_trailing_whitespace(text)),
		_Check("no_def_one_line", "def-one-line", "def-one-line", lambda lines, text, path, tracked: check_def_one_line(text)),
		_Check("no_def_comment", "def-comment", "def-comment", lambda lines, text, path, tracked: check_def_comment(text)),
		_Check("no_final_newline", "final-newline", "final-newline", lambda lines, text, path, tracked: check_trailing_blank(text) + check_final_newline(lines)),
		_Check("no_imports", "imports", "imports", lambda lines, text, path, tracked: check_imports(text)),
		_Check("no_double_space", "double-space", "double-space", lambda lines, text, path, tracked: check_double_space(text, True)),
		_Check("no_absolute_paths", "absolute-paths", "absolute-paths", lambda lines, text, path, tracked: check_absolute_paths(text, _python_string_lines(text) - _python_docstring_lines(text), path) if tracked else [], tracked_only=True),
	]

def _md_checks():
	def _abs_exempt(text):
		exempt = _frontmatter_exempt(text)
		exempt.update(_fence_exempt(text))
		exempt.update(_blockquote_exempt(text))
		return exempt

	def _space_exempt(text):
		exempt = _frontmatter_exempt(text)
		exempt.update(_fence_exempt(text))
		return exempt

	return [
		_Check("no_leading_blank", "leading-blank", "leading-blank", lambda lines, text, path, tracked: check_leading_blank(text)),
		_Check("no_double_blank", "double-blank", "double-blank", lambda lines, text, path, tracked: check_double_blank(text)),
		_Check("no_absolute_paths", "absolute-paths", "absolute-paths", lambda lines, text, path, tracked: check_absolute_paths(text, _abs_exempt(text), path) if tracked else [], tracked_only=True),
		_Check("no_space_indent", "space-indent", "space-indent", lambda lines, text, path, tracked: check_space_indent_exempt(text, _space_exempt(text))),
		_Check("no_trailing", "trailing", "trailing", lambda lines, text, path, tracked: check_trailing_whitespace(text, True)),
		_Check("no_final_newline", "final-newline", "final-newline", lambda lines, text, path, tracked: check_trailing_blank(text) + check_final_newline(lines)),
		_Check("no_double_space", "double-space", "double-space", lambda lines, text, path, tracked: check_double_space(text, False)),
	]

def _js_checks():
	return [
		_Check("no_leading_blank", "leading-blank", "leading-blank", lambda lines, text, path, tracked: check_leading_blank(text)),
		_Check("no_js_double_blank", "js-double-blank", "js-double-blank", lambda lines, text, path, tracked: check_js_double_blank(text)),
		_Check("no_js_space_indent", "js-space-indent", "js-space-indent", lambda lines, text, path, tracked: check_js_space_indent(text, _js_exempt_lines(text))),
		_Check("no_js_trailing", "js-trailing", "js-trailing", lambda lines, text, path, tracked: check_js_trailing_whitespace(text)),
		_Check("no_js_final_newline", "js-final-newline", "js-final-newline", lambda lines, text, path, tracked: check_js_trailing_blank(text) + check_js_final_newline(lines)),
	]

def _html_checks():
	return [
		_Check("no_leading_blank", "leading-blank", "leading-blank", lambda lines, text, path, tracked: check_leading_blank(text)),
		_Check("no_html_double_blank", "html-double-blank", "html-double-blank", lambda lines, text, path, tracked: check_double_blank(text)),
		_Check("no_html_space_indent", "html-space-indent", "html-space-indent", lambda lines, text, path, tracked: check_space_indent(text)),
		_Check("no_html_trailing", "html-trailing", "html-trailing", lambda lines, text, path, tracked: check_trailing_whitespace(text)),
		_Check("no_html_final_newline", "html-final-newline", "html-final-newline", lambda lines, text, path, tracked: check_trailing_blank(text) + check_final_newline(lines)),
		_Check("no_html_unclosed", "html-unclosed", "html-unclosed", lambda lines, text, path, tracked: _html.check_html(text)["unclosed"]),
		_Check("no_html_bad_closer", "html-bad-closer", "html-bad-closer", lambda lines, text, path, tracked: _html.check_html(text)["bad_closer"]),
		_Check("no_html_depth", "html-depth", "html-depth", lambda lines, text, path, tracked: _html.check_html(text)["depth"]),
	]

def _c_checks():
	return [
		_Check("no_leading_blank", "leading-blank", "leading-blank", lambda lines, text, path, tracked: check_leading_blank(text)),
		_Check("no_double_blank", "double-blank", "double-blank", lambda lines, text, path, tracked: check_double_blank(text)),
		_Check("no_space_indent", "space-indent", "space-indent", lambda lines, text, path, tracked: check_space_indent(text)),
		_Check("no_trailing", "trailing", "trailing", lambda lines, text, path, tracked: check_trailing_whitespace(text)),
		_Check("no_final_newline", "final-newline", "final-newline", lambda lines, text, path, tracked: check_trailing_blank(text) + check_final_newline(lines)),
	]

_LANGUAGE_CHECKS = {
	"py": _py_checks(),
	"md": _md_checks(),
	"js": _js_checks(),
	"html": _html_checks(),
	"c": _c_checks(),
}

_SUFFIX_TO_LANGUAGE = {}
for _s in (".py",):
	_SUFFIX_TO_LANGUAGE[_s] = "py"
for _s in (".md",):
	_SUFFIX_TO_LANGUAGE[_s] = "md"
for _s in _JS_SUFFIXES:
	_SUFFIX_TO_LANGUAGE[_s] = "js"
for _s in _HTML_SUFFIXES:
	_SUFFIX_TO_LANGUAGE[_s] = "html"
for _s in _C_SUFFIXES:
	_SUFFIX_TO_LANGUAGE[_s] = "c"

def check_file(path, args):
	try:
		lines = path.read_text().splitlines(keepends=True)
	except (OSError, UnicodeDecodeError):
		return []
	text_lines = [line.rstrip("\n") for line in lines]
	problems = []
	disabled = _disabled_canonical(args)
	tracked = _is_tracked_file(path)
	language = _SUFFIX_TO_LANGUAGE.get(path.suffix)
	if language is not None:
		for chk in _LANGUAGE_CHECKS[language]:
			if getattr(args, chk.attr, False) or chk.name in disabled:
				continue
			if chk.tracked_only and not tracked:
				continue
			for line, msg in chk.produce(lines, text_lines, path, tracked):
				problems.append((line, chk.rule, msg))
	if not (args.no_personal or "personal" in disabled) and tracked:
		problems.extend((line, "personal", msg) for line, msg in _personal.check(text_lines))
	if not (args.no_banned_git or "banned-git" in disabled) and tracked:
		_posix = path.as_posix()
		_exempt_paths = ("AGENTS.md", "doc/working-tree.md", "tools/xlint/xlint.py", "tools/xlint/_banned_git.py", "tools/xlint/test/test_xlint_git.py")
		if not any(_posix == candidate or _posix.endswith("/" + candidate) for candidate in _exempt_paths):
			problems.extend((line, "banned-git", msg) for line, msg in _banned_git.check(text_lines))
	return problems

__all__ = ['check_double_blank', 'check_space_indent', 'check_space_indent_exempt', 'check_trailing_whitespace', 'check_double_space', '_line_has_double_space', 'check_absolute_paths', 'check_trailing_blank', 'check_final_newline', 'check_leading_blank', 'check_file', '_Check', '_LANGUAGE_CHECKS', '_SUFFIX_TO_LANGUAGE']
