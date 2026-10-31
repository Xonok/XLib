import argparse,ast,contextlib,ctypes,errno,importlib.util,io,itertools,os,re,select,signal,struct,sys,tempfile,termios,time,tokenize,tomllib,types,subprocess
from pathlib import Path
try:
	_libc = ctypes.CDLL(None, use_errno=True)
	_libc.inotify_init.restype = ctypes.c_int
	_libc.inotify_init.argtypes = []
	_libc.inotify_add_watch.restype = ctypes.c_int
	_libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
	_libc.inotify_rm_watch.restype = ctypes.c_int
	_libc.inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
except AttributeError:
	_libc = None
def _inotify_failure(syscall, code, path = None):
	"""The report line for an inotify call the kernel refused.

	`code` is an errno number: the name and the message are both carried, because
	`EMFILE` says what to search for and `Too many open files` says what happened.
	"""
	where = f" for {path}" if path is not None else ""
	name = errno.errorcode.get(code, str(code))
	return f"warning: {syscall} failed{where}: {name} ({os.strerror(code)})"
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
	and `#` comments. `**` is a whole segment standing for zero or more of them, so
	`a/**/b` matches `a/b`, `a/x/b` and `a/x/y/b`. Anything outside the subset is
	treated as literal text rather than guessed at, so an unrecognised pattern cannot
	silently exclude the whole tree.
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
	parts = line.split("/")
	globstar = "(?:[^/]+/)*"
	body = ""
	for index, part in enumerate(parts):
		if part == "**":
			# The separator belongs to the globstar: it absorbs the zero or more
			# segments that follow it, including their separators, so joining the
			# next segment must not add another one. A trailing globstar takes
			# the whole remainder of the path.
			if body and not body.endswith(globstar):
				body += "/"
			body += ".*" if index == len(parts) - 1 else globstar
			continue
		if body and not body.endswith(globstar):
			body += "/"
		body += _glob_to_regex(part)
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
def _is_checkout_root(path):
	"""True when `path` is the root of a Git checkout.

	A worktree's `.git` is a *file* naming the main repository's administrative
	directory, so a lookup that recognises only a `.git` directory walks straight past
	every worktree and out into the directory that holds it.
	"""
	return (path / ".git").exists()
def find_exclusion_chain(start):
	"""Every directory from `start` upward whose ignore file could govern it, nearest first.

	The chain is the whole walk, not only the directories that hold an ignore
	file today: a file can appear in one of them, and a rule set built from the
	files that happen to exist cannot see it.

	The walk stops at the checkout that owns `start`, because an ignore file
	belongs to the repository it sits in. A worktree is a separate checkout of
	that same repository rather than a subdirectory of it, and it holds its own
	copy of the ignore file. The rule the outer repository keeps for the
	worktrees it contains (`.work/`) says nothing about what is inside one of
	them, and applying it there excluded every file the worktree held: a run
	that checked nothing, reported clean.
	"""
	chain = []
	current = start.resolve()
	if current.is_file():
		current = current.parent
	while True:
		chain.append(current)
		if _is_checkout_root(current) or current.parent == current:
			return chain
		current = current.parent
def find_exclusion_roots(start):
	"""Directories from `start` upward whose `.xlintignore` governs it, nearest first.

	Walks up so a run from a subdirectory sees the same exclusions a run from the repo
	root does, and so a nested repository's file overrides rather than disappears.
	"""
	return [directory for directory in find_exclusion_chain(start)
		if (directory / _IGNORE_FILE).is_file()]
def find_checkout_root(start):
	"""The checkout that owns `start`, or None when it is outside every checkout.

	The same walk the exclusion chain uses, because the boundary is the same
	one: a `.xlintignore` and a `tools/xlint_rules.py` both belong to the
	repository that holds them, and a worktree is its own checkout.
	"""
	root = find_exclusion_chain(start)[-1]
	return root if _is_checkout_root(root) else None
def exclusion_reason(path, exclusions=None):
	"""Why `path` is excluded, or None when it is not.

	`is_ignored` says whether a path is skipped; this says which rule skipped it, so
	a report of a skipped path can name the rule instead of guessing at one.
	"""
	if set(path.parts) & _BUILTIN_EXCLUDED:
		return "the built-in exclusions"
	if exclusions is not None and exclusions.excluded(path, path.is_dir()):
		return _IGNORE_FILE
	return None
def is_ignored(path, exclusions=None):
	return exclusion_reason(path, exclusions) is not None
def excluded_paths(paths, exclusions=None):
	"""The requested paths that are excluded, each with the rule that excluded it.

	A run over these checks nothing, and a run that checks nothing must not look like
	a run that found nothing. One of the two is a statement about the code and the
	other is a lie about it, and on a screen they are the same word.
	"""
	skipped = []
	for path in paths:
		reason = exclusion_reason(path, exclusions)
		if reason is not None:
			skipped.append((path, reason))
	return skipped
