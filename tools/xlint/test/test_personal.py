#!/usr/bin/env python3
"""
Tests for the personal-identifier check — the rule in `doc/personal-data.md`.

Run with: python3 dev/xtest/xtest.py tools/xlint/test/test_personal.py

The check exists because this repository is public and a record of it quoted
the owner's real name, the private workspace slug and the private repo names.
A check that reports too much is a check nobody runs, and one that reports too
little is the leak it exists to prevent — so both directions are pinned here.

**The tokens in these tests are invented.** The real ones live outside the
repository, in `~/.config/xlib/personal-details.txt`, and a test that carried
them would be the leak the check prevents.
"""

import os,subprocess,sys,tempfile,unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
sys.path.insert(0, str(REPO))

from tools.xlint import _personal

XLINT = REPO / "tools" / "xlint" / "xlint.py"
CHECK = REPO / "tools" / "check-personal.py"

TOKEN = "a-private-project"
WORKSPACE = "a-private-workspace"

def _token_file(folder, tokens=(TOKEN, WORKSPACE)):
	"""A token list outside the repository, holding the given tokens."""
	path = Path(folder) / "personal-details.txt"
	path.write_text("\n".join(tokens) + "\n", encoding="utf-8")
	return path

def _env(tokens_path):
	"""The environment that points the loader at a given token list."""
	env = dict(os.environ)
	env["XPERSONAL_DETAILS"] = str(tokens_path)
	return env

def _git_repo(folder, name = "repo"):
	"""A real checkout with one committed file, so `git ls-files` has something to say."""
	root = Path(folder) / name
	root.mkdir(parents=True)
	subprocess.run(["git", "init", "-q"], cwd=root, check=True)
	(root / "notes.md").write_text("a clean line\n", encoding="utf-8")
	subprocess.run(["git", "add", "notes.md"], cwd=root, check=True)
	subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
		"commit", "-qm", "t"], cwd=root, check=True)
	return root

class TestTheTokenList(unittest.TestCase):
	"""The list is read from outside the repository, and only the values are kept."""

	def test_a_missing_list_is_not_an_error(self):
		with tempfile.TemporaryDirectory() as folder:
			self.assertEqual(_personal.load_tokens(Path(folder) / "absent.txt"), [])

	def test_comments_and_blank_lines_are_not_tokens(self):
		with tempfile.TemporaryDirectory() as folder:
			path = Path(folder) / "list.txt"
			path.write_text("# a comment\n\n  a-token  \n\n#another\nb-token\n", encoding="utf-8")
			self.assertEqual(_personal.load_tokens(path), ["a-token", "b-token"])

	def test_the_environment_variable_points_the_list_elsewhere(self):
		with tempfile.TemporaryDirectory() as folder:
			path = _token_file(folder)
			os.environ["XPERSONAL_DETAILS"] = str(path)
			try:
				self.assertEqual(_personal.load_tokens(), [TOKEN, WORKSPACE])
			finally:
				del os.environ["XPERSONAL_DETAILS"]

class TestTheMatch(unittest.TestCase):
	"""A token is a whole word: the name of a project is not found inside a longer name."""

	def test_a_token_is_found(self):
		self.assertEqual(_personal.find(["the project is %s" % TOKEN], [TOKEN]), [(1, TOKEN)])

	def test_the_case_does_not_matter(self):
		self.assertEqual(_personal.find(["the project is %s" % TOKEN.upper()], [TOKEN]), [(1, TOKEN)])

	def test_a_token_inside_a_longer_name_is_not_found(self):
		# a short token must not fire inside a longer name that begins with it,
		# or every mention of the longer name is reported twice and the report
		# stops being read.
		self.assertEqual(_personal.find(["the a-private-project project"], ["a-private"]), [])

	def test_a_longer_token_is_found(self):
		self.assertEqual(_personal.find(["the a-private-project project"], ["a-private-project"]), [(1, "a-private-project")])

	def test_a_token_inside_a_word_is_not_found(self):
		self.assertEqual(_personal.find(["un-a-privatesomething"], ["a-private"]), [])

	def test_a_multi_word_token_is_found(self):
		self.assertEqual(_personal.find(["the Private Name project"], ["Private Name"]),
			[(1, "Private Name")])

	def test_the_line_number_is_reported(self):
		self.assertEqual(_personal.find(["clean", "clean", TOKEN], [TOKEN]), [(3, TOKEN)])

