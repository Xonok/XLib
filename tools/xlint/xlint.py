import argparse,ast,ctypes,io,os,re,select,struct,sys,time,tokenize,subprocess
from pathlib import Path

_DEF_PREFIX_RE = re.compile(r"^\s*(async\s+def|def)\s+\w+")
_SPACE_INDENT_RE = re.compile(r"^ +\S")
_ALIASED_NAME_RE = re.compile(r"\bas\b")
_CLEAR_SCREEN = "\033[2J\033[H"
NAME = "xlint"
_EVENT_HEADER = struct.Struct("=iIII")
_IN_CLOSE_WRITE = 0x00000008
_IN_MOVED_FROM = 0x00000040
_IN_MOVED_TO = 0x00000080
_IN_CREATE = 0x00000100
_IN_DELETE = 0x00000200
_IN_DELETE_SELF = 0x00000400
_IN_MOVE_SELF = 0x00000800
_IN_IGNORED = 0x00008000
_IN_ISDIR = 0x40000000
_WATCH_MASK = _IN_CLOSE_WRITE | _IN_MOVED_FROM | _IN_MOVED_TO | _IN_CREATE | _IN_DELETE | _IN_DELETE_SELF | _IN_MOVE_SELF
try:
	_libc = ctypes.CDLL(None, use_errno=True)
	_libc.inotify_init.restype = ctypes.c_int
	_libc.inotify_init.argtypes = []
	_libc.inotify_add_watch.restype = ctypes.c_int
	_libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
except AttributeError:
	_libc = None

_BUILTIN_EXCLUDED = {"__pycache__", ".git", "node_modules", "xlib_legacy"}
_IGNORE_FILE = ".xlintignore"

class _Exclusions:
	"""What xlint skips, from its own defaults plus a per-repo `.xlintignore`.

	A separate file rather than `.gitignore` on purpose: a tracking statement is not a
	style statement, and a documentation file the human is still drafting is untracked
	by definition. Reading `.gitignore` here would exempt exactly the files most worth
	linting (`AK633QC`).
	"""

	def __init__(self, extra=()):
		self.rules = []
		for base in sorted(set(extra)):
			self.load(base / _IGNORE_FILE, base)

	def load(self, path, base):
		"""Read one `.xlintignore`; patterns are relative to the directory holding it."""
		try:
			text = path.read_text(encoding="utf-8")
		except OSError:
			return
		for line in text.splitlines():
			rule = _compile_pattern(line, base)
			if rule is not None:
				self.rules.append(rule)

	def excluded(self, path, is_dir):
		"""True when `path` is skipped, directly or by living inside an excluded directory.

		Each ancestor is tested too, because a pattern ending in `/` is about a
		directory and never matches the file inside it.
		"""
		path = path.resolve()
		parts = path.parts
		for depth in range(len(parts), 0, -1):
			if self.excluded_here(Path(*parts[:depth]), is_dir and depth == len(parts)):
				return True
		return False

	def excluded_here(self, path, is_dir):
		"""True when a pattern matches `path` itself. Last match wins, as in gitignore."""
		verdict = False
		for negated, base, regex in self.rules:
			base = base.resolve()
			try:
				relative = path.relative_to(base)
			except ValueError:
				continue
			if regex.match(relative.as_posix() + ("/" if is_dir else "")) is not None:
				verdict = not negated
		return verdict

def _compile_pattern(line, base):
	"""One gitignore pattern to `(negated, base, regex)`, or None for a comment or blank.

	The supported subset is what an exclusion list needs: `*`, `?`, `**`, a trailing `/`
	for directories only, a leading `/` or an interior `/` to anchor, `!` to re-include,
	and `#` comments. Anything outside it is treated as literal text rather than
	guessed at, so an unrecognised pattern cannot silently exclude the whole tree.
	"""
	line = line.rstrip()
	if not line.strip() or line.lstrip().startswith("#"):
		return None
	negated = line.startswith("!")
	if negated:
		line = line[1:]
	dir_only = line.endswith("/")
	if dir_only:
		line = line[:-1]
		if not line:
			return None
	anchored = line.startswith("/") or "/" in line
	line = line.lstrip("/")
	parts = []
	for part in line.split("/"):
		if part == "**":
			parts.append("(?:.*/)?")
			continue
		parts.append(_glob_to_regex(part))
	body = "/".join(parts)
	if dir_only:
		# A directory pattern matches the directory itself AND everything inside it.
		regex = "^" + body + "(?:/.*)?$"
	else:
		regex = "^" + body + ("$" if anchored else "(?:/.*)?$")
	return negated, base, re.compile(regex)

