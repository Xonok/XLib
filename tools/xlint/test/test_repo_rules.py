"""Repo-specific rules: a checkout's own lint policy, loaded beside it.

A repository's policy should live in that repository, not in the shared
`tools/xlint/xlint.py`. The default module is `<checkout>/tools/xlint_rules.py`;
`.xlint.toml` is only the backup when that location does not fit. One module
per checkout, so a worktree and a nested checkout each govern their own files.

These tests pin the load path, the contract, the failure modes and the watch
reload. The failures are the half that matters: a rule that did not run must
never look like a rule that found nothing, so every load or run error is a hard
error rather than a pass.

A fixture checkout needs a `.git` entry because a path outside a checkout has
no repo rules. It is created as a directory, except in the worktree test where
it is the file a real worktree carries.
"""
import subprocess,sys,tempfile,threading,time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "dev" / "xtest"))
sys.path.insert(0, str(ROOT))

import xtest
from tools.xlint import xlint

XLINT = ROOT / "tools" / "xlint" / "xlint.py"

def _checkout(folder, name = "repo"):
	"""A checkout holding one clean Python file, and the `.git` that owns it."""
	root = Path(folder) / name
	root.mkdir(parents = True)
	(root / ".git").mkdir()
	(root / "code.py").write_text("x = 1\n", encoding = "utf-8")
	return root

def _module(root, source, relative = "tools/xlint_rules.py"):
	"""Write one repo rule module, creating the directories it needs."""
	path = root / relative
	path.parent.mkdir(parents = True, exist_ok = True)
	path.write_text(source, encoding = "utf-8")
	return path

def _flag_rule(message, paths = ("code.py",)):
	"""A module whose one rule reports `message` on every selected file."""
	selection = "" if paths is None else f", \"paths\": {list(paths)!r}"
	return (
		"def rules():\n"
		f"\treturn [{{\"name\": \"flag\", \"check\": check{selection}}}]\n"
		"\n"
		"def check(files):\n"
		f"\treturn [(path, 1, {message!r}) for path, lines in files]\n"
	)

def _names_rule(paths = None):
	"""A module whose one rule reports every selected file's name, at file level."""
	selection = "" if paths is None else f", \"paths\": {list(paths)!r}"
	return (
		"def rules():\n"
		f"\treturn [{{\"name\": \"names\", \"check\": check{selection}}}]\n"
		"\n"
		"def check(files):\n"
		"\treturn [(path, None, path.name) for path, lines in files]\n"
	)

def _problems(root):
	"""The repo findings for one checkout, through the composite rule set."""
	rules = xlint._Rules([root])
	return rules.repo_problems(rules.files())

def _messages(found):
	"""The messages alone, so a test asserts on what is reported and not its order."""
	return sorted(message for _, _, message in found)

def _error(fn):
	"""The message of the repo-rule error `fn` raises, or a failure if it passes."""
	try:
		fn()
	except xlint._RepoRuleError as error:
		return str(error)
	raise AssertionError("expected _RepoRuleError")

def _start_watch(root):
	"""Watch `root` in a real process, and collect what it prints."""
	proc = subprocess.Popen([sys.executable, str(XLINT), "--watch", str(root)],
		stdout = subprocess.PIPE, stderr = subprocess.STDOUT, text = True)
	lines = []
	def reader():
		for line in proc.stdout:
			lines.append(line)
	threading.Thread(target = reader, daemon = True).start()
	return proc, lines

def _stop_watch(proc):
	"""End the watch, and give it a moment to go."""
	proc.terminate()
	try:
		proc.wait(timeout = 5)
	except subprocess.TimeoutExpired:
		proc.kill()
		proc.wait(timeout = 5)
	if proc.stdout is not None:
		proc.stdout.close()

def _wait_for(lines, needle, timeout = 20.0):
	"""Wait for `needle` to appear in the output, and say whether it did."""
	deadline = time.time() + timeout
	while time.time() < deadline:
		if any(needle in line for line in lines):
			return True
		time.sleep(0.05)
	return False

def test_a_default_module_is_loaded_without_a_config():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, _flag_rule("flagged"))
		xtest.equal(_messages(_problems(root)), ["flagged"])

def test_a_config_selects_another_module():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, _flag_rule("default"))
		_module(root, _flag_rule("config"), "lint/policy.py")
		(root / ".xlint.toml").write_text('[rules]\npath = "lint/policy.py"\n', encoding = "utf-8")
		xtest.equal(_messages(_problems(root)), ["config"])

