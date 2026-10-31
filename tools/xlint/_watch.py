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
class _InotifyWatcher:
	"""The inotify backend: a watch on every directory the rules allow.

	The watch set is built from the rules in force, so a rule that changes
	which directories are in scope changes what is watched — in both
	directions, because a directory the rules now exclude has to stop being
	watched as surely as one they now include has to start.
	"""

	def __init__(self, rules):
		self.rules = rules
		self.fd = None
		self.wd_to_dir = {}
		self.failed = []
		self.rebuild()

	def notices(self):
		"""What the report says about the calls the kernel refused.

		The notices stay for as long as the degradation does, because a message
		printed once is erased by the next redraw — watch mode clears the screen
		and the saved lines together.
		"""
		if not self.failed:
			return []
		return ([_inotify_failure(*failure) + " — not watched" for failure in self.failed]
			+ _INOTIFY_ADVICE)

	def rebuild(self):
		"""Watch the directories the rules allow now, and nothing else.

		The whole set is registered afresh on a new descriptor: a watch the
		kernel has already dropped may have been handed to another directory,
		and releasing it by name would release the wrong one. A new descriptor
		starts from nothing, and the old one goes away with its watches.
		"""
		self._close()
		self.fd = _libc.inotify_init()
		if self.fd == -1:
			raise OSError(ctypes.get_errno(), "inotify_init failed")
		self.wd_to_dir = {}
		self.failed = []
		for path in self.rules.watch_dirs():
			self.add_dir(path)

	def _close(self):
		if self.fd is not None:
			os.close(self.fd)
			self.fd = None

	def watched_dirs(self):
		"""The directories under a watch right now."""
		return set(self.wd_to_dir.values())

	def add_dir(self, path):
		wd = _libc.inotify_add_watch(self.fd, os.fsencode(path), _WATCH_MASK)
		if wd == -1:
			self.failed.append(("inotify_add_watch", ctypes.get_errno(), path))
			return
		self.wd_to_dir[wd] = path

	def forget(self, path):
		"""Stop tracking a directory the kernel has already dropped."""
		for wd, watched in list(self.wd_to_dir.items()):
			if watched == path:
				del self.wd_to_dir[wd]

	def collect(self):
		"""The changes since the last call, as (action, path) pairs."""
		events = []
		ready, _, _ = select.select([self.fd], [], [], _POLL_SECONDS)
		if ready:
			raw = os.read(self.fd, 65536)
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
		if self.rules.refresh():
			# The rules moved, so the directories in scope moved with them: the
			# watch is built again over the new scope, and the report is built
			# again from it.
			self.rebuild()
			return [("rules", None)]
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
				exclusions = self.rules.for_path(path)
				if is_ignored(path, exclusions):
					return []
				self.add_dir(path)
				return [("modify", inner) for inner in lint_files([path], exclusions)]
			return []
		if path.suffix not in _ALL_SUFFIXES:
			return []
		if mask & (_IN_DELETE | _IN_MOVED_FROM):
			return [("delete_file", path)]
		if not self.rules.in_scope(path):
			# The rules exclude this file now, so it is no part of the report.
			# A file ignored a moment ago must not come back because it was
			# touched afterwards.
			return []
		return [("modify", path)]
class _PollWatcher:
	"""The polling backend: a stamp on every file in scope, compared each pass.

	Used where inotify is not available, and it is the one backend that has to
	walk the tree every poll — so the rules are re-read here too, and the two
	backends notice the same change at the same moment.
	"""

	def __init__(self, rules, notices = ()):
		self.rules = rules
		self.stamps = {path: stamp(path) for path in rules.files()}
		self._notices = list(notices)

	def notices(self):
		"""The report lines for the inotify failure that made polling the backend."""
		return list(self._notices)

	def collect(self):
		"""The changes since the last call, as (action, path) pairs."""
		time.sleep(_POLL_SECONDS)
		if self.rules.refresh():
			self.stamps = {path: stamp(path) for path in self.rules.files()}
			return [("rules", None)]
		current = {path: stamp(path) for path in self.rules.files()}
		events = []
		for path, value in current.items():
			if value != self.stamps.get(path):
				events.append(("modify", path))
		for path in self.stamps:
			if path not in current:
				events.append(("delete_file", path))
		self.stamps = current
		return events
def make_watcher(rules):
	if _libc is not None:
		try:
			return _InotifyWatcher(rules)
		except OSError as error:
			return _PollWatcher(rules,
				[_inotify_failure("inotify_init", error.errno) + " — polling instead"]
				+ _INOTIFY_ADVICE)
	return _PollWatcher(rules)
def _watch_cursor():
	"""Hide the cursor for the watch, and leave the scrollback where it is.

	The report can be taller than the pane, and the error list is worth more
	than a fixed layout: it stays on the normal screen, so the terminal's own
	scrollback holds the lines above the fold and copy-mode keeps the reader's
	place. The alternate screen would throw that away.
	"""
	_stdin_fd = None
	_old_attrs = None
	if sys.stdin.isatty():
		try:
			_stdin_fd = sys.stdin.fileno()
			_old_attrs = termios.tcgetattr(_stdin_fd)
			_new_attrs = termios.tcgetattr(_stdin_fd)
			_new_attrs[3] &= ~(termios.ECHO | getattr(termios, "ECHOCTL", 0))
			termios.tcsetattr(_stdin_fd, termios.TCSANOW, _new_attrs)
		except (termios.error, OSError, AttributeError):
			_stdin_fd = None
			_old_attrs = None
	sys.stdout.write(_ENTER_WATCH)
	sys.stdout.flush()
	try:
		yield
	finally:
		if _old_attrs is not None and _stdin_fd is not None:
			try:
				termios.tcsetattr(_stdin_fd, termios.TCSANOW, _old_attrs)
			except (termios.error, OSError):
				pass
		sys.stdout.write(_LEAVE_WATCH)
		sys.stdout.flush()