def _glob_to_regex(part):
	"""One path segment of a pattern to a regex: `*` and `?` stop at a separator, and
	everything else is literal."""
	out = []
	for char in part:
		if char == "*":
			out.append("[^/]*")
		elif char == "?":
			out.append("[^/]")
		else:
			out.append(re.escape(char))
	return "".join(out)

def find_exclusion_roots(start):
	"""Directories from `start` upward whose `.xlintignore` governs it, nearest last.

	Walks up so a run from a subdirectory sees the same exclusions a run from the repo
	root does, and so a nested repository's file overrides rather than disappears.
	"""
	roots = []
	current = start.resolve()
	if current.is_file():
		current = current.parent
	while True:
		if (current / _IGNORE_FILE).is_file():
			roots.append(current)
		if current.parent == current:
			return roots
		current = current.parent

def is_ignored(path, exclusions=None):
	if set(path.parts) & _BUILTIN_EXCLUDED:
		return True
	if exclusions is not None and exclusions.excluded(path, path.is_dir()):
		return True
	return False

_JS_SUFFIXES = (".js", ".mjs", ".cjs", ".ts", ".tsx")
_PY_MD_SUFFIXES = (".py", ".md")
_ALL_SUFFIXES = _PY_MD_SUFFIXES + _JS_SUFFIXES

def lint_files(paths, exclusions=None):
	found = []
	for entry in paths:
		if entry.is_file() and entry.suffix in _ALL_SUFFIXES:
			if exclusions is None:
				exclusions = _Exclusions(find_exclusion_roots(entry))
			if not is_ignored(entry, exclusions):
				found.append(entry)
		elif entry.is_dir():
			if exclusions is None:
				exclusions = _Exclusions(find_exclusion_roots(entry))
			for path in sorted(entry.rglob("*")):
				if not is_ignored(path, exclusions) and path.suffix in _ALL_SUFFIXES:
					found.append(path)
	return found

def stamp(path):
	try:
		return path.stat().st_mtime_ns
	except OSError:
		return None

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

def _frontmatter_exempt(lines):
	if not lines or lines[0] != "---":
		return set()
	for i in range(1, len(lines)):
		if lines[i] == "---":
			return set(range(1, i + 2))
	return set()

def _fence_exempt(lines):
	"""Line numbers inside a fenced code block, including the fence lines themselves.

	A fence is recognised after leading whitespace, so a block nested in a list item is
	a fence rather than a space-indented violation. That is the ordinary way to write
	one, and a rule that makes it unlintable is a rule whose only remedy is to corrupt
	the code to satisfy the linter (`QN1N82Y`).
	"""
	exempt = set()
	in_fence = False
	fence_char = None
	fence_len = 0
	for i, line in enumerate(lines, start=1):
		body = line.lstrip()
		if not body:
			if in_fence:
				exempt.add(i)
			continue
		ch = body[0]
		if ch not in ("`", "~"):
			if in_fence:
				exempt.add(i)
			continue
		count = 0
		for c in body:
			if c == ch:
				count += 1
			else:
				break
		if count >= 3:
			if not in_fence:
				in_fence = True
				fence_char = ch
				fence_len = count
			elif ch == fence_char and count >= fence_len:
				in_fence = False
				fence_char = None
				fence_len = 0
			else:
				exempt.add(i)
		else:
			if in_fence:
				exempt.add(i)
	return exempt

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


def check_js_trailing_whitespace(lines):
	"""Trailing whitespace check for JS/TS — same as Python, no Markdown exception."""
	report = []
	for index, line in enumerate(lines, start=1):
		if line != line.rstrip() and line.strip():
			report.append((index, "trailing whitespace"))
	return report


def check_js_double_blank(lines):
	"""Double blank line check for JS/TS — same as Python/Markdown."""
	report = []
	for index, (prev, current) in enumerate(zip(lines, lines[1:]), start=2):
		if prev == "" and current == "":
			report.append((index, "double blank line"))
	return report


def check_js_space_indent(lines, exempt):
	"""Space indentation check for JS/TS — tabs only, with exempt spans."""
	report = []
	for index, line in enumerate(lines, start=1):
		if index in exempt:
			continue
		if _SPACE_INDENT_RE.match(line):
			report.append((index, "indented with spaces"))
	return report


def check_js_final_newline(lines):
	"""Final newline check for JS/TS — file must end with exactly one newline."""
	if lines and not lines[-1].endswith("\n"):
		return [(len(lines), "missing final newline")]
	return []


def check_js_trailing_blank(lines):
	"""Trailing blank line check for JS/TS — no empty line at end after real content."""
	if len(lines) < 2 or lines[-1].strip():
		return []
	if lines[-2].strip():
		return [(len(lines), "trailing blank line at end of file")]
	return []


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

