"""The launcher takes the window's name from agent-coord, and the session uses it.

A window is named before its opencode client exists, so `allocate` keys the id
by the launcher's pid instead of the client's, and the launcher exports the
result: the id every tool in the session reports, and the window name the
title is made of.

The other half is which client a session belongs to. Under opencode 2 every
tool shell descends from the shared service, and the service's parent is
whichever client started it; asking the ancestry first gave every session on
the machine that one client's identity.
"""
import argparse,contextlib,importlib.util,io,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path

# xtest, found relative to this file rather than to the working directory: a
# path relative to the cwd only works from the repository root, and a test
# that runs from one directory and fails from another is worse than one that
# never runs.
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
import xtest

TOOL = REPO / "tools" / "agent-coord.py"
LAUNCHER = REPO / "tools" / "oc-agent"

def load_tool():
	spec = importlib.util.spec_from_file_location("agent_coord", TOOL)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module

class Fixture:
	"""A tool whose state lives in a temporary workspace."""

	def __init__(self):
		self.folder = tempfile.TemporaryDirectory()
		self.ws = Path(self.folder.name) / "ws"
		agents = self.ws / ".agents"
		agents.mkdir(parents=True)
		self.tool = load_tool()
		self.tool.DIR = str(agents)
		self.tool.LOCK = str(agents / "lock")
		self.tool.IDS = str(agents / "ids.json")
		self.tool.CLAIMS = str(agents / "claims.json")
		self.tool.RULE_CURSOR = str(agents / "rule-cursor.json")
		self.tool.workspace_root = lambda: str(self.ws)
		self.tool.launch_workspace = lambda: str(self.ws)
		self.tool.agent_role = lambda: "secretary"

	def allocate(self, pid, role=None):
		out = io.StringIO()
		with contextlib.redirect_stdout(out):
			self.tool.cmd_allocate(argparse.Namespace(pid=pid, role=role))
		return out.getvalue().strip()

	def free(self, pid):
		self.tool.cmd_free(argparse.Namespace(pid=pid))

	def read_ids(self):
		path = Path(self.tool.IDS)
		if not path.exists():
			return {}
		return json.loads(path.read_text(encoding="utf-8"))

	def close(self):
		self.folder.cleanup()

def _fixture(fn):
	def run():
		f = Fixture()
		try:
			fn(f)
		finally:
			f.close()
	return run

@_fixture
def test_an_allocation_names_the_window_and_stores_it_against_the_launcher(f):
	pid = os.getpid()
	xtest.equal(f.allocate(pid), "ws/secretary-1", "the first window is the bare role")
	key = "pid-%d@%d" % (pid, f.tool.proc_starttime(pid))
	xtest.equal(f.read_ids().get(key), "ws/secretary-1", "the key records the start time")

@_fixture
def test_a_second_launcher_gets_the_next_number(f):
	xtest.equal(f.allocate(os.getpid()), "ws/secretary-1", "the first launcher takes 1")
	xtest.equal(f.allocate(os.getppid()), "ws/secretary-2", "the second does not take the same number")

@_fixture
def test_freeing_returns_the_number(f):
	pid = os.getpid()
	xtest.equal(f.allocate(pid), "ws/secretary-1", "allocated")
	f.free(pid)
	xtest.equal(f.allocate(pid), "ws/secretary-1", "and the number comes back")

@_fixture
def test_the_client_named_by_the_session_wins_over_the_ancestor(f):
	"""The service's parent client is not this session's client."""
	service_parent = (100, ["opencode", "--session", "ses_other"], "/elsewhere")
	this_client = (200, ["opencode", "--session", "ses_this"], "/repo")
	f.tool.opencode_clients = lambda: [service_parent, this_client]
	f.tool.opencode_pid = lambda: 100
	old = os.environ.get("OPENCODE_SESSION_ID")
	os.environ["OPENCODE_SESSION_ID"] = "ses_this"
	try:
		xtest.equal(f.tool.session_client_pid(), 200, "the session's own client is the answer")
	finally:
		if old is None:
			os.environ.pop("OPENCODE_SESSION_ID", None)
		else:
			os.environ["OPENCODE_SESSION_ID"] = old