def _finding_text(path, line, message, rule=None):
	"""One finding as the report prints it; a file-level finding has no line."""
	if line is None:
		text = f"{path}: {message}"
	else:
		text = f"{path}:{line}: {message}"
	if rule is not None:
		text = f"{text} ({rule})"
	return text
def _finding_key(finding):
	"""The report's order, with a file-level finding sorting before line 1."""
	path, line, rule, message = finding
	return (str(path), -1 if line is None else line, message)
def _write_output(path, content):
	"""Atomically write `content` to `path`: temp file in the same directory, then rename."""
	path = Path(path)
	parent = path.parent
	if str(parent) and not parent.exists():
		parent.mkdir(parents=True, exist_ok=True)
	fd, tmp = tempfile.mkstemp(prefix=".xlint-", dir=str(parent) if str(parent) else ".")
	try:
		with os.fdopen(fd, "w", encoding="utf-8") as handle:
			handle.write(content)
			handle.flush()
			os.fsync(handle.fileno())
		os.replace(tmp, path)
	except BaseException:
		try:
			os.unlink(tmp)
		except OSError:
			pass
		raise
def draw(snapshot, skipped=(), notices=(), repo=(), error=None, output=None):
	print(_CLEAR_SCREEN, end="")
	print(f"=== {NAME} ===")
	for notice in notices:
		print(notice)
	if error is not None:
		print(f"repo rules: {error}", flush=True)
	for entry, reason in skipped:
		print(f"{entry}: excluded by {reason} — nothing checked", flush=True)
	found = [(path, line, rule, msg) for path in snapshot for line, rule, msg in snapshot[path]]
	found.extend(repo)
	ordered = sorted(found, key=_finding_key)
	for path, line, rule, msg in ordered:
		print(_finding_text(path, line, msg, rule), flush=True)
	if found:
		print(f"{len(found)} problem(s)", flush=True)
	elif error is not None:
		print("repo rules failed", flush=True)
	elif skipped:
		print("nothing checked", flush=True)
	else:
		print("clean", flush=True)
	if output is not None:
		_write_output(output, "".join(_finding_text(path, line, msg, rule) + "\n" for path, line, rule, msg in ordered))
def _repo_report(rules, files, changed = None):
	"""The repo findings, or the load/run error that replaced them."""
	try:
		return rules.repo_problems(files, changed = changed), None
	except _RepoRuleError as error:
		return [], str(error)
def watch(rules, args):
	"""Watch the paths, and redraw the report as they change.

	The rules are part of what is watched: a rule edited while the watch runs
	moves the scope, and a scope that moved is read again from the top. That is
	the only way a newly ignored file can leave the report and a newly
	un-ignored one can enter it — and the reload prints nothing of its own, so
	what the screen shows is the report and nothing else. A repo rule module is
	a rule too: its errors are shown and retried when the module or config
	changes, rather than ending the watch.
	"""
	with _watch_cursor():
		files = rules.files()
		snapshot = {path: check_file(path, args) for path in files}
		repo, error = _repo_report(rules, files)
		skipped = rules.skipped()
		watcher = make_watcher(rules)
		notices = watcher.notices()
		draw(snapshot, skipped, notices, repo, error, output=getattr(args, 'output', None))
		while True:
			changed = {}
			reloaded = False
			for action, path in watcher.collect():
				if action == "rules":
					reloaded = True
					break
				if action == "modify":
					changed[path] = "modify"
				else:
					changed.setdefault(path, action)
			if reloaded:
				_apply_disabled_to_args(args, rules)
				files = rules.files()
				snapshot = {path: check_file(path, args) for path in files}
				repo, error = _repo_report(rules, files)
				skipped = rules.skipped()
				notices = watcher.notices()
				draw(snapshot, skipped, notices, repo, error, output=getattr(args, 'output', None))
				continue
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
			# A directory that could not be watched is a change to the report too:
			# the notice appears without any file event to carry it there.
			current_notices = watcher.notices()
			if current_notices != notices:
				dirty = True
				notices = current_notices
			if dirty:
				repo_changed = False
				changed_paths = set(changed)
				delete_dir = False
				if rules.repo is not None:
					for path, action in changed.items():
						if action == "delete_dir":
							delete_dir = True
							repo_changed = True
							break
						for entry in rules.repo.entries.values():
							for rule in entry.rules:
								if rule["selects"](path):
									repo_changed = True
									break
							if repo_changed:
								break
						if repo_changed:
							break
				if repo_changed:
					if delete_dir:
						repo, error = _repo_report(rules, list(snapshot))
					else:
						repo, error = _repo_report(rules, list(snapshot), changed = changed_paths)
				else:
					# Repo rules did not need to re-run; drop findings for files that
					# are no longer in scope so a deletion still clears the report.
					repo = [item for item in repo if item[0] in snapshot]
				draw(snapshot, skipped, notices, repo, error, output=getattr(args, 'output', None))

__all__ = ['_InotifyWatcher', '_PollWatcher', 'make_watcher', '_watch_cursor', '_finding_text', '_finding_key', '_write_output', 'draw', '_repo_report', 'watch']