class TestTheCheck(unittest.TestCase):
	"""The check reports a tracked file's identifiers, and leaves the rest alone."""

	def test_a_file_with_an_identifier_is_reported(self):
		with tempfile.TemporaryDirectory() as folder:
			path = _token_file(folder)
			os.environ["XPERSONAL_DETAILS"] = str(path)
			try:
				problems = _personal.check(["the %s project" % TOKEN])
				self.assertEqual(len(problems), 1)
				self.assertIn("personal identifier", problems[0][1])
			finally:
				del os.environ["XPERSONAL_DETAILS"]

	def test_a_clean_file_is_clean(self):
		with tempfile.TemporaryDirectory() as folder:
			path = _token_file(folder)
			os.environ["XPERSONAL_DETAILS"] = str(path)
			try:
				self.assertEqual(_personal.check(["a clean line"]), [])
			finally:
				del os.environ["XPERSONAL_DETAILS"]

	def test_a_machine_without_a_list_has_no_findings(self):
		os.environ["XPERSONAL_DETAILS"] = "/nonexistent/personal-details.txt"
		try:
			self.assertEqual(_personal.check(["the %s project" % TOKEN]), [])
		finally:
			del os.environ["XPERSONAL_DETAILS"]

class TestTheLinter(unittest.TestCase):
	"""The check is wired into xlint, so the pre-commit hook refuses the commit."""

	def _run(self, root, *args):
		return subprocess.run([sys.executable, str(XLINT), *args], cwd=root,
			capture_output=True, text=True, env=_env(self.tokens))

	def setUp(self):
		self.folder = tempfile.TemporaryDirectory()
		self.tokens = _token_file(self.folder.name)
		self.root = _git_repo(self.folder.name)

	def tearDown(self):
		self.folder.cleanup()

	def test_a_tracked_file_with_an_identifier_fails(self):
		(self.root / "notes.md").write_text("the %s project\n" % TOKEN, encoding="utf-8")
		subprocess.run(["git", "add", "notes.md"], cwd=self.root, check=True)
		result = self._run(self.root, "notes.md")
		self.assertEqual(result.returncode, 1)
		self.assertIn("personal identifier", result.stdout)

	def test_the_flag_turns_the_check_off(self):
		(self.root / "notes.md").write_text("the %s project\n" % TOKEN, encoding="utf-8")
		subprocess.run(["git", "add", "notes.md"], cwd=self.root, check=True)
		result = self._run(self.root, "--no-personal", "notes.md")
		self.assertEqual(result.returncode, 0)

	def test_an_untracked_file_is_not_checked(self):
		# A draft is allowed to carry a value while it is being written: it is
		# not published, and the check is about what the repository publishes.
		(self.root / "draft.md").write_text("the %s project\n" % TOKEN, encoding="utf-8")
		result = self._run(self.root, "draft.md")
		self.assertEqual(result.returncode, 0)

class TestTheScript(unittest.TestCase):
	"""The board gate: the text is checked before it is written."""

	def _run(self, text):
		return subprocess.run([sys.executable, str(CHECK), "--text"], input=text,
			capture_output=True, text=True, env=_env(self.tokens))

	def setUp(self):
		self.folder = tempfile.TemporaryDirectory()
		self.tokens = _token_file(self.folder.name)

	def tearDown(self):
		self.folder.cleanup()

	def test_text_with_an_identifier_fails(self):
		result = self._run("the %s project\n" % TOKEN)
		self.assertEqual(result.returncode, 1)
		self.assertIn(TOKEN, result.stdout)

	def test_clean_text_passes(self):
		result = self._run("a line about the tools\n")
		self.assertEqual(result.returncode, 0)

if __name__ == "__main__":
	unittest.main()