_DOUBLE_SPACE_RE = re.compile(r"[^ ](  +)[^ ]")

def _python_exempt_spans(lines):
	"""Map each line number to a list of (start, end) spans that are exempt from the double-space check.

	Covers string literals, f-strings, and comments as tokenize sees them. A `#` inside a string
	is not a comment; a `"` inside a comment is not a string.
	"""
	exempt = {}
	source = "".join(line + "\n" for line in lines)
	try:
		for token in tokenize.generate_tokens(io.StringIO(source).readline):
			if token.type in (tokenize.STRING, tokenize.COMMENT, tokenize.FSTRING_START, tokenize.FSTRING_MIDDLE, tokenize.FSTRING_END):
				start_line = token.start[0]
				start_col = token.start[1]
				end_line = token.end[0]
				end_col = token.end[1]
				for ln in range(start_line, end_line + 1):
					if ln not in exempt:
						exempt[ln] = []
					if ln == start_line and ln == end_line:
						exempt[ln].append((start_col, end_col))
					elif ln == start_line:
						exempt[ln].append((start_col, len(lines[ln - 1])))
					elif ln == end_line:
						exempt[ln].append((0, end_col))
					else:
						exempt[ln].append((0, len(lines[ln - 1])))
	except (tokenize.TokenError, IndentationError, SyntaxError):
		return {}
	return exempt

def _python_string_lines(lines):
	"""Return set of line numbers that are inside string literals (including f-strings).

	These lines may start with spaces as part of the string content and should be
	exempt from the space-indentation check.
	"""
	exempt = _python_exempt_spans(lines)
	# Filter to only string spans (not comments)
	string_lines = set()
	source = "".join(line + "\n" for line in lines)
	try:
		for token in tokenize.generate_tokens(io.StringIO(source).readline):
			if token.type in (tokenize.STRING, tokenize.FSTRING_START, tokenize.FSTRING_MIDDLE, tokenize.FSTRING_END):
				start_line = token.start[0]
				end_line = token.end[0]
				for ln in range(start_line, end_line + 1):
					string_lines.add(ln)
	except (tokenize.TokenError, IndentationError, SyntaxError):
		return set()
	return string_lines

def _markdown_exempt_spans(lines):
	"""Line spans inside fenced code, frontmatter, or inline code spans."""
	exempt = {}
	exempt_set = _frontmatter_exempt(lines)
	exempt_set.update(_fence_exempt(lines))
	# Inline code spans: backtick-delimited on a single line
	for index, line in enumerate(lines, start=1):
		if index in exempt_set:
			continue
		for match in re.finditer(r"`[^`]*`", line):
			start, end = match.span()
			exempt.setdefault(index, []).append((start, end))
	# Convert the set of fully-exempt lines to spans
	for ln in exempt_set:
		if ln <= len(lines):
			exempt[ln] = [(0, len(lines[ln - 1]))]
	return exempt

def _blockquote_exempt(lines):
	"""Line numbers of block-quote lines (lines starting with `> ` after optional whitespace).

	These are exempt from the absolute-path check because quoted material is evidence,
	not a location reference.
	"""
	exempt = set()
	for i, line in enumerate(lines, start=1):
		stripped = line.lstrip()
		if stripped.startswith("> "):
			exempt.add(i)
	return exempt


