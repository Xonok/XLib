#!/usr/bin/env python3
"""xlint — the repository's style checker.

A checkout can carry its own policy in `tools/xlint_rules.py`, or in the file
`.xlint.toml` names with `[rules] path`. The module is arbitrary Python: its
`rules()` returns `{name, paths?, check}`, and `check(files)` receives the
selected files' lines and returns findings. One module per checkout, loaded
in-process, reloaded in watch mode, and skippable with `--no-repo-rules`.
REPO_RULES.md is the contract.

Watch mode's terminal contract — cursor, scrollback, scroll position, inotify
and fitting — is recorded in TERMINAL.md.
"""

import argparse,ast,contextlib,ctypes,errno,importlib.util,io,itertools,os,re,select,signal,struct,sys,tempfile,termios,time,tokenize,tomllib,types,subprocess
from pathlib import Path

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
	sys.path.insert(0, str(_here))

try:
	from . import _html
	from . import _personal
except ImportError:
	import _html
	import _personal

_DEF_PREFIX_RE = re.compile(r"^\s*(async\s+def|def)\s+\w+")
_SPACE_INDENT_RE = re.compile(r"^ +\S")
_ALIASED_NAME_RE = re.compile(r"\bas\b")
# The screen is cleared before the saved lines, not after: tmux treats 2J as
# "move the screen into history", so erasing history first (3J) lets the next
# 2J put one screenful back, and the previous report survives. One-shot runs
# print directly and never clear.
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

_BUILTIN_EXCLUDED = {"__pycache__", ".git", "node_modules", "xlib_legacy"}
_IGNORE_FILE = ".xlintignore"
_POLL_SECONDS = 0.2
_INOTIFY_ADVICE = [
	"  check: cat /proc/sys/fs/inotify/max_user_instances /proc/sys/fs/inotify/max_user_watches",
	"  raise: sudo sysctl -w fs.inotify.max_user_instances=1024",
	"         sudo sysctl -w fs.inotify.max_user_watches=524288",
	"         persist in /etc/sysctl.d/60-inotify.conf",
]

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
	"""True when `path` is the root of a git checkout.

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

_JS_SUFFIXES = (".js", ".mjs", ".cjs", ".ts", ".tsx")
_PY_MD_SUFFIXES = (".py", ".md")
_HTML_SUFFIXES = (".html",)
_C_SUFFIXES = (".c", ".h")
# Shell scripts carry no style rules, but they are files a value can be pasted
# into — `tools/tmux-xlib.sh` named a private project in a comment — so they are
# visited for the personal-identifier check alone.
_SH_SUFFIXES = (".sh",)
_ALL_SUFFIXES = _PY_MD_SUFFIXES + _JS_SUFFIXES + _HTML_SUFFIXES + _C_SUFFIXES + _SH_SUFFIXES

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

class _RepoRuleError(Exception):
	"""A repo rule that could not be loaded or run.

	Every one of these is fatal to the run. A rule that did not run must not
	look like a rule that found nothing, so the caller exits 1 rather than
	reporting a clean tree.
	"""

_RULE_MODULE_SERIAL = itertools.count()

def _select_all(path):
	"""The matcher for a rule that names no `paths`: every file xlint visits."""
	return True

def _selection(patterns, base):
	"""A matcher for one rule's `paths`, in the `.xlintignore` pattern language.

	The patterns are relative to the checkout root, and the last match wins, so
	a negation re-includes what an earlier pattern selected — the same rule
	`.xlintignore` follows.
	"""
	compiled = [rule for rule in (_compile_pattern(line, base) for line in patterns) if rule is not None]
	base = base.resolve()
	def selects(path):
		verdict = False
		try:
			relative = Path(path).resolve().relative_to(base).as_posix()
		except ValueError:
			return False
		for negated, _, regex in compiled:
			if regex.match(relative) is not None:
				verdict = not negated
		return verdict
	return selects

def _validate_rules(entries, path, root):
	"""The `rules()` result as the run needs it, or the error that stops the run."""
	if not isinstance(entries, (list, tuple)):
		raise _RepoRuleError(f"{path}: `rules()` returned {type(entries).__name__}, expected a list")
	rules = []
	names = set()
	for index, entry in enumerate(entries, start = 1):
		if not isinstance(entry, dict):
			raise _RepoRuleError(f"{path}: rule #{index} is {type(entry).__name__}, expected a mapping")
		name = entry.get("name")
		if not isinstance(name, str) or not name:
			raise _RepoRuleError(f"{path}: rule #{index} has no name")
		if name in names:
			raise _RepoRuleError(f"{path}: duplicate rule name '{name}'")
		names.add(name)
		unknown = set(entry) - {"name", "paths", "check"}
		if unknown:
			raise _RepoRuleError(f"{path}: rule '{name}' has unknown keys: {', '.join(sorted(unknown))}")
		check = entry.get("check")
		if not callable(check):
			raise _RepoRuleError(f"{path}: rule '{name}' has no `check` callable")
		selection = entry.get("paths")
		if selection is None:
			selects = _select_all
		elif not isinstance(selection, (list, tuple)) or not all(isinstance(item, str) for item in selection):
			raise _RepoRuleError(f"{path}: rule '{name}' has `paths` that is not a list of strings")
		else:
			selects = _selection(selection, root)
		rules.append({"name": name, "check": check, "selects": selects})
	return rules

def _findings(result, path, rule):
	"""Validate one rule's return value, and normalise it to `(Path, line, message)`."""
	if result is None:
		raise _RepoRuleError(f"{path}: rule '{rule}' returned None, expected findings")
	try:
		items = list(result)
	except TypeError as error:
		raise _RepoRuleError(f"{path}: rule '{rule}' returned {type(result).__name__}, expected findings") from error
	except (Exception, SystemExit) as error:
		raise _RepoRuleError(f"{path}: rule '{rule}' raised {type(error).__name__}: {error}") from error
	found = []
	for item in items:
		if not isinstance(item, (tuple, list)) or len(item) != 3:
			raise _RepoRuleError(f"{path}: rule '{rule}' returned {item!r}, expected (path, line, message)")
		offender, line, message = item
		if not isinstance(offender, (str, os.PathLike)):
			raise _RepoRuleError(f"{path}: rule '{rule}' returned a finding whose path is {type(offender).__name__}")
		if line is not None and (not isinstance(line, int) or isinstance(line, bool) or line < 1):
			raise _RepoRuleError(f"{path}: rule '{rule}' returned line {line!r}, expected 1 or greater, or None")
		if not isinstance(message, str):
			raise _RepoRuleError(f"{path}: rule '{rule}' returned a finding whose message is {type(message).__name__}")
		found.append((Path(offender), line, rule, message))
	return found

