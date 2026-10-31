import argparse,ast,contextlib,ctypes,errno,importlib.util,io,itertools,os,re,select,signal,struct,sys,tempfile,termios,time,tokenize,tomllib,types,subprocess
from pathlib import Path
try:
	from ._io import *
except ImportError:
	from _io import *
class _RepoRuleError(Exception):
	"""A repo rule that could not be loaded or run.

	Every one of these is fatal to the run. A rule that did not run must not
	look like a rule that found nothing, so the caller exits 1 rather than
	reporting a clean tree.
	"""
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

__all__ = ['_RepoRuleError', '_select_all', '_selection', '_validate_rules', '_findings', '_load_rules', '_canonical_disable', '_add_disabled', '_parse_disabled', '_RepoModule', '_RepoRules', '_Rules', '_disabled_canonical', '_apply_disabled_to_args']
