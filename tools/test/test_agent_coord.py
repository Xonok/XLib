"""Tests for tools/agent-coord.py.

The tool is one file whose name is not a module name, so it is loaded by path.
Its state lives in the `.agents` folder of the workspace, and every test here
points that at a temporary folder: the live one belongs to the machine, and a
test that wrote to it would take the claims of every agent on it with it.
"""
import argparse,contextlib,importlib.util,io,json,os,subprocess,tempfile,unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "agent-coord.py"

def load_tool():
	"""The agent-coord module, loaded from its path."""
	spec = importlib.util.spec_from_file_location("agent_coord", TOOL)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module

def news_args(status=False, peek=False):
	return argparse.Namespace(status=status, peek=peek)

class CoordTestCase(unittest.TestCase):
	"""A tool whose state lives in a temporary workspace."""

	def setUp(self):
		self.tool = load_tool()
		self.folder = tempfile.TemporaryDirectory()
		self.addCleanup(self.folder.cleanup)
		self.ws = Path(self.folder.name) / "ws"
		agents = self.ws / ".agents"
		agents.mkdir(parents=True)
		self.tool.DIR = str(agents)
		self.tool.LOCK = str(agents / "lock")
		self.tool.IDS = str(agents / "ids.json")
		self.tool.CLAIMS = str(agents / "claims.json")
		self.tool.RULE_CURSOR = str(agents / "rule-cursor.json")
		self.tool.workspace_root = lambda: str(self.ws)
		self.tool.agent_role = lambda: "secretary"
		# The session key is the client's pid, and a pid that is alive is one the
		# recycling pass keeps. The identity itself is left to the real code, so
		# the migration runs the way it runs in a session.
		self.tool.session_key = lambda: "pid-%d" % os.getpid()
		self.other_key = "pid-%d" % os.getppid()
		self.other_id = "ws/secretary-2"

	def write_json(self, name, data):
		path = self.ws / ".agents" / name
		path.write_text(json.dumps(data), encoding="utf-8")
		return path

	def read_json(self, name):
		path = self.ws / ".agents" / name
		if not path.exists():
			return {}
		return json.loads(path.read_text(encoding="utf-8"))

	def run_news(self, *args):
		out = io.StringIO()
		with contextlib.redirect_stdout(out):
			self.tool.cmd_news(news_args(*args))
		return out.getvalue()

class TestNewsKeepsClaims(CoordTestCase):
	"""`news` is what every agent runs at session start, and it used to take the
	claims of the whole machine with it."""

	def test_the_claims_of_another_agent_survive_a_news_run(self):
		self.write_json("ids.json", {self.other_key: self.other_id})
		self.write_json("claims.json", {self.other_id: ["/tmp/other.py"]})
		(self.ws / "AGENTS.md").write_text("rules\n", encoding="utf-8")
		self.run_news()
		self.assertEqual(self.read_json("claims.json"), {self.other_id: ["/tmp/other.py"]})

	def test_the_rule_cursor_of_another_agent_survives_a_news_run(self):
		self.write_json("ids.json", {self.other_key: self.other_id})
		self.write_json("rule-cursor.json", {self.other_id: {"/tmp/AGENTS.md": "abc"}})
		(self.ws / "AGENTS.md").write_text("rules\n", encoding="utf-8")
		self.run_news()
		self.assertIn(self.other_id, self.read_json("rule-cursor.json"))

	def test_a_claim_owned_by_a_dropped_slot_id_is_still_dropped(self):
		# The migration exists to clear out the old slot-based ids, and the claims
		# that went with them. That part still has to happen.
		self.write_json("ids.json", {"pid-999": "ws/a1", self.other_key: self.other_id})
		self.write_json("claims.json", {"ws/a1": ["/tmp/old.py"], self.other_id: ["/tmp/other.py"]})
		self.write_json("rule-cursor.json", {"ws/a1": {"/tmp/AGENTS.md": "abc"}, self.other_id: {"/tmp/AGENTS.md": "def"}})
		self.tool.migrate_ids()
		self.assertEqual(self.read_json("claims.json"), {self.other_id: ["/tmp/other.py"]})
		self.assertEqual(self.read_json("rule-cursor.json"), {self.other_id: {"/tmp/AGENTS.md": "def"}})