def lint_files(paths, exclusions=None):
	"""The files in scope, each path judged by the rules that govern it.

	Without a rule set each path is judged by the chain of directories above it,
	so a run over two repositories honours the ignore file of each rather than
	only the first one's.
	"""
	found = []
	for entry in paths:
		rules = exclusions if exclusions is not None else _Exclusions(find_exclusion_roots(entry))
		if entry.is_file() and entry.suffix in _ALL_SUFFIXES:
			if not is_ignored(entry, rules):
				found.append(entry)
		elif entry.is_dir():
			for path in sorted(entry.rglob("*")):
				if not is_ignored(path, rules) and path.suffix in _ALL_SUFFIXES:
					found.append(path)
	return found
def stamp(path):
	"""The state of a path: its mtime and size, or None when there is no path.

	Size as well as mtime, because a filesystem whose timestamps are coarse
	can record two changes to a file within the same tick, and a watcher that
	misses one of them reports a file it never read.
	"""
	try:
		info = path.stat()
	except OSError:
		return None
	return (info.st_mtime_ns, info.st_size)
class _IgnoreRules:
	"""The ignore rules in force for each watched path, and a way to notice a change.

	`--watch` reads `.xlintignore` once, at startup, and keeps the result for
	the life of the process, so a rule edited while the watch runs changes
	nothing until the tool is restarted — and restarting is the workaround,
	which costs the thing watch mode exists for.

	Each watched path is governed by the rules of its own chain, up to the
	checkout that owns it, so a run over two repositories honours the ignore
	file of each rather than only the first one's.

	The stamp covers every directory the chains visit, not only the ones holding
	a file today: a file that appears is as much a change as one that is
	edited, and a file that vanishes stops governing the run.
	"""

	def __init__(self, paths):
		self.paths = [Path(path) for path in paths]
		self.chains = [find_exclusion_chain(path) for path in self.paths]
		self.exclusions = [_Exclusions(self._roots(chain)) for chain in self.chains]
		self.resolved = [path.resolve() for path in self.paths]
		self.stamp = self._stamp()

	@staticmethod
	def _roots(chain):
		"""The directories of a chain that hold an ignore file."""
		return [directory for directory in chain
			if (directory / _IGNORE_FILE).is_file()]

	def _stamp(self):
		"""The state of every ignore file the chains can reach."""
		return tuple((str(directory), stamp(directory / _IGNORE_FILE))
			for chain in self.chains for directory in chain)

	def changed(self):
		"""True when an ignore file was edited, added or removed."""
		return self._stamp() != self.stamp

	def reload(self):
		"""Read the ignore files again.

		The stamp is taken before the files are read, so an ignore file edited
		while they are being read is noticed on the next pass rather than
		missed: the stamp still describes the older file, and the older file is
		not what is on disk any more.
		"""
		before = self._stamp()
		self.exclusions = [_Exclusions(self._roots(chain)) for chain in self.chains]
		self.stamp = before

	def refresh(self):
		"""Re-read the ignore files when they changed, and say whether they did.

		Both watchers call this on every pass. It is the only thing that notices
		a rule edited while the watch runs, and the only thing that lets a file
		the new rules exclude leave the report.
		"""
		if not self.changed():
			return False
		self.reload()
		return True

	def for_path(self, path):
		"""The rules that govern `path`; the built-in exclusions alone if none do.

		A path that no watched path holds is not linted, and the empty rule set
		says so: it excludes nothing of its own, so only the built-in exclusions
		apply.
		"""
		index = self.governing(path)
		if index is None:
			return _Exclusions()
		return self.exclusions[index]

	def governing(self, path):
		"""The index of the watched path whose rules govern `path`, or None.

		The deepest watched path holding it wins, the way the nearest ignore
		file wins: a file under two watched paths is judged by the rules of the
		one that holds it more closely.
		"""
		target = Path(path).resolve()
		best = None
		for index, root in enumerate(self.resolved):
			if root.is_file():
				if root != target:
					continue
			elif root != target and root not in target.parents:
				continue
			if best is None or len(root.parts) > len(self.resolved[best].parts):
				best = index
		return best

	def in_scope(self, path):
		"""True when the rules let this path be linted."""
		index = self.governing(path)
		if index is None:
			return False
		return not is_ignored(path, self.exclusions[index])

	def files(self):
		"""The files in scope, each judged by the rules of the path that holds it.

		The walk itself carries no rules of its own, and the rules are applied
		afterwards by `in_scope`: a file under two watched paths is judged by
		the deeper one, so a rule that excludes it from the outer watch must
		not exclude it from the inner one.
		"""
		found = []
		seen = set()
		for path in self.paths:
			for file in lint_files([path], _Exclusions()):
				key = file.resolve()
				if key in seen:
					continue
				seen.add(key)
				if self.in_scope(file):
					found.append(file)
		return found

	def skipped(self):
		"""The watched paths the rules exclude, each with the rule that excluded it."""
		skipped = []
		for path, exclusions in zip(self.paths, self.exclusions):
			skipped.extend(excluded_paths([path], exclusions))
		return skipped

	def watch_dirs(self):
		"""The directories a watch over these paths must cover.

		A directory the rules exclude holds nothing that is linted, so a change
		in it is not a change in the report. The rules that decide this are the
		ones governing the directory, not the ones of the watched path it
		happens to sit under: a nested checkout keeps its own rules.
		"""
		wanted = set()
		for path in self.paths:
			if path.is_file():
				wanted.add(path.parent)
				continue
			wanted.add(path)
			for child in path.rglob("*"):
				if child.is_dir() and self.in_scope(child):
					wanted.add(child)
		return wanted
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