@_fixture
def test_the_ancestor_still_answers_when_no_client_names_the_session(f):
	f.tool.opencode_clients = lambda: [(200, ["opencode", "--session", "ses_other"], "/repo")]
	f.tool.opencode_pid = lambda: 100
	old = os.environ.get("OPENCODE_SESSION_ID")
	os.environ["OPENCODE_SESSION_ID"] = "ses_unknown"
	try:
		xtest.equal(f.tool.session_client_pid(), 100, "a v1-shaped session still resolves")
	finally:
		if old is None:
			os.environ.pop("OPENCODE_SESSION_ID", None)
		else:
			os.environ["OPENCODE_SESSION_ID"] = old

@_fixture
def test_a_named_id_wins_over_the_client(f):
	f.tool.session_client_pid = lambda: 100
	old = os.environ.get("OPENCODE_AGENT_ID")
	os.environ["OPENCODE_AGENT_ID"] = "ws/secretary-7"
	try:
		xtest.equal(f.tool.session_key(), "ws/secretary-7", "the launcher's allocation is the identity")
	finally:
		if old is None:
			os.environ.pop("OPENCODE_AGENT_ID", None)
		else:
			os.environ["OPENCODE_AGENT_ID"] = old

def test_the_launcher_is_still_a_valid_shell_script():
	proc = subprocess.run(["bash", "-n", str(LAUNCHER)], capture_output=True, text=True)
	xtest.equal(proc.returncode, 0, proc.stderr or "oc-agent parses")

def test_the_launcher_exports_the_name_it_allocated():
	"""End to end, with opencode faked: the window's name is agent-coord's.

	The copies are what makes this safe to run: agent-coord keeps its state
	beside its own script, so the launcher under test must be a copy in a
	temporary tree, or the test would allocate a number in this repository's
	live `.agents` folder.
	"""
	root = Path(tempfile.mkdtemp())
	try:
		ws = root / "ws"
		(ws / ".agents").mkdir(parents=True)
		(root / ".agents").mkdir()
		tools = root / "tools"
		tools.mkdir()
		shutil.copy(TOOL, tools / "agent-coord.py")
		shutil.copy(LAUNCHER, tools / "oc-agent")
		bin = root / "bin"
		bin.mkdir()
		fake = bin / "opencode"
		fake.write_text(
			'#!/bin/bash\n'
			'if [ "$1" = api ] && [ "$2" = get ]; then\n'
			"\tprintf '%s' '{\"data\":[{\"name\":\"secretary\",\"mode\":\"all\",\"model\":null}]}'\n"
			'\texit 0\n'
			'fi\n'
			'if [ "$1" = api ] && [ "$2" = post ]; then\n'
			"\tprintf '%s' '{\"data\":{\"id\":\"ses_test\"}}'\n"
			'\texit 0\n'
			'fi\n'
			'env > "$FAKE_ENV_OUT"\n'
			'exit 0\n', encoding="utf-8")
		fake.chmod(0o755)
		env = dict(os.environ, PATH=str(bin) + ":" + os.environ["PATH"],
			FAKE_ENV_OUT=str(root / "env.txt"))
		proc = subprocess.run([str(tools / "oc-agent"), "secretary"],
			cwd=str(ws), env=env, capture_output=True, text=True)
		xtest.equal(proc.returncode, 0, proc.stderr or "the launcher runs")
		xtest.contains("\033]2;secretary\007", proc.stdout, "the window is named")
		exported = (root / "env.txt").read_text(encoding="utf-8")
		xtest.contains("OPENCODE_AGENT_ID=ws/secretary-1", exported, "the allocated id is exported")
		xtest.contains("OPENCODE_AGENT_NAME=secretary", exported, "the window name is exported")
		xtest.contains("OPENCODE_AGENT_ROLE=secretary", exported, "the role is exported")
		ids = json.loads((root / ".agents" / "ids.json").read_text(encoding="utf-8"))
		xtest.equal(ids, {}, "the number is given back when the window closes")
	finally:
		shutil.rmtree(root)

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