def _load_rules(path, root):
	"""Import one rule module afresh, and validate what its `rules()` returns.

	The source is read and compiled here rather than handed to `importlib` for
	one reason: the bytecode cache keys on mtime and size, so a same-size edit
	within the filesystem's timestamp granularity would run the old code. That
	is exactly what a watch-mode reload must not do. A fresh module object is
	created each time, and dropped from `sys.modules` by the next load or by a
	failed one.
	"""
	name = f"_xlint_repo_rules_{next(_RULE_MODULE_SERIAL)}"
	try:
		source = path.read_text(encoding = "utf-8")
	except (OSError, UnicodeDecodeError) as error:
		raise _RepoRuleError(f"{path}: cannot read the module: {error}") from error
	try:
		code = compile(source, str(path), "exec")
	except SyntaxError as error:
		raise _RepoRuleError(f"{path}: import failed: SyntaxError: {error}") from error
	spec = importlib.util.spec_from_file_location(name, path,
		submodule_search_locations = [str(path.parent)] if path.name == "__init__.py" else None)
	if spec is None or spec.loader is None:
		module = types.ModuleType(name)
	else:
		module = importlib.util.module_from_spec(spec)
	module.__file__ = str(path)
	sys.modules[name] = module
	try:
		try:
			exec(code, module.__dict__)
		except (Exception, SystemExit) as error:
			raise _RepoRuleError(f"{path}: import failed: {type(error).__name__}: {error}") from error
		runner = getattr(module, "rules", None)
		if runner is None:
			raise _RepoRuleError(f"{path}: no `rules()` function")
		if not callable(runner):
			raise _RepoRuleError(f"{path}: `rules` is not callable")
		try:
			entries = runner()
		except (Exception, SystemExit) as error:
			raise _RepoRuleError(f"{path}: `rules()` raised {type(error).__name__}: {error}") from error
		return name, _validate_rules(entries, path, root)
	except BaseException:
		sys.modules.pop(name, None)
		raise

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