_here = Path(__file__).resolve().parent

_DEF_PREFIX_RE = re.compile(r"^\s*(async\s+def|def)\s+\w+")

_SPACE_INDENT_RE = re.compile(r"^ +\S")

_ALIASED_NAME_RE = re.compile(r"\bas\b")

_CLEAR_SCREEN = "\033[H\033[2J\033[3J"

_ENTER_WATCH = "\033[?25l"

_LEAVE_WATCH = "\033[?25h"

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

_BUILTIN_EXCLUDED = {"__pycache__", ".git", "node_modules", "xlib_legacy"}

_IGNORE_FILE = ".xlintignore"

_POLL_SECONDS = 0.2

_INOTIFY_ADVICE = [
	"  check: cat /proc/sys/fs/inotify/max_user_instances /proc/sys/fs/inotify/max_user_watches",
	"  raise: sudo sysctl -w fs.inotify.max_user_instances=1024",
	"         sudo sysctl -w fs.inotify.max_user_watches=524288",
	"         persist in /etc/sysctl.d/60-inotify.conf",
]

_JS_SUFFIXES = (".js", ".mjs", ".cjs", ".ts", ".tsx")

_PY_MD_SUFFIXES = (".py", ".md")

_HTML_SUFFIXES = (".html",)

_C_SUFFIXES = (".c", ".h")

_SH_SUFFIXES = (".sh",)

_ALL_SUFFIXES = _PY_MD_SUFFIXES + _JS_SUFFIXES + _HTML_SUFFIXES + _C_SUFFIXES + _SH_SUFFIXES

_RULE_MODULE_SERIAL = itertools.count()

_BUILTIN_DISABLES = [
	("double-blank", "no_double_blank"),
	("space-indent", "no_space_indent"),
	("trailing", "no_trailing"),
	("def-one-line", "no_def_one_line"),
	("def-comment", "no_def_comment"),
	("final-newline", "no_final_newline"),
	("leading-blank", "no_leading_blank"),
	("imports", "no_imports"),
	("double-space", "no_double_space"),
	("absolute-paths", "no_absolute_paths"),
	("personal", "no_personal"),
	("banned-git", "no_banned_git"),
	("js-double-blank", "no_js_double_blank"),
	("js-space-indent", "no_js_space_indent"),
	("js-trailing", "no_js_trailing"),
	("js-final-newline", "no_js_final_newline"),
	("html-double-blank", "no_html_double_blank"),
	("html-space-indent", "no_html_space_indent"),
	("html-trailing", "no_html_trailing"),
	("html-final-newline", "no_html_final_newline"),
	("html-unclosed", "no_html_unclosed"),
	("html-bad-closer", "no_html_bad_closer"),
	("html-depth", "no_html_depth"),
]

_DOUBLE_SPACE_RE = re.compile(r"[^ ](  +)[^ ]")

_ABSOLUTE_PATH_RE = re.compile(r"(?:^|[\s\(\"\'])((?:/storage/|/home/[^/]+/|/root/)[^\s\)\]\}\"'>]+)")

__all__ = ['_libc', '_inotify_failure', '_Exclusions', '_compile_pattern', '_glob_to_regex', '_is_checkout_root', 'find_exclusion_chain', 'find_exclusion_roots', 'find_checkout_root', 'exclusion_reason', 'is_ignored', 'excluded_paths', 'lint_files', 'stamp', '_IgnoreRules', '_is_tracked_file', '_here', '_DEF_PREFIX_RE', '_SPACE_INDENT_RE', '_ALIASED_NAME_RE', '_CLEAR_SCREEN', '_ENTER_WATCH', '_LEAVE_WATCH', 'NAME', '_EVENT_HEADER', '_IN_CLOSE_WRITE', '_IN_MOVED_FROM', '_IN_MOVED_TO', '_IN_CREATE', '_IN_DELETE', '_IN_DELETE_SELF', '_IN_MOVE_SELF', '_IN_IGNORED', '_IN_ISDIR', '_WATCH_MASK', '_BUILTIN_EXCLUDED', '_IGNORE_FILE', '_POLL_SECONDS', '_INOTIFY_ADVICE', '_JS_SUFFIXES', '_PY_MD_SUFFIXES', '_HTML_SUFFIXES', '_C_SUFFIXES', '_SH_SUFFIXES', '_ALL_SUFFIXES', '_RULE_MODULE_SERIAL', '_BUILTIN_DISABLES', '_DOUBLE_SPACE_RE', '_ABSOLUTE_PATH_RE']