def _js_exempt_spans(lines):
	"""Map each line number to a list of (start_col, end_col) spans exempt from checks.

	Covers string literals (single/double quoted), template literals (backtick),
	line comments (//), block comments (/* */), and regex literals (/pattern/flags).

	Uses a simple state machine — no parser — because the exemption rules only need
	to know where literal content lives, not the full AST.
	"""
	exempt = {}
	source = "\n".join(lines) + "\n"
	i = 0
	line = 1
	col = 0
	line_start = 0

	while i < len(source):
		ch = source[i]

		if ch == "\n":
			line += 1
			col = 0
			line_start = i + 1
			i += 1
			continue

		# Single-line comment //
		if ch == "/" and i + 1 < len(source) and source[i + 1] == "/":
			start_line = line
			start_col = col
			# Consume to end of line
			while i < len(source) and source[i] != "\n":
				i += 1
				col += 1
			end_col = col
			if start_line not in exempt:
				exempt[start_line] = []
			exempt[start_line].append((start_col, end_col))
			continue

		# Block comment /* ... */
		if ch == "/" and i + 1 < len(source) and source[i + 1] == "*":
			start_line = line
			start_col = col
			i += 2
			col += 2
			while i + 1 < len(source):
				if source[i] == "\n":
					line += 1
					col = 0
					line_start = i + 1
					i += 1
				elif source[i] == "*" and source[i + 1] == "/":
					i += 2
					col += 2
					break
				else:
					i += 1
					col += 1
			end_line = line
			end_col = col
			for ln in range(start_line, end_line + 1):
				if ln not in exempt:
					exempt[ln] = []
				if ln == start_line and ln == end_line:
					exempt[ln].append((start_col, end_col))
				elif ln == start_line:
					exempt[ln].append((start_col, len(lines[ln - 1])))
				elif ln == end_line:
					exempt[ln].append((0, end_col))
				else:
					exempt[ln].append((0, len(lines[ln - 1])))
			continue

		# String literals: '...' or "..." (with escape handling)
		if ch == "'" or ch == '"':
			quote = ch
			start_line = line
			start_col = col
			i += 1
			col += 1
			while i < len(source):
				if source[i] == "\n":
					# Unclosed string - treat as ending at line end
					break
				if source[i] == "\\":
					i += 2
					col += 2
					continue
				if source[i] == quote:
					i += 1
					col += 1
					break
				i += 1
				col += 1
			end_line = line
			end_col = col
			for ln in range(start_line, end_line + 1):
				if ln not in exempt:
					exempt[ln] = []
				if ln == start_line and ln == end_line:
					exempt[ln].append((start_col, end_col))
				elif ln == start_line:
					exempt[ln].append((start_col, len(lines[ln - 1])))
				elif ln == end_line:
					exempt[ln].append((0, end_col))
				else:
					exempt[ln].append((0, len(lines[ln - 1])))
			continue

		# Template literals: `...` (with ${...} interpolation and escape handling)
		if ch == "`":
			start_line = line
			start_col = col
			i += 1
			col += 1
			while i < len(source):
				if source[i] == "\n":
					line += 1
					col = 0
					line_start = i + 1
					i += 1
					continue
				if source[i] == "\\":
					i += 2
					col += 2
					continue
				if source[i] == "$" and i + 1 < len(source) and source[i + 1] == "{":
					# Skip interpolation - treat as part of template
					i += 2
					col += 2
					continue
				if source[i] == "`":
					i += 1
					col += 1
					break
				i += 1
				col += 1
			end_line = line
			end_col = col
			for ln in range(start_line, end_line + 1):
				if ln not in exempt:
					exempt[ln] = []
				if ln == start_line and ln == end_line:
					exempt[ln].append((start_col, end_col))
				elif ln == start_line:
					exempt[ln].append((start_col, len(lines[ln - 1])))
				elif ln == end_line:
					exempt[ln].append((0, end_col))
				else:
					exempt[ln].append((0, len(lines[ln - 1])))
			continue

		# Regex literals: /pattern/flags (heuristic: / not preceded by identifier, (, [, {, ,, ;, :, =, !, &, |, ?, +, -, *, %, ~, ^)
		# This is a best-effort approximation without a full parser
		if ch == "/":
			# Look back to see if this could be a regex
			prev_i = i - 1
			while prev_i >= 0 and source[prev_i] in " \t\r\n":
				prev_i -= 1
			prev_char = source[prev_i] if prev_i >= 0 else ""
			# Regex appears after: ( [ { , ; : = ! & | ? + - * % ~ ^ > < return throw case
			# Not after: identifier, ), ], }, string, number, regex, `, null, true, false, this
			is_regex = prev_char in "([{,;:=!&|?+-*%~^<>"

			if is_regex:
				start_line = line
				start_col = col
				i += 1
				col += 1
				in_class = False
				while i < len(source):
					if source[i] == "\n":
						# Unclosed regex
						break
					if source[i] == "\\":
						i += 2
						col += 2
						continue
					if source[i] == "[" and not in_class:
						in_class = True
					elif source[i] == "]" and in_class:
						in_class = False
					elif source[i] == "/" and not in_class:
						i += 1
						col += 1
						# Consume flags
						while i < len(source) and source[i].isalpha():
							i += 1
							col += 1
						break
					i += 1
					col += 1
				end_line = line
				end_col = col
				for ln in range(start_line, end_line + 1):
					if ln not in exempt:
						exempt[ln] = []
					if ln == start_line and ln == end_line:
						exempt[ln].append((start_col, end_col))
					elif ln == start_line:
						exempt[ln].append((start_col, len(lines[ln - 1])))
					elif ln == end_line:
						exempt[ln].append((0, end_col))
					else:
						exempt[ln].append((0, len(lines[ln - 1])))
				continue

		i += 1
		col += 1

	return exempt