def test_a_config_can_point_at_a_package():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, "def check(files):\n\treturn [(path, 1, \"packaged\") for path, lines in files]\n", "lint/helper.py")
		_module(root, (
			"from . import helper\n"
			"\n"
			"def rules():\n"
			"\treturn [{\"name\": \"packaged\", \"paths\": [\"code.py\"], \"check\": helper.check}]\n"
		), "lint/__init__.py")
		(root / ".xlint.toml").write_text('[rules]\npath = "lint/__init__.py"\n', encoding = "utf-8")
		xtest.equal(_messages(_problems(root)), ["packaged"])

def test_an_unknown_rule_key_is_an_error():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, (
			"def rules():\n"
			"\treturn [{\"name\": \"one\", \"path\": [\"code.py\"], \"check\": check}]\n"
			"\n"
			"def check(files):\n"
			"\treturn []\n"
		))
		xtest.contains("unknown keys: path", _error(lambda: _problems(root)))

def test_a_config_without_rules_uses_the_default():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, _flag_rule("default"))
		(root / ".xlint.toml").write_text('[other]\npath = "lint/policy.py"\n', encoding = "utf-8")
		xtest.equal(_messages(_problems(root)), ["default"])

def test_neither_a_module_nor_a_config_is_clean():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		xtest.equal(_problems(root), [])

def test_paths_omitted_selects_every_linted_file():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, _names_rule())
		found = _problems(root)
		xtest.equal(sorted(path.name for path, _, _ in found), ["code.py", "xlint_rules.py"])

def test_paths_select_by_glob():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		(root / "a").mkdir()
		(root / "a" / "one.py").write_text("x = 1\n", encoding = "utf-8")
		(root / "b").mkdir()
		(root / "b" / "two.py").write_text("x = 2\n", encoding = "utf-8")
		_module(root, _names_rule(["a/**"]))
		xtest.equal(_messages(_problems(root)), ["one.py"])

def test_a_path_globstar_matches_zero_segments():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		(root / "a" / "b").mkdir(parents = True)
		(root / "a" / "b" / "one.py").write_text("x = 1\n", encoding = "utf-8")
		_module(root, _names_rule(["a/**/b/**"]))
		xtest.equal(_messages(_problems(root)), ["one.py"])

def test_a_rule_sees_every_file_at_once():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		(root / "a.py").write_text("secret = 1\n", encoding = "utf-8")
		(root / "b.py").write_text("x = 2\n", encoding = "utf-8")
		_module(root, (
			"def rules():\n"
			"\treturn [{\"name\": \"cross\", \"check\": check}]\n"
			"\n"
			"def check(files):\n"
			"\tmarker = \"se\" + \"cret\"\n"
			"\tseen = sorted(path.name for path, lines in files if any(marker in line for line in lines))\n"
			"\treturn [(path, None, \"sees \" + \",\".join(seen)) for path, lines in files if path.name == \"b.py\"]\n"
		))
		xtest.equal(_messages(_problems(root)), ["sees a.py"])

def test_each_checkout_uses_its_own_module():
	with tempfile.TemporaryDirectory() as folder:
		first = _checkout(folder, "first")
		second = _checkout(folder, "second")
		_module(first, _flag_rule("first"))
		_module(second, _flag_rule("second"))
		rules = xlint._Rules([first, second])
		found = rules.repo_problems(rules.files())
		xtest.equal(sorted((path.parent.name, message) for path, _, message in found),
			[("first", "first"), ("second", "second")])

def test_a_checkout_without_a_module_adds_no_findings():
	with tempfile.TemporaryDirectory() as folder:
		first = _checkout(folder, "first")
		second = _checkout(folder, "second")
		_module(first, _flag_rule("first"))
		rules = xlint._Rules([first, second])
		found = rules.repo_problems(rules.files())
		xtest.true(all(path.parent == first for path, _, _ in found),
			"a finding in the checkout that has no module")
		xtest.equal(_messages(found), ["first"])

def test_a_nested_checkout_keeps_its_own_module():
	with tempfile.TemporaryDirectory() as folder:
		parent = _checkout(folder, "parent")
		nested = _checkout(Path(folder) / "parent", "nested")
		_module(parent, _flag_rule("parent"))
		_module(nested, _flag_rule("nested"))
		rules = xlint._Rules([parent])
		found = rules.repo_problems(rules.files())
		xtest.equal(sorted((str(path.relative_to(parent)), message) for path, _, message in found),
			[("code.py", "parent"), ("nested/code.py", "nested")])