def _canonical_disable(name):
	"""One disable identifier in its canonical form: lower case, hyphens, no leading `no-`."""
	name = str(name).strip().lower().replace("_", "-")
	if name.startswith("no-"):
		name = name[3:]
	return name

def _add_disabled(disabled, value, where):
	"""Add disabled rule names from one config value (a list or a mapping)."""
	if isinstance(value, (list, tuple)):
		for item in value:
			if not isinstance(item, str) or not item.strip():
				raise _RepoRuleError(f"{where}: disabled entries must be non-empty strings")
			disabled.add(item.strip())
		return
	if isinstance(value, dict):
		for key, flag in value.items():
			if not isinstance(key, str) or not key.strip():
				raise _RepoRuleError(f"{where}: disabled keys must be non-empty strings")
			if flag is True:
				disabled.add(key.strip())
			elif flag is not False:
				raise _RepoRuleError(f"{where}: disabled values must be true or false")
		return
	raise _RepoRuleError(f"{where}: disabled rules must be a list or a mapping")

def _parse_disabled(data, config):
	"""The set of rule names `.xlint.toml` asks to disable."""
	disabled = set()
	# Top-level forms.
	for key in ("disable", "disabled", "disabled_rules", "disabled-rules"):
		if key in data:
			_add_disabled(disabled, data[key], f"{config}: {key}")
	# A `[disable]` table: a list under `rules`/`disabled`, or boolean entries.
	section = data.get("disable")
	if isinstance(section, dict):
		for key in ("rules", "disabled", "disabled_rules", "disabled-rules"):
			if key in section:
				_add_disabled(disabled, section[key], f"{config}: [disable].{key}")
		for key, value in section.items():
			if key in ("rules", "disabled", "disabled_rules", "disabled-rules"):
				continue
			if value is True:
				if not isinstance(key, str) or not key.strip():
					raise _RepoRuleError(f"{config}: [disable]: disabled keys must be non-empty strings")
				disabled.add(key.strip())
			elif value is not False:
				raise _RepoRuleError(f"{config}: [disable]: values must be true or false")
	# A `[rules]` table may also carry the list.
	rules_section = data.get("rules")
	if isinstance(rules_section, dict):
		for key in ("disable", "disabled", "disabled_rules", "disabled-rules"):
			if key in rules_section:
				_add_disabled(disabled, rules_section[key], f"{config}: [rules].{key}")
	return disabled

class _RepoModule:
	"""One checkout's repo rules: the module it resolves to, and its rules.

	The config is read on every load, so a `.xlint.toml` that appears, moves or
	breaks is honoured without restarting. A load that fails stores the error
	instead of raising, so watch mode can show it and retry; `problems` is
	where a stored error becomes fatal.
	"""

	def __init__(self, root):
		self.root = root
		self.config = root / ".xlint.toml"
		self.default = root / "tools" / "xlint_rules.py"
		self.target = None
		self.rules = []
		self.disabled = set()
		self.error = None
		self.module_name = None
		self.load()

	def candidates(self):
		"""The files whose change can change this checkout's rules."""
		paths = [self.config, self.default]
		if self.target is not None:
			paths.append(self.target)
		return paths

	def state(self):
		"""A stamp over the config, the default module and the configured module."""
		return tuple((str(path), stamp(path)) for path in self.candidates())

	def load(self):
		"""Read the config and load the module it names, or the default one.

		The previous module is dropped from `sys.modules` first, so a reload
		executes the file that is on disk now rather than reusing the module
		from the run before.
		"""
		self.error = None
		self.rules = []
		self.target = None
		self.disabled = set()
		if self.module_name is not None:
			sys.modules.pop(self.module_name, None)
			self.module_name = None
		try:
			data = {}
			if self.config.is_file():
				try:
					data = tomllib.loads(self.config.read_text(encoding = "utf-8"))
				except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
					raise _RepoRuleError(f"{self.config}: {error}") from error
			self.disabled = _parse_disabled(data, self.config)
			target = self._configured(data)
			if target is None and self.default.is_file():
				target = self.default
			self.target = target
			if target is None:
				return
			if not target.exists():
				raise _RepoRuleError(f"{self.config}: [rules] path does not exist: {target}")
			if not target.is_file():
				raise _RepoRuleError(f"{self.config}: [rules] path is not a file: {target}")
			self.module_name, self.rules = _load_rules(target, self.root)
		except _RepoRuleError as error:
			self.error = error

	def _configured(self, data = None):
		"""The path `.xlint.toml` names, or None when it has no `[rules]` table.

		The path is relative to the checkout root and must stay inside it. An
		absolute path, or one that climbs out with `..`, is an error rather than
		a silent load of a file the repository does not carry.
		"""
		if data is None:
			if not self.config.is_file():
				return None
			try:
				data = tomllib.loads(self.config.read_text(encoding = "utf-8"))
			except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
				raise _RepoRuleError(f"{self.config}: {error}") from error
		section = data.get("rules")
		if section is None:
			return None
		if not isinstance(section, dict):
			raise _RepoRuleError(f"{self.config}: [rules] must be a table")
		path = section.get("path")
		if path is None:
			# A [rules] table with no path is allowed when it only disables rules.
			if "path" not in section and not any(key in section for key in ("disable", "disabled", "disabled_rules", "disabled-rules")):
				raise _RepoRuleError(f"{self.config}: [rules] needs a `path` string")
			if "path" not in section:
				return None
		if not isinstance(path, str) or not path:
			raise _RepoRuleError(f"{self.config}: [rules] needs a `path` string")
		candidate = Path(path)
		if candidate.is_absolute():
			raise _RepoRuleError(f"{self.config}: [rules] path must stay inside the checkout: {path}")
		target = (self.root / candidate).resolve()
		if target != self.root and self.root not in target.parents:
			raise _RepoRuleError(f"{self.config}: [rules] path must stay inside the checkout: {path}")
		return target