def _js_exempt_lines(lines):
	"""Return set of line numbers that are inside JS/TS literals or comments.

	These lines may start with spaces as part of the literal/comment content and should be
	exempt from the space-indentation check. Mirrors `_python_string_lines`.
	"""
	spans = _js_exempt_spans(lines)
	# A line is exempt if it has any exempt span (string, template, comment, regex)
	return set(spans.keys())

def _is_tracked_file(path):
	"""True when `path` is tracked by git (in the index or committed)."""
	try:
		result = subprocess.run(
			["git", "ls-files", "--", str(path)],
			capture_output=True,
			text=True,
			timeout=2,
		)
		return bool(result.stdout.strip())
	except (subprocess.SubprocessError, OSError):
		return False

_ABSOLUTE_PATH_RE = re.compile(r"(?:^|[\s\(\"\'])((?:/storage/|/home/[^/]+/|/root/|~/)[^\s\)\]\}\"'>]+)")

def check_absolute_paths(lines, exempt_lines, path):
	"""Report absolute system paths in tracked Markdown files.

	Flags tokens starting with `/storage/`, `/home/<user>/`, `/root/`, or `~/`
	that are not in exempt lines (frontmatter, fenced code, block quotes).
	Known exempt paths (AGENTS.md, plans/, personal/*/HISTORY.md) are skipped
	entirely at the file level.
	"""
	# File-level exemptions: known paths where absolute paths are the content
	path_str = str(path)
	if path_str == "AGENTS.md" or path_str.startswith("plans/") or path_str.startswith("doc/plans/") or re.match(r"personal/[^/]+/HISTORY\.md$", path_str):
		return []

	report = []
	for index, line in enumerate(lines, start=1):
		if index in exempt_lines:
			continue
		for match in _ABSOLUTE_PATH_RE.finditer(line):
			report.append((index, "absolute system path in tracked file — use a repo-relative path or point at .agents/machine-info.md"))
	return report

def _is_permitted_multiline(lines, node, end):
	"""True when `node`'s header takes the shape the houserule permits.

	Arguments each on their own line, one tab deeper than the `def`; the closing `)`
	on its own line at the `def`'s own indent. Structure, not alignment — which is
	the point of the shape (a rename cannot break it).
	"""
	start = node.lineno
	def_indent = len(lines[start - 1]) - len(lines[start - 1].lstrip("\t"))
	for line in lines[start:end - 1]:
		if not line.strip():
			return False
		if len(line) - len(line.lstrip("\t")) != def_indent + 1:
			return False
	closing = lines[end - 1]
	if len(closing) - len(closing.lstrip("\t")) != def_indent:
		return False
	if not closing.lstrip("\t").startswith(")"):
		return False
	return _one_argument_per_line(node, start)

def _one_argument_per_line(node, start):
	"""True when no two arguments of `node` share a line, and none sits on the `def` line.

	Reads the argument nodes' own lines rather than counting commas: a default value
	may contain one (`alpha=(1, 2)`), and a comma count cannot tell that from a
	separator.
	"""
	nodes = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
	nodes += [extra for extra in (node.args.vararg, node.args.kwarg) if extra is not None]
	seen = set()
	for argument in nodes:
		if argument.lineno <= start or argument.lineno in seen:
			return False
		seen.add(argument.lineno)
	return True

def _spanned_def_lines(lines):
	"""Map each `def` line to the line its parameter list closes on, or None when the file does not parse.

	`ast` is asked rather than a bracket count: a paren inside a string literal or a
	comment is not a paren, and counting characters cannot tell the difference.
	"""
	try:
		tree = ast.parse("".join(line + "\n" for line in lines))
	except SyntaxError:
		return None
	spans = {}
	for node in ast.walk(tree):
		if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
			spans[node.lineno] = (node, _signature_end(node, lines))
	return spans

def _signature_end(node, lines):
	"""The line the header of `node` — everything up to its closing `:` — closes on.

	Read off the first statement rather than off the arguments: `ast` gives no node for
	the parameter list itself, so an empty one (`def ok(\\n):`) would leave nothing to
	measure. The line above the body is that `):` by construction, stepping back over
	blank and comment lines so neither a gap nor a comment between the two hides it —
	both sit inside the header without being part of it.
	"""
	if not node.body:
		return node.lineno
	end = node.body[0].lineno - 1
	while end > node.lineno and _is_gap(lines[end - 1]):
		end -= 1
	return max(end, node.lineno)

def _is_gap(line):
	"""True when a line carries nothing that belongs to the header it sits inside."""
	stripped = line.strip()
	return not stripped or stripped.startswith("#")