class TestNewsFindsTheRules(CoordTestCase):
	"""A run that checks nothing must not read like a run that found no changes."""

	def test_the_style_rules_of_the_workspace_are_checked(self):
		(self.ws / "doc" / "style").mkdir(parents=True)
		(self.ws / "doc" / "style" / "python.md").write_text("rules\n", encoding="utf-8")
		(self.ws / "AGENTS.md").write_text("rules\n", encoding="utf-8")
		out = self.run_news()
		self.assertIn("AGENTS.md", out)
		self.assertIn("python.md", out)

	def test_a_change_is_reported_once_and_then_remembered(self):
		(self.ws / "AGENTS.md").write_text("rules\n", encoding="utf-8")
		first = self.run_news()
		self.assertIn("new guideline changes", first)
		second = self.run_news()
		self.assertIn("no new guideline changes", second)

	def test_a_workspace_without_rule_files_says_it_checked_nothing(self):
		out = self.run_news()
		self.assertIn("nothing checked", out)
		self.assertNotIn("no new guideline changes", out)

	def test_peek_does_not_mark_the_rules_seen(self):
		(self.ws / "AGENTS.md").write_text("rules\n", encoding="utf-8")
		self.run_news(False, True)
		self.assertEqual(self.read_json("rule-cursor.json"), {})

class TestRuleFiles(CoordTestCase):

	def test_the_style_rules_are_found_where_the_pointer_table_names_them(self):
		(self.ws / "doc" / "style").mkdir(parents=True)
		(self.ws / "doc" / "style" / "markdown.md").write_text("rules\n", encoding="utf-8")
		found = self.tool.rule_files(str(self.ws))
		self.assertIn(str(self.ws / "doc" / "style" / "markdown.md"), found)

	def test_the_agent_definitions_are_still_rule_files(self):
		(self.ws / ".opencode" / "agent").mkdir(parents=True)
		(self.ws / ".opencode" / "agent" / "secretary.md").write_text("agent\n", encoding="utf-8")
		found = self.tool.rule_files(str(self.ws))
		self.assertIn(str(self.ws / ".opencode" / "agent" / "secretary.md"), found)

class TestSessionIdentity(CoordTestCase):
	"""The opencode 2 service is one process for the whole machine, and asking it
	instead of the client put every session in the same place."""

	def test_the_client_is_preferred_over_the_shared_service(self):
		entries = [
			(200, "opencode", ["opencode", "serve", "--service"]),
			(100, "opencode", ["opencode", "--session", "ses_abc", "--log-level", "warn"]),
		]
		self.assertEqual(self.tool.pick_opencode_pid(entries), 100)

	def test_the_service_is_the_answer_when_there_is_no_client(self):
		entries = [(200, "opencode", ["opencode", "serve", "--service"])]
		self.assertEqual(self.tool.pick_opencode_pid(entries), 200)

	def test_a_process_that_is_not_opencode_is_skipped(self):
		entries = [
			(300, "bash", ["/bin/bash", "-c", "python3 tools/agent-coord.py"]),
			(100, "opencode", ["opencode", "--session", "ses_abc"]),
		]
		self.assertEqual(self.tool.pick_opencode_pid(entries), 100)

	def test_no_opencode_process_at_all_is_no_answer(self):
		self.assertIsNone(self.tool.pick_opencode_pid([(300, "bash", ["/bin/bash"])]))

