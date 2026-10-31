import argparse,ast,contextlib,ctypes,errno,importlib.util,io,itertools,os,re,select,signal,struct,sys,tempfile,termios,time,tokenize,tomllib,types,subprocess
from pathlib import Path
try:
	from ._io import *
except ImportError:
	from _io import *
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
def _python_docstring_lines(lines):
	"""The line numbers of the docstrings in a Python file.

	A docstring is prose about the code, and a string literal is a value. The
	absolute-path check needs the difference: a docstring that says where this
	tool lives names a location, and a string literal that looks like a path is
	usually a fixture.
	"""
	source = "".join(line + "\n" for line in lines)
	try:
		tree = ast.parse(source)
	except (SyntaxError, ValueError):
		return set()
	docstrings = set()
	for node in ast.walk(tree):
		if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
			continue
		if not node.body:
			continue
		first = node.body[0]
		if not isinstance(first, ast.Expr):
			continue
		if not isinstance(first.value, ast.Constant) or not isinstance(first.value.value, str):
			continue
		for ln in range(first.value.lineno, (first.value.end_lineno or first.value.lineno) + 1):
			docstrings.add(ln)
	return docstrings
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

__all__ = ['_python_exempt_spans', '_python_string_lines', '_python_docstring_lines', '_is_permitted_multiline', '_one_argument_per_line', '_spanned_def_lines', '_signature_end', '_is_gap', 'check_def_one_line', '_def_lines', '_comment_lines', 'check_def_comment', 'check_imports']