def check_def_one_line(lines):
	"""Report a `def` whose signature is neither on one line nor in the permitted shape.

	Three states, previously conflated into one: closed on the line is clean whatever
	follows the colon (a trailing comment included); spanning lines in the permitted
	shape is clean; anything else is a spill. Deciding the middle case needs `ast`,
	because whether the parameter list closes on its line is not a question a regex
	can answer without also being fooled by a comment or a string.
	"""
	report = []
	spans = _spanned_def_lines(lines)
	if spans is None:
		# File has a SyntaxError; we cannot reliably distinguish real function
		# definitions from ones inside strings/comments. Skip this check.
		return report
	for index, line in enumerate(lines, start=1):
		open_paren = line.find("(")
		if open_paren == -1:
			continue
		if not _DEF_PREFIX_RE.match(line[:open_paren]):
			continue
		spanned = spans.get(index)
		if spanned is None:
			# Line looks like a function definition but `ast` didn't recognize it
			# as one — it's inside a string literal or a comment. Skip it.
			continue
		node, end = spanned
		if end == index:
			continue
		if end <= len(lines) and _is_permitted_multiline(lines, node, end):
			continue
		report.append((index, "function definition split across lines"))
	return report

def _def_lines(lines):
	"""Line numbers of every `def`, `async def` and `class` statement, or None when the file does not parse."""
	try:
		tree = ast.parse("".join(line + "\n" for line in lines))
	except SyntaxError:
		return None
	kinds = (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef)
	return {node.lineno for node in ast.walk(tree) if isinstance(node, kinds)}

def _comment_lines(lines):
	"""Line numbers carrying a real comment, as `tokenize` sees them.

	`tokenize` rather than a `#` split, because a `#` inside a string literal is not a
	comment: `f"  #{name}"` is report layout, and reading it as a comment would flag a
	line whose author never wrote one.
	"""
	found = set()
	try:
		for token in tokenize.generate_tokens(io.StringIO("".join(line + "\n" for line in lines)).readline):
			if token.type == tokenize.COMMENT:
				found.add(token.start[0])
	except (tokenize.TokenError, IndentationError, SyntaxError):
		return None
	return found

def check_def_comment(lines):
	"""Report a comment sharing a line with a `def` or `class`.

	Its own rule rather than a verdict of the one-line-signature check, because it is
	fixable in a way that check is not: the comment moves up a line. Folded in there, a
	reader had to re-derive per hit which of two problems they were looking at — which
	is how that check ended up reporting 74 findings and not one of them right.
	"""
	defs = _def_lines(lines)
	comments = _comment_lines(lines)
	if defs is None or comments is None:
		return []
	return [(line, "comment on a def line") for line in sorted(defs & comments)]

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

def check_imports(lines):
	report = []
	in_block = False
	prev_module = None
	prev_plain = False
	pending_blank = None
	for index, line in enumerate(lines, start=1):
		stripped = line.strip()
		if not in_block and not stripped.startswith(("import ", "from ")):
			continue
		in_block = True
		if not stripped:
			pending_blank = index
			prev_plain = False
			continue
		if stripped.startswith("#"):
			continue
		if not stripped.startswith(("import ", "from ")):
			break
		if pending_blank is not None:
			report.append((pending_blank, "blank line between imports"))
			pending_blank = None
		if ";" in line:
			report.append((index, "multiple statements on one line"))
		from_match = re.match(r"^\s*from\s+(\S+)\s+import\s+", line)
		if from_match:
			module = from_match.group(1)
			if module == prev_module:
				report.append((index, "same module imported on separate lines"))
			prev_module = module
			prev_plain = False
			names = line[from_match.end():]
			if "*" in names:
				report.append((index, "wildcard import"))
			if re.search(r",\s", names):
				report.append((index, "space after comma in import"))
		else:
			prev_module = None
			import_match = re.match(r"^\s*import\s+", line)
			if import_match:
				names = line[import_match.end():]
				if re.search(r",\s", names):
					report.append((index, "space after comma in import"))
				if _ALIASED_NAME_RE.search(names):
					if "," in names:
						report.append((index, "aliased import on a shared line"))
					prev_plain = False
				elif "." not in names:
					if prev_plain:
						report.append((index, "consecutive plain imports not merged"))
					prev_plain = True
				else:
					prev_plain = False
	return report