def test_a_worktree_is_a_checkout():
	with tempfile.TemporaryDirectory() as folder:
		root = Path(folder) / "worktree"
		root.mkdir()
		(root / ".git").write_text("gitdir: /somewhere/else\n", encoding = "utf-8")
		(root / "code.py").write_text("x = 1\n", encoding = "utf-8")
		_module(root, _flag_rule("worktree"))
		xtest.equal(_messages(_problems(root)), ["worktree"])

def test_a_path_outside_a_checkout_has_no_repo_rules():
	with tempfile.TemporaryDirectory() as folder:
		root = Path(folder)
		(root / "code.py").write_text("x = 1\n", encoding = "utf-8")
		_module(root, _flag_rule("never"))
		xtest.equal(_problems(root), [])

def test_an_import_error_names_the_module():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, "raise RuntimeError(\"broken at import\")\n")
		message = _error(lambda: _problems(root))
		xtest.contains("xlint_rules.py", message)
		xtest.contains("broken at import", message)

def test_a_missing_rules_function_is_an_error():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, "def check(files):\n\treturn []\n")
		xtest.contains("rules()", _error(lambda: _problems(root)))

def test_rules_must_return_a_list():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, (
			"def rules():\n"
			"\treturn {\"name\": \"one\", \"check\": check}\n"
			"\n"
			"def check(files):\n"
			"\treturn []\n"
		))
		xtest.contains("expected a list", _error(lambda: _problems(root)))

def test_a_rule_mapping_without_a_check_is_an_error():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, "def rules():\n\treturn [{\"name\": \"one\"}]\n")
		xtest.contains("check", _error(lambda: _problems(root)))

def test_a_rule_mapping_without_a_name_is_an_error():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, (
			"def rules():\n"
			"\treturn [{\"check\": check}]\n"
			"\n"
			"def check(files):\n"
			"\treturn []\n"
		))
		xtest.contains("no name", _error(lambda: _problems(root)))

def test_a_rules_exception_is_an_error():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, "def rules():\n\traise ValueError(\"no list\")\n")
		message = _error(lambda: _problems(root))
		xtest.contains("`rules()` raised", message)
		xtest.contains("ValueError: no list", message)

def test_paths_must_be_a_list_of_strings():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, (
			"def rules():\n"
			"\treturn [{\"name\": \"one\", \"paths\": \"code.py\", \"check\": check}]\n"
			"\n"
			"def check(files):\n"
			"\treturn []\n"
		))
		xtest.contains("`paths`", _error(lambda: _problems(root)))

def test_duplicate_rule_names_are_an_error():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, (
			"def rules():\n"
			"\treturn [{\"name\": \"same\", \"check\": check}, {\"name\": \"same\", \"check\": check}]\n"
			"\n"
			"def check(files):\n"
			"\treturn []\n"
		))
		xtest.contains("duplicate rule name 'same'", _error(lambda: _problems(root)))

def test_a_rule_exception_names_the_rule():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, (
			"def rules():\n"
			"\treturn [{\"name\": \"boom\", \"check\": check}]\n"
			"\n"
			"def check(files):\n"
			"\traise ValueError(\"exploding\")\n"
		))
		message = _error(lambda: _problems(root))
		xtest.contains("rule 'boom'", message)
		xtest.contains("ValueError: exploding", message)

def test_a_rule_that_exits_is_an_error():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, (
			"import sys\n"
			"\n"
			"def rules():\n"
			"\treturn [{\"name\": \"exit\", \"check\": check}]\n"
			"\n"
			"def check(files):\n"
			"\tsys.exit(0)\n"
		))
		message = _error(lambda: _problems(root))
		xtest.contains("rule 'exit'", message)
		xtest.contains("SystemExit", message)

def test_a_malformed_finding_is_an_error():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, (
			"def rules():\n"
			"\treturn [{\"name\": \"bad\", \"check\": check}]\n"
			"\n"
			"def check(files):\n"
			"\treturn [(path, 0, \"line zero\") for path, lines in files]\n"
		))
		message = _error(lambda: _problems(root))
		xtest.contains("rule 'bad'", message)
		xtest.contains("line", message)

def test_a_file_level_finding_has_no_line():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, _names_rule(["code.py"]))
		found = _problems(root)
		xtest.equal(len(found), 1)
		xtest.equal(found[0][1], None)

def test_the_one_shot_report_prints_a_file_level_finding():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, _names_rule(["code.py"]))
		result = subprocess.run([sys.executable, str(XLINT), str(root)],
			capture_output = True, text = True)
		xtest.equal(result.returncode, 1)
		xtest.contains("code.py: code.py", result.stdout)
		xtest.contains("1 problem(s)", result.stdout)