class TestNearestGit(CoordTestCase):
	"""A worktree's `.git` is a file, and a lookup that recognises only a
	directory walks past it to the repository that contains it."""

	def test_a_worktree_root_is_a_checkout_of_its_own(self):
		outer = Path(self.folder.name) / "outer"
		work = outer / ".work" / "ticket"
		work.mkdir(parents=True)
		(outer / ".git").mkdir()
		(work / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
		self.assertEqual(self.tool.nearest_git(str(work / "code.py")), str(work))

	def test_a_plain_checkout_is_still_found(self):
		outer = Path(self.folder.name) / "outer"
		(outer / ".git").mkdir(parents=True)
		self.assertEqual(self.tool.nearest_git(str(outer / "code.py")), str(outer))

	def test_a_path_outside_any_checkout_has_no_repository(self):
		loose = Path(self.folder.name) / "loose"
		loose.mkdir()
		self.assertIsNone(self.tool.nearest_git(str(loose / "code.py")))

class TestCheckClean(CoordTestCase):
	"""`check-clean` is the guard that stops an agent editing a file another
	agent has edited, and in a worktree it reported clean for a dirty file."""

	def _repo(self):
		repo = Path(self.folder.name) / "repo"
		repo.mkdir()
		self._git(repo, "init", "-q")
		self._git(repo, "config", "user.email", "t@example.com")
		self._git(repo, "config", "user.name", "T")
		(repo / ".gitignore").write_text(".work/\n", encoding="utf-8")
		(repo / "code.py").write_text("x = 1\n", encoding="utf-8")
		self._git(repo, "add", ".gitignore", "code.py")
		self._git(repo, "commit", "-qm", "first")
		return repo

	def _git(self, repo, *args):
		result = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True)
		if result.returncode != 0:
			raise AssertionError("git %s failed: %s" % (" ".join(args), result.stderr))
		return result.stdout

	def test_a_dirty_file_in_a_worktree_is_reported_dirty(self):
		repo = self._repo()
		work = repo / ".work" / "wt"
		self._git(repo, "worktree", "add", "-q", str(work), "-b", "side")
		(work / "code.py").write_text("x = 2\n", encoding="utf-8")
		out = io.StringIO()
		with contextlib.redirect_stdout(out):
			with self.assertRaises(SystemExit) as raised:
				self.tool.cmd_check_clean(argparse.Namespace(paths=[str(work / "code.py")], repo=None))
		self.assertEqual(raised.exception.code, 1)
		self.assertIn("dirty", out.getvalue())

	def test_a_clean_file_in_a_worktree_is_reported_clean(self):
		repo = self._repo()
		work = repo / ".work" / "wt"
		self._git(repo, "worktree", "add", "-q", str(work), "-b", "side")
		out = io.StringIO()
		with contextlib.redirect_stdout(out):
			self.tool.cmd_check_clean(argparse.Namespace(paths=[str(work / "code.py")], repo=None))
		self.assertIn("clean", out.getvalue())

	def test_a_file_in_each_of_two_checkouts_is_checked_against_its_own(self):
		repo = self._repo()
		work = repo / ".work" / "wt"
		self._git(repo, "worktree", "add", "-q", str(work), "-b", "side")
		(repo / "code.py").write_text("x = 9\n", encoding="utf-8")
		(work / "code.py").write_text("x = 2\n", encoding="utf-8")
		out = io.StringIO()
		with contextlib.redirect_stdout(out):
			with self.assertRaises(SystemExit) as raised:
				self.tool.cmd_check_clean(argparse.Namespace(paths=[str(repo / "code.py"), str(work / "code.py")], repo=None))
		self.assertEqual(raised.exception.code, 1)
		self.assertIn(str(repo / "code.py"), out.getvalue())
		self.assertIn(str(work / "code.py"), out.getvalue())

	def test_a_file_behind_a_symlink_is_reported_dirty(self):
		repo = self._repo()
		(repo / "real.py").write_text("x = 1\n", encoding="utf-8")
		self._git(repo, "add", "real.py")
		self._git(repo, "commit", "-qm", "second")
		(repo / "link.py").symlink_to(repo / "real.py")
		self._git(repo, "add", "link.py")
		self._git(repo, "commit", "-qm", "third")
		(repo / "real.py").write_text("x = 3\n", encoding="utf-8")
		out = io.StringIO()
		with contextlib.redirect_stdout(out):
			with self.assertRaises(SystemExit) as raised:
				self.tool.cmd_check_clean(argparse.Namespace(paths=[str(repo / "link.py")], repo=None))
		self.assertEqual(raised.exception.code, 1)
		self.assertIn("dirty", out.getvalue())

	def test_a_clean_file_is_reported_clean(self):
		repo = self._repo()
		out = io.StringIO()
		with contextlib.redirect_stdout(out):
			self.tool.cmd_check_clean(argparse.Namespace(paths=[str(repo / "code.py")], repo=None))
		self.assertIn("clean", out.getvalue())

if __name__ == "__main__":
	unittest.main()
