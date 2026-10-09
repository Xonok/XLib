import argparse,ast,ctypes,os,re,select,struct,sys,time
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

def is_ignored(path):
	parts = set(path.parts)
	excluded = {"__pycache__", ".git", "node_modules", "xlib_legacy", "test"}
	return bool(parts & excluded)

def lint_files(paths):
	found = []
	for entry in paths:
		if entry.is_file() and entry.suffix in (".py", ".md"):
			found.append(entry)
		elif entry.is_dir():
			for path in sorted(entry.rglob("*")):
				if not is_ignored(path) and path.suffix in (".py", ".md"):
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
	exempt = set()
	in_fence = False
	fence_char = None
	fence_len = 0
	for i, line in enumerate(lines, start=1):
		if not line:
			if in_fence:
				exempt.add(i)
			continue
		if line[0].isspace():
			if in_fence:
				exempt.add(i)
			continue
		ch = line[0]
		if ch not in ("`", "~"):
			if in_fence:
				exempt.add(i)
			continue
		count = 0
		for c in line:
			if c == ch:
				count += 1
			else:
				break
		if count >= 3:
			if not in_fence:
				in_fence = True
				fence_char = ch
				fence_len = count
			else:
				if ch == fence_char and count >= fence_len:
					in_fence = False
					fence_char = None
					fence_len = 0
				else:
					exempt.add(i)
		else:
			if in_fence:
				exempt.add(i)
	return exempt

def check_trailing_whitespace(lines):
	report = []
	for index, line in enumerate(lines, start=1):
		if line != line.rstrip() and line.strip():
			report.append((index, "trailing whitespace"))
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
	for index, line in enumerate(lines, start=1):
		open_paren = line.find("(")
		if open_paren == -1:
			continue
		if not _DEF_PREFIX_RE.match(line[:open_paren]):
			continue
		if spans is not None:
			spanned = spans.get(index)
			if spanned is None:
				end = None
			else:
				node, end = spanned
				if end == index:
					continue
				if end <= len(lines) and _is_permitted_multiline(lines, node, end):
					continue
		elif not re.match(r"\(.*\)\s*(->\s*.+)?\s*:\s*$", line[open_paren:].split("#", 1)[0].rstrip()):
			continue
		report.append((index, "function definition split across lines"))
	return report

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
			problems.extend((line, msg) for line, msg in check_space_indent(text_lines))
		if not args.no_trailing:
			problems.extend((line, msg) for line, msg in check_trailing_whitespace(text_lines))
		if not args.no_def_one_line:
			problems.extend((line, msg) for line, msg in check_def_one_line(text_lines))
		if not args.no_final_newline:
			problems.extend((line, msg) for line, msg in check_final_newline(lines))
		if not args.no_imports:
			problems.extend((line, msg) for line, msg in check_imports(text_lines))
	elif path.suffix == ".md":
		if not args.no_space_indent:
			exempt = _frontmatter_exempt(text_lines)
			exempt.update(_fence_exempt(text_lines))
			problems.extend((line, msg) for line, msg in check_space_indent_exempt(text_lines, exempt))
		if not args.no_final_newline:
			problems.extend((line, msg) for line, msg in check_final_newline(lines))
	return problems

class _InotifyWatcher:
	def __init__(self, paths):
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
			if path.is_dir() and not is_ignored(path):
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
				return [("modify", inner) for inner in lint_files([path])]
			return []
		if path.suffix not in (".py", ".md"):
			return []
		if mask & (_IN_DELETE | _IN_MOVED_FROM):
			return [("delete_file", path)]
		return [("modify", path)]

class _PollWatcher:
	def __init__(self, paths):
		self.paths = paths
		self.stamps = {path: stamp(path) for path in lint_files(paths)}

	def collect(self):
		time.sleep(0.2)
		current = {path: stamp(path) for path in lint_files(self.paths)}
		events = []
		for path, value in current.items():
			if value != self.stamps.get(path):
				events.append(("modify", path))
		for path in self.stamps:
			if path not in current:
				events.append(("delete_file", path))
		self.stamps = current
		return events

def make_watcher(paths):
	if _libc is not None:
		try:
			return _InotifyWatcher(paths)
		except OSError:
			pass
	return _PollWatcher(paths)

def draw(snapshot):
	print(_CLEAR_SCREEN, end="")
	print(f"=== {NAME} ===")
	found = [(path, line, msg) for path in snapshot for line, msg in snapshot[path]]
	print(f"{len(found)} problem(s)" if found else "clean", end="\n\n", flush=True)
	for path, line, msg in sorted(found):
		print(f"{path}:{line}: {msg}", flush=True)

def watch(paths, args):
	snapshot = {path: check_file(path, args) for path in lint_files(paths)}
	watcher = make_watcher(paths)
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
	parser = argparse.ArgumentParser(description="Check Python files against XLib style rules, and Markdown files for space indentation (code fences and frontmatter exempt)")
	parser.add_argument("paths", nargs="+", type=Path)
	parser.add_argument("--watch", action="store_true", help="stay running, redraw the issue list when files change")
	parser.add_argument("--no-double-blank", action="store_true", help="disable double blank line check")
	parser.add_argument("--no-space-indent", action="store_true", help="disable space indentation check")
	parser.add_argument("--no-trailing", action="store_true", help="disable trailing whitespace check")
	parser.add_argument("--no-def-one-line", action="store_true", help="disable one-line function definition check")
	parser.add_argument("--no-final-newline", action="store_true", help="disable final newline check")
	parser.add_argument("--no-imports", action="store_true", help="disable import style check")
	args = parser.parse_args()

	for entry in args.paths:
		if not entry.exists():
			parser.error(f"not found: {entry}")

	if args.watch:
		try:
			watch(args.paths, args)
		except KeyboardInterrupt:
			pass
		return 0

	problems = []
	for path in lint_files(args.paths):
		problems.extend((path, line, msg) for line, msg in check_file(path, args))
	if not problems:
		return 0
	for path, line, msg in problems:
		print(f"{path}:{line}: {msg}")
	return 1

if __name__ == "__main__":
	sys.exit(main())
