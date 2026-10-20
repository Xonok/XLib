"""Tests for `xlint --watch`: the rules are part of what is watched.

`--watch` read `.xlintignore` once, at startup, and kept the result for the life
of the process, so a rule edited while the watch ran changed nothing until the
tool was restarted — and restarting is the workaround, which costs the thing
watch mode exists for.

These tests cover the reload: a rule edited, added or removed is noticed; the
scope moves with it, so a newly ignored file leaves the report and a newly
un-ignored one enters it; and the directories watched are rebuilt to match, in
both directions.

The last tests drive the real process, because the loop that turns a changed
rule into a changed report is the thing under test.
"""
import os,subprocess,sys,tempfile,threading,time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
sys.path.insert(0, str(REPO))

import xtest
from tools.xlint import xlint

XLINT = REPO / "tools" / "xlint" / "xlint.py"

def _repo(folder, name = "repo"):
	"""A checkout holding one file, and a problem in that file to report."""
	root = Path(folder) / name
	root.mkdir(parents=True)
	(root / ".git").mkdir()
	(root / "code.py").write_text("x = 1 \n", encoding="utf-8")
	return root

def _names(paths):
	"""The names of the paths, so a test asserts on what was found and not on where."""
	return sorted(path.name for path in paths)

def _start_watch(root):
	"""Watch `root` in a real process, and collect what it prints."""
	proc = subprocess.Popen([sys.executable, str(XLINT), "--watch", str(root)],
		stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
	lines = []
	def reader():
		for line in proc.stdout:
			lines.append(line)
	threading.Thread(target=reader, daemon=True).start()
	return proc, lines

def _stop_watch(proc):
	"""End the watch, and give it a moment to go."""
	proc.terminate()
	try:
		proc.wait(timeout=5)
	except subprocess.TimeoutExpired:
		proc.kill()
		proc.wait(timeout=5)
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

def _draws(lines):
	"""How many times the report has been drawn."""
	return sum(1 for line in lines if "=== xlint ===" in line)

def test_the_rules_are_reloaded_when_the_ignore_file_is_edited():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		(root / ".xlintignore").write_text("code.py\n", encoding="utf-8")
		rules = xlint._IgnoreRules([root])
		xtest.equal(_names(rules.files()), [], "the rule already excludes the file")
		(root / ".xlintignore").write_text("other.py\n", encoding="utf-8")
		xtest.true(rules.refresh(), "the edit is noticed")
		xtest.equal(_names(rules.files()), ["code.py"], "the new rule applies")

def test_the_rules_are_reloaded_when_the_ignore_file_appears():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		rules = xlint._IgnoreRules([root])
		xtest.equal(_names(rules.files()), ["code.py"], "the file starts in scope")
		(root / ".xlintignore").write_text("code.py\n", encoding="utf-8")
		xtest.true(rules.refresh(), "the new file is noticed")
		xtest.equal(_names(rules.files()), [], "the new rule applies")

def test_the_rules_are_reloaded_when_the_ignore_file_vanishes():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		(root / ".xlintignore").write_text("code.py\n", encoding="utf-8")
		rules = xlint._IgnoreRules([root])
		xtest.equal(_names(rules.files()), [], "the file starts out of scope")
		(root / ".xlintignore").unlink()
		xtest.true(rules.refresh(), "the removal is noticed")
		xtest.equal(_names(rules.files()), ["code.py"], "the file is back")

def test_a_pass_that_finds_no_change_reloads_nothing():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		(root / ".xlintignore").write_text("code.py\n", encoding="utf-8")
		rules = xlint._IgnoreRules([root])
		xtest.equal(rules.refresh(), False, "nothing changed, so nothing was reloaded")

def test_a_newly_ignored_file_leaves_the_scope():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		rules = xlint._IgnoreRules([root])
		xtest.equal(_names(rules.files()), ["code.py"], "the file starts in scope")
		(root / ".xlintignore").write_text("code.py\n", encoding="utf-8")
		rules.refresh()
		xtest.equal(_names(rules.files()), [], "the file left the scope")

def test_a_newly_unignored_file_enters_the_scope():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		(root / ".xlintignore").write_text("code.py\n", encoding="utf-8")
		rules = xlint._IgnoreRules([root])
		xtest.equal(_names(rules.files()), [], "the file starts out of scope")
		(root / ".xlintignore").write_text("other.py\n", encoding="utf-8")
		rules.refresh()
		xtest.equal(_names(rules.files()), ["code.py"], "the file entered the scope")

def test_the_watch_set_drops_a_directory_the_new_rules_exclude():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		(root / "sub").mkdir()
		rules = xlint._IgnoreRules([root])
		xtest.true(root / "sub" in rules.watch_dirs(), "the directory is watched")
		(root / ".xlintignore").write_text("sub/\n", encoding="utf-8")
		rules.refresh()
		xtest.true(root / "sub" not in rules.watch_dirs(), "the directory stopped being watched")

def test_the_watch_set_gains_a_directory_the_new_rules_allow():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		(root / "sub").mkdir()
		(root / ".xlintignore").write_text("sub/\n", encoding="utf-8")
		rules = xlint._IgnoreRules([root])
		xtest.true(root / "sub" not in rules.watch_dirs(), "the directory is not watched")
		(root / ".xlintignore").write_text("other.py\n", encoding="utf-8")
		rules.refresh()
		xtest.true(root / "sub" in rules.watch_dirs(), "the directory is watched now")

def test_two_repositories_are_governed_by_their_own_chains():
	with tempfile.TemporaryDirectory() as folder:
		one = _repo(folder, "one")
		two = _repo(folder, "two")
		(one / ".xlintignore").write_text("hidden.py\n", encoding="utf-8")
		(two / ".xlintignore").write_text("hidden.py\n", encoding="utf-8")
		(one / "hidden.py").write_text("x = 1 \n", encoding="utf-8")
		(two / "hidden.py").write_text("x = 1 \n", encoding="utf-8")
		rules = xlint._IgnoreRules([one, two])
		found = sorted(path.parent.name + "/" + path.name for path in rules.files())
		xtest.equal(found, ["one/code.py", "two/code.py"],
			"each repository keeps its own file and hides its own hidden one")

def test_a_run_over_two_repositories_honours_the_chain_of_each():
	with tempfile.TemporaryDirectory() as folder:
		one = _repo(folder, "one")
		two = _repo(folder, "two")
		(one / ".xlintignore").write_text("hidden.py\n", encoding="utf-8")
		(two / ".xlintignore").write_text("hidden.py\n", encoding="utf-8")
		(one / "hidden.py").write_text("x = 1 \n", encoding="utf-8")
		(two / "hidden.py").write_text("x = 1 \n", encoding="utf-8")
		result = subprocess.run([sys.executable, str(XLINT), str(one), str(two)],
			capture_output=True, text=True, timeout=60)
		xtest.true("one/code.py" in result.stdout, "the first repository is linted")
		xtest.true("two/code.py" in result.stdout, "the second repository is linted")
		xtest.true("one/hidden.py" not in result.stdout, "the first repository's rule is honoured")
		xtest.true("two/hidden.py" not in result.stdout, "the second repository's rule is honoured")

def test_the_watch_reports_a_file_the_new_rules_allow():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		(root / ".xlintignore").write_text("code.py\n", encoding="utf-8")
		proc, lines = _start_watch(root)
		try:
			xtest.true(_wait_for(lines, "clean"), "the first report is drawn")
			(root / ".xlintignore").write_text("other.py\n", encoding="utf-8")
			xtest.true(_wait_for(lines, "code.py"), "the newly allowed file is reported")
		finally:
			_stop_watch(proc)

def test_the_watch_drops_a_file_the_new_rules_exclude():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		proc, lines = _start_watch(root)
		try:
			xtest.true(_wait_for(lines, "code.py"), "the file is reported to begin with")
			(root / ".xlintignore").write_text("code.py\n", encoding="utf-8")
			xtest.true(_wait_for(lines, "clean"), "the file left the report")
		finally:
			_stop_watch(proc)

def test_the_reload_prints_nothing_of_its_own():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		(root / ".xlintignore").write_text("code.py\n", encoding="utf-8")
		proc, lines = _start_watch(root)
		try:
			xtest.true(_wait_for(lines, "clean"), "the first report is drawn")
			(root / ".xlintignore").write_text("other.py\n", encoding="utf-8")
			xtest.true(_wait_for(lines, "code.py"), "the report is drawn again")
			time.sleep(0.5)
			xtest.equal(_draws(lines), 2, "the reload drew the report and printed nothing else")
		finally:
			_stop_watch(proc)

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