class _RepoRules:
	"""Every checkout a run touches, and the repo rules each one carries.

	The watched paths decide which checkouts exist at startup; a nested
	checkout is discovered when one of its files reaches `problems`, and its
	own module governs those files from then on. A path outside every checkout
	has no repo rules.
	"""

	def __init__(self, paths):
		self.paths = [Path(path) for path in paths]
		self.entries = {}
		for path in self.paths:
			root = find_checkout_root(path)
			if root is not None:
				self._entry(root)
		self.state = self._state()
		# Per-rule finding cache: (root, rule name) -> list of (Path, line, rule, msg).
		# Used to skip re-running a rule whose selected files did not change.
		self._cache = {}

	def _entry(self, root):
		"""The rules of one checkout, loaded on first use."""
		if root not in self.entries:
			self.entries[root] = _RepoModule(root)
		return self.entries[root]

	def _state(self):
		"""A stamp over every file that can change the loaded rules."""
		return tuple((str(root), entry.state()) for root, entry in self.entries.items())

	def watch_dirs(self):
		"""The directories whose files can change the rules.

		The nearest existing parent is used for a candidate that does not exist
		yet, because inotify cannot watch a directory that is not there; the
		checkout root is watched so the creation of `tools/` is seen.
		"""
		dirs = set()
		for entry in self.entries.values():
			for path in entry.candidates():
				parent = path.parent
				while not parent.is_dir() and parent != parent.parent:
					parent = parent.parent
				dirs.add(parent)
		return dirs

	def refresh(self):
		"""Reload the rules when a config or module changed, and say whether it did."""
		before = self._state()
		if before == self.state:
			return False
		for entry in self.entries.values():
			entry.load()
		self._cache.clear()
		self.state = before
		return True

	def problems(self, files, changed = None):
		"""The findings of every checkout's rules over `files`.

		Each rule is called once with every file it selects, so a rule can
		compare files. A load or run error is raised: a rule that did not run
		must not be mistaken for one that found nothing.

		`changed`, when given, is the set of files whose content moved since the
		last pass. A rule whose selected files are none of them is not re-run:
		its cached findings are reused instead, filtered to the files still in
		scope. A rule that touches a changed file is re-run over its *full*
		selected set, so a rule that compares files still sees every file it
		needs. Pass `changed = None` (the default) to force a full pass and
		repopulate the cache — rule reloads and one-shot runs do this.
		"""
		grouped = {root: [] for root in self.entries}
		for path in files:
			root = find_checkout_root(path)
			if root is None:
				continue
			self._entry(root)
			grouped.setdefault(root, []).append(path)
		for root in list(self.entries):
			entry = self.entries[root]
			if entry.error is not None:
				raise entry.error
		file_set = set(files)
		found = []
		for root, group in grouped.items():
			entry = self.entries[root]
			texts = {}
			for path in group:
				try:
					texts[path] = path.read_text(encoding = "utf-8").splitlines()
				except (OSError, UnicodeDecodeError):
					continue
			if "*" in entry.disabled or "repo-rules" in entry.disabled or "repo_rules" in entry.disabled:
				continue
			for rule in entry.rules:
				if rule["name"] in entry.disabled:
					continue
				selected_paths = [path for path in group if path in texts and rule["selects"](path)]
				# Incremental skip: if nothing this rule selects changed, reuse cache.
				if changed is not None and not any(path in changed for path in selected_paths):
					cached = self._cache.get((root, rule["name"]))
					if cached is not None:
						found.extend(item for item in cached if item[0] in file_set)
					continue
				selected = [(path, texts[path]) for path in selected_paths]
				try:
					result = rule["check"](selected)
				except (Exception, SystemExit) as error:
					raise _RepoRuleError(f"{entry.target}: rule '{rule['name']}' raised {type(error).__name__}: {error}") from error
				findings = _findings(result, entry.target, rule["name"])
				self._cache[(root, rule["name"])] = findings
				found.extend(item for item in findings if item[0] in file_set)
		return found