def test_a_broken_module_exits_one_and_never_says_clean():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, "raise RuntimeError(\"broken at import\")\n")
		result = subprocess.run([sys.executable, str(XLINT), str(root)],
			capture_output = True, text = True)
		xtest.equal(result.returncode, 1)
		xtest.contains("broken at import", result.stderr)
		xtest.true("clean" not in result.stdout, "a failed rule set must not report clean")

def test_no_repo_rules_skips_a_broken_module():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, "raise RuntimeError(\"broken at import\")\n")
		result = subprocess.run([sys.executable, str(XLINT), "--no-repo-rules", str(root)],
			capture_output = True, text = True)
		xtest.equal(result.returncode, 0)
		xtest.contains("clean", result.stdout)

def test_the_config_path_must_stay_inside_the_checkout():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		(root / ".xlint.toml").write_text('[rules]\npath = "/tmp/elsewhere.py"\n', encoding = "utf-8")
		xtest.contains("inside the checkout", _error(lambda: _problems(root)))

def test_a_config_path_may_not_escape_with_dot_dot():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		(root / ".xlint.toml").write_text('[rules]\npath = "../outside.py"\n', encoding = "utf-8")
		xtest.contains("inside the checkout", _error(lambda: _problems(root)))

def test_the_config_path_must_exist():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		(root / ".xlint.toml").write_text('[rules]\npath = "lint/missing.py"\n', encoding = "utf-8")
		xtest.contains("does not exist", _error(lambda: _problems(root)))

def test_the_config_path_must_be_a_file():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		(root / "lint" / "policy.py").mkdir(parents = True)
		(root / ".xlint.toml").write_text('[rules]\npath = "lint/policy.py"\n', encoding = "utf-8")
		xtest.contains("not a file", _error(lambda: _problems(root)))

def test_the_config_table_needs_a_path():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		(root / ".xlint.toml").write_text('[rules]\nother = "x"\n', encoding = "utf-8")
		xtest.contains("path", _error(lambda: _problems(root)))

def test_a_broken_config_is_an_error():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		(root / ".xlint.toml").write_text('[rules\npath = "x"\n', encoding = "utf-8")
		xtest.contains(".xlint.toml", _error(lambda: _problems(root)))

def test_watch_dirs_include_the_module_and_config():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, _flag_rule("flagged"))
		rules = xlint._Rules([root])
		xtest.true((root / "tools") in rules.watch_dirs(), "the default module's directory is watched")
		xtest.true(root in rules.watch_dirs(), "the config's directory is watched")

def test_watch_reloads_an_edited_module():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, _flag_rule("first"))
		proc, lines = _start_watch(root)
		try:
			xtest.true(_wait_for(lines, "code.py:1: first"), "the first report names the first rule")
			_module(root, _flag_rule("second"))
			xtest.true(_wait_for(lines, "code.py:1: second"), "the edited module is reloaded")
		finally:
			_stop_watch(proc)

def test_watch_retries_a_broken_module():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, "raise RuntimeError(\"broken at import\")\n")
		proc, lines = _start_watch(root)
		try:
			xtest.true(_wait_for(lines, "broken at import"), "the error is in the report")
			_module(root, _flag_rule("fixed"))
			xtest.true(_wait_for(lines, "code.py:1: fixed"), "the module is retried after it changes")
		finally:
			_stop_watch(proc)

def test_watch_reloads_a_changed_config():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, _flag_rule("one"), "lint/one.py")
		_module(root, _flag_rule("two"), "lint/two.py")
		(root / ".xlint.toml").write_text('[rules]\npath = "lint/one.py"\n', encoding = "utf-8")
		proc, lines = _start_watch(root)
		try:
			xtest.true(_wait_for(lines, "code.py:1: one"), "the configured module is loaded")
			(root / ".xlint.toml").write_text('[rules]\npath = "lint/two.py"\n', encoding = "utf-8")
			xtest.true(_wait_for(lines, "code.py:1: two"), "the changed config selects the new module")
		finally:
			_stop_watch(proc)

def test_watch_reloads_a_changed_config_target():
	with tempfile.TemporaryDirectory() as folder:
		root = _checkout(folder)
		_module(root, _flag_rule("one"), "lint/policy.py")
		(root / ".xlint.toml").write_text('[rules]\npath = "lint/policy.py"\n', encoding = "utf-8")
		proc, lines = _start_watch(root)
		try:
			xtest.true(_wait_for(lines, "code.py:1: one"), "the configured module is loaded")
			_module(root, _flag_rule("two"), "lint/policy.py")
			xtest.true(_wait_for(lines, "code.py:1: two"), "the configured module is reloaded")
		finally:
			_stop_watch(proc)

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