def check_file(path, args):
	try:
		lines = path.read_text().splitlines(keepends=True)
	except (OSError, UnicodeDecodeError):
		return []
	text_lines = [line.rstrip("\n") for line in lines]
	problems = []
	if path.suffix == ".py":
		if not args.no_double_blank:
			problems.extend((line, msg) for line, msg in check_double_blank(text_lines))
		if not args.no_space_indent:
			string_lines = _python_string_lines(text_lines)
			problems.extend((line, msg) for line, msg in check_space_indent_exempt(text_lines, string_lines))
		if not args.no_trailing:
			problems.extend((line, msg) for line, msg in check_trailing_whitespace(text_lines))
		if not args.no_def_one_line:
			problems.extend((line, msg) for line, msg in check_def_one_line(text_lines))
		if not args.no_def_comment:
			problems.extend((line, msg) for line, msg in check_def_comment(text_lines))
		if not args.no_final_newline:
			problems.extend((line, msg) for line, msg in check_trailing_blank(text_lines))
			problems.extend((line, msg) for line, msg in check_final_newline(lines))
		if not args.no_imports:
			problems.extend((line, msg) for line, msg in check_imports(text_lines))
		if not args.no_double_space:
			problems.extend((line, msg) for line, msg in check_double_space(text_lines, True))
	elif path.suffix == ".md":
		if not _is_tracked_file(path):
			# Untracked files are not subject to the absolute-path rule
			pass
		else:
			exempt = _frontmatter_exempt(text_lines)
			exempt.update(_fence_exempt(text_lines))
			exempt.update(_blockquote_exempt(text_lines))
			if not args.no_absolute_paths:
				problems.extend((line, msg) for line, msg in check_absolute_paths(text_lines, exempt, path))
		if not args.no_space_indent:
			exempt = _frontmatter_exempt(text_lines)
			exempt.update(_fence_exempt(text_lines))
			problems.extend((line, msg) for line, msg in check_space_indent_exempt(text_lines, exempt))
		if not args.no_trailing:
			problems.extend((line, msg) for line, msg in check_trailing_whitespace(text_lines, True))
		if not args.no_final_newline:
			problems.extend((line, msg) for line, msg in check_trailing_blank(text_lines))
			problems.extend((line, msg) for line, msg in check_final_newline(lines))
		if not args.no_double_space:
			problems.extend((line, msg) for line, msg in check_double_space(text_lines, False))
	elif path.suffix in _JS_SUFFIXES:
		if not args.no_js_double_blank:
			problems.extend((line, msg) for line, msg in check_js_double_blank(text_lines))
		if not args.no_js_space_indent:
			exempt = _js_exempt_lines(text_lines)
			problems.extend((line, msg) for line, msg in check_js_space_indent(text_lines, exempt))
		if not args.no_js_trailing:
			problems.extend((line, msg) for line, msg in check_js_trailing_whitespace(text_lines))
		if not args.no_js_final_newline:
			problems.extend((line, msg) for line, msg in check_js_trailing_blank(text_lines))
			problems.extend((line, msg) for line, msg in check_js_final_newline(lines))
	return problems

class _InotifyWatcher:
	def __init__(self, paths, exclusions):
		self.exclusions = exclusions
		self.wd_to_dir = {}
		self.fd = _libc.inotify_init()
		if self.fd == -1:
			raise OSError(ctypes.get_errno(), "inotify_init failed")
		for root in paths:
			self.watch_tree(root)

	def watch_tree(self, root):
		if root.is_file():
			self.add_dir(root.parent)
			return
		self.add_dir(root)
		for path in root.rglob("*"):
			if path.is_dir() and not is_ignored(path, self.exclusions):
				self.add_dir(path)

	def add_dir(self, path):
		wd = _libc.inotify_add_watch(self.fd, os.fsencode(path), _WATCH_MASK)
		if wd != -1:
			self.wd_to_dir[wd] = path

	def forget(self, path):
		for wd, watched in list(self.wd_to_dir.items()):
			if watched == path:
				del self.wd_to_dir[wd]

	def collect(self):
		select.select([self.fd], [], [], None)
		raw = os.read(self.fd, 65536)
		events = []
		offset = 0
		while offset < len(raw):
			wd, mask, cookie, namelen = _EVENT_HEADER.unpack_from(raw, offset)
			offset += _EVENT_HEADER.size
			path = self.wd_to_dir.get(wd)
			if path is not None and namelen:
				encoded = raw[offset:offset + namelen].split(b"\0", 1)[0]
				path = path / os.fsdecode(encoded)
			offset += (namelen + 3) & ~3
			events.extend(self._classify(wd, mask, path))
		return events

	def _classify(self, wd, mask, path):
		if path is None:
			return []
		if mask & _IN_IGNORED:
			self.wd_to_dir.pop(wd, None)
			return []
		if mask & (_IN_DELETE_SELF | _IN_MOVE_SELF):
			self.wd_to_dir.pop(wd, None)
			return [("delete_dir", path)]
		if mask & _IN_ISDIR:
			if mask & (_IN_DELETE | _IN_MOVED_FROM):
				self.forget(path)
				return [("delete_dir", path)]
			if mask & (_IN_CREATE | _IN_MOVED_TO):
				self.add_dir(path)
				return [("modify", inner) for inner in lint_files([path], self.exclusions)]
			return []
		if path.suffix not in _ALL_SUFFIXES:
			return []
		if mask & (_IN_DELETE | _IN_MOVED_FROM):
			return [("delete_file", path)]
		return [("modify", path)]