class _Rules:
	"""The rule set in force for one run: built-in exclusions plus repo rules.

	`_IgnoreRules` decides what is in scope; `_RepoRules` decides what the
	checkouts in scope add to the report. They are separate because an ignore
	file can exclude a file from the run, and a repo rule cannot: a rule
	selects files to inspect, and the report is built from every file the run
	visits.
	"""

	def __init__(self, paths, repo_rules = True):
		self.ignores = _IgnoreRules(paths)
		self.repo = _RepoRules(paths) if repo_rules else None

	def files(self):
		return self.ignores.files()

	def skipped(self):
		return self.ignores.skipped()

	def watch_dirs(self):
		dirs = self.ignores.watch_dirs()
		if self.repo is not None:
			dirs |= self.repo.watch_dirs()
		return dirs

	def for_path(self, path):
		return self.ignores.for_path(path)

	def in_scope(self, path):
		return self.ignores.in_scope(path)

	def refresh(self):
		changed = self.ignores.refresh()
		if self.repo is not None and self.repo.refresh():
			changed = True
		return changed

	def repo_problems(self, files, changed = None):
		"""The repo findings, or an empty list when `--no-repo-rules` is in force."""
		if self.repo is None:
			return []
		return self.repo.problems(files, changed = changed)

	@property
	def disabled(self):
		"""The rule names `.xlint.toml` disables across the checkouts in scope."""
		if self.repo is None:
			return set()
		out = set()
		for entry in self.repo.entries.values():
			out |= entry.disabled
		return out

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

_ABSOLUTE_PATH_RE = re.compile(r"(?:^|[\s\(\"\'])((?:/storage/|/home/[^/]+/|/root/)[^\s\)\]\}\"'>]+)")

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

def check_leading_blank(lines):
	"""Report a file whose first line is empty.

	An empty line at the start of a file is never intended: it pushes every
	line number down by one and serves no formatting purpose. The check is
	language-agnostic, so every language xlint checks gets it.
	"""
	if lines and not lines[0].strip():
		return [(1, "empty line at start of file")]
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

def _disabled_canonical(args):
	"""Canonical disabled rule names from an args namespace, if any."""
	raw = getattr(args, "disabled", None)
	if raw is None:
		raw = getattr(args, "disabled_rules", None)
	if raw is None:
		return set()
	if isinstance(raw, str):
		raw = [raw]
	try:
		items = list(raw)
	except TypeError:
		return set()
	return {_canonical_disable(item) for item in items if isinstance(item, str)}

def _apply_disabled_to_args(args, rules):
	"""Let a workspace's `.xlint.toml` disable built-in rules via args flags."""
	disabled = getattr(rules, "disabled", set()) if rules is not None else set()
	canonical = {_canonical_disable(item) for item in disabled}
	args.disabled = set(disabled) | _disabled_canonical(args)
	for key, attr in _BUILTIN_DISABLES:
		if key in canonical:
			setattr(args, attr, True)

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
	return problems

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

@contextlib.contextmanager
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

if __name__ == "__main__":
	sys.exit(main())
