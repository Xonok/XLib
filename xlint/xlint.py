import argparse,ctypes,os,re,select,struct,sys,time
from pathlib import Path

_DEF_PREFIX_RE = re.compile(r"^\s*(async\s+def|def)\s+\w+")
_SPACE_INDENT_RE = re.compile(r"^ +\S")
_CLEAR_SCREEN = "\033[2J\033[H"
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
	return "__pycache__" in parts or ".git" in parts

def python_files(paths):
	found = []
	for entry in paths:
		if entry.is_file() and entry.suffix == ".py":
			found.append(entry)
		elif entry.is_dir():
			for path in sorted(entry.rglob("*.py")):
				if not is_ignored(path):
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

def check_trailing_whitespace(lines):
	report = []
	for index, line in enumerate(lines, start=1):
		if line != line.rstrip():
			report.append((index, "trailing whitespace"))
	return report

def check_def_one_line(lines):
	report = []
	for index, line in enumerate(lines, start=1):
		open_paren = line.find("(")
		if open_paren == -1:
			continue
		if not _DEF_PREFIX_RE.match(line[:open_paren]):
			continue
		if not re.match(r"\(.*\)\s*:\s*$", line[open_paren:]):
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
				if "." not in names:
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
				return [("modify", inner) for inner in python_files([path])]
			return []
		if path.suffix != ".py":
			return []
		if mask & (_IN_DELETE | _IN_MOVED_FROM):
			return [("delete_file", path)]
		return [("modify", path)]

class _PollWatcher:
	def __init__(self, paths):
		self.paths = paths
		self.stamps = {path: stamp(path) for path in python_files(paths)}

	def collect(self):
		time.sleep(0.2)
		current = {path: stamp(path) for path in python_files(self.paths)}
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
	found = [(path, line, msg) for path in snapshot for line, msg in snapshot[path]]
	print(f"{len(found)} problem(s)" if found else "clean", end="\n\n", flush=True)
	for path, line, msg in sorted(found):
		print(f"{path}:{line}: {msg}", flush=True)

def watch(paths, args):
	snapshot = {path: check_file(path, args) for path in python_files(paths)}
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
	parser = argparse.ArgumentParser(description="Check python files against XLib style rules")
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
	for path in python_files(args.paths):
		problems.extend((path, line, msg) for line, msg in check_file(path, args))
	if not problems:
		return 0
	for path, line, msg in problems:
		print(f"{path}:{line}: {msg}")
	return 1

if __name__ == "__main__":
	sys.exit(main())