class _PollWatcher:
	def __init__(self, paths, exclusions):
		self.exclusions = exclusions
		self.paths = paths
		self.stamps = {path: stamp(path) for path in lint_files(paths, self.exclusions)}

	def collect(self):
		time.sleep(0.2)
		current = {path: stamp(path) for path in lint_files(self.paths, self.exclusions)}
		events = []
		for path, value in current.items():
			if value != self.stamps.get(path):
				events.append(("modify", path))
		for path in self.stamps:
			if path not in current:
				events.append(("delete_file", path))
		self.stamps = current
		return events

def make_watcher(paths, exclusions):
	if _libc is not None:
		try:
			return _InotifyWatcher(paths, exclusions)
		except OSError:
			pass
	return _PollWatcher(paths, exclusions)

def draw(snapshot):
	print(_CLEAR_SCREEN, end="")
	print(f"=== {NAME} ===")
	found = [(path, line, msg) for path in snapshot for line, msg in snapshot[path]]
	for path, line, msg in sorted(found):
		print(f"{path}:{line}: {msg}", flush=True)
	print(f"{len(found)} problem(s)" if found else "clean", flush=True)

def watch(paths, args, exclusions):
	snapshot = {path: check_file(path, args) for path in lint_files(paths, exclusions)}
	watcher = make_watcher(paths, exclusions)
	draw(snapshot)
	while True:
		changed = {}
		for action, path in watcher.collect():
			if action == "modify":
				changed[path] = "modify"
			else:
				changed.setdefault(path, action)
		dirty = False
		for path, action in changed.items():
			if action == "delete_file":
				dirty |= path in snapshot
				snapshot.pop(path, None)
			elif action == "delete_dir":
				for watched in list(snapshot):
					if watched == path or path in watched.parents:
						del snapshot[watched]
						dirty = True
			else:
				dirty = True
				snapshot[path] = check_file(path, args)
		if dirty:
			draw(snapshot)

def main():
	parser = argparse.ArgumentParser(description="Check Python, Markdown, and JavaScript/TypeScript files against XLib style rules")
	parser.add_argument("paths", nargs="+", type=Path)
	parser.add_argument("--watch", action="store_true", help="stay running, redraw the issue list when files change")
	parser.add_argument("--no-double-blank", action="store_true", help="disable double blank line check")
	parser.add_argument("--no-space-indent", action="store_true", help="disable space indentation check")
	parser.add_argument("--no-trailing", action="store_true", help="disable trailing whitespace check")
	parser.add_argument("--no-def-one-line", action="store_true", help="disable one-line function definition check")
	parser.add_argument("--no-def-comment", action="store_true", help="disable the check for a comment on a def line")
	parser.add_argument("--no-final-newline", action="store_true", help="disable final newline and trailing blank line checks")
	parser.add_argument("--no-imports", action="store_true", help="disable import style check")
	parser.add_argument("--no-double-space", action="store_true", help="disable mid-line double space check")
	parser.add_argument("--no-absolute-paths", action="store_true", help="disable absolute system path check in Markdown")
	parser.add_argument("--no-js-double-blank", action="store_true", help="disable JS/TS double blank line check")
	parser.add_argument("--no-js-space-indent", action="store_true", help="disable JS/TS space indentation check")
	parser.add_argument("--no-js-trailing", action="store_true", help="disable JS/TS trailing whitespace check")
	parser.add_argument("--no-js-final-newline", action="store_true", help="disable JS/TS final newline and trailing blank line checks")
	args = parser.parse_args()

	for entry in args.paths:
		if not entry.exists():
			parser.error(f"not found: {entry}")

	exclusions = _Exclusions(find_exclusion_roots(args.paths[0]))

	if args.watch:
		try:
			watch(args.paths, args, exclusions)
		except KeyboardInterrupt:
			pass
		return 0

	problems = []
	for path in lint_files(args.paths, exclusions):
		problems.extend((path, line, msg) for line, msg in check_file(path, args))
	if not problems:
		print("clean")
		return 0
	for path, line, msg in problems:
		print(f"{path}:{line}: {msg}")
	print(f"{len(problems)} problem(s)")
	return 1

if __name__ == "__main__":
	sys.exit(main())
