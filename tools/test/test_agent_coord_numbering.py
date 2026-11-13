"""Instance numbers are one sequence per role for the machine.

`oc-agent` asks `agent-coord allocate` for a number before the session exists.
The number must not depend on the folder the window was opened in: a window
launched in one workspace and the next launched in another share one counter.
And the number must come back when the window closes, even if a dispatch the
window started is still running and carries its id in the environment -- the
number belongs to the launcher, and the launcher is gone.
"""
import argparse,contextlib,importlib.util,io,json,os,subprocess,sys,tempfile
from pathlib import Path

# xtest, found relative to this file rather than to the working directory: a
# path relative to the cwd only works from the repository root, and a test
# that runs from one directory and fails from another is worse than one that
# never runs.
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
import xtest

TOOL = REPO / "tools" / "agent-coord.py"

def load_tool():
	spec = importlib.util.spec_from_file_location("agent_coord", TOOL)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module

class Fixture:
	"""A tool whose one store serves several workspace folders."""

	def __init__(self):
		self.folder = tempfile.TemporaryDirectory()
		self.root = Path(self.folder.name)
		self.store = self.root / "store" / ".agents"
		self.store.mkdir(parents=True)
		self.tool = load_tool()
		self.tool.DIR = str(self.store)
		self.tool.LOCK = str(self.store / "lock")
		self.tool.IDS = str(self.store / "ids.json")
		self.tool.CLAIMS = str(self.store / "claims.json")
		self.tool.RULE_CURSOR = str(self.store / "rule-cursor.json")
		self.tool.agent_role = lambda: "secretary"
		self.workspace = self.root / "XLib"
		(self.workspace / ".agents").mkdir(parents=True)
		self.tool.workspace_root = lambda: str(self.workspace)
		self.launch_from("XLib")

	def launch_from(self, tag):
		"""Make the next launch open in a folder whose workspace tag is `tag`."""
		folder = self.root / tag
		(folder / ".agents").mkdir(parents=True, exist_ok=True)
		self.tool.launch_workspace = lambda: str(folder)

	def allocate(self, pid, role=None):
		out = io.StringIO()
		with contextlib.redirect_stdout(out):
			self.tool.cmd_allocate(argparse.Namespace(pid=pid, role=role))
		return out.getvalue().strip()

	def free(self, pid):
		self.tool.cmd_free(argparse.Namespace(pid=pid))

	def write(self, name, data):
		Path(self.tool.DIR, name).write_text(json.dumps(data), encoding="utf-8")

	def read(self, name):
		path = Path(self.tool.DIR, name)
		return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

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

def _worker_carrying(agent_id):
	"""A live process with the window's id in its environment.

	This is what a dispatch outliving its window looks like: a process that
	inherited `OPENCODE_AGENT_ID` and would share the notes file if the number
	were handed to a new window while it runs.
	"""
	return subprocess.Popen(["sleep", "60"],
		env=dict(os.environ, OPENCODE_AGENT_ID=agent_id))

@_fixture
def test_the_number_is_one_sequence_per_role_across_folders(f):
	f.launch_from("XLib")
	xtest.equal(f.allocate(os.getpid()), "XLib/secretary-1", "the first window in the first folder takes 1")
	f.launch_from("Agents")
	xtest.equal(f.allocate(os.getppid()), "Agents/secretary-2",
		"a window in another folder takes the next number, not 1 again")

@_fixture
def test_a_role_with_hyphens_is_a_sequence_of_its_own(f):
	xtest.equal(f.allocate(os.getpid(), role="worker-north-mini-code"),
		"XLib/worker-north-mini-code-1", "the long role counts from 1")
	xtest.equal(f.allocate(os.getppid(), role="worker-north"),
		"XLib/worker-north-1", "a shorter role does not see the long role's number")
	xtest.equal(f.allocate(1, role="worker-north-mini-code"),
		"XLib/worker-north-mini-code-2", "and the long role continues")

@_fixture
def test_a_closed_window_s_number_comes_back_while_a_worker_carries_it(f):
	f.write("ids.json", {"pid-910001": "XLib/overseer-1"})
	worker = _worker_carrying("XLib/overseer-1")
	try:
		xtest.equal(f.allocate(910002, role="overseer"), "XLib/overseer-1",
			"the dead launcher's number is free")
	finally:
		worker.terminate()
		worker.wait()

@_fixture
def test_the_reaper_does_not_hold_a_number_for_a_live_worker(f):
	f.write("ids.json", {"pid-910001": "XLib/overseer-1"})
	f.write("claims.json", {"XLib/overseer-1": ["/tmp/a.py"]})
	worker = _worker_carrying("XLib/overseer-1")
	try:
		f.tool.recycle_dead_slots()
		xtest.equal(f.read("ids.json"), {}, "the dead launcher's entry goes")
		xtest.equal(f.read("claims.json"), {}, "and its claims go with it")
	finally:
		worker.terminate()
		worker.wait()

@_fixture
def test_free_does_not_hold_a_number_for_a_live_worker(f):
	f.write("ids.json", {"pid-910001": "XLib/overseer-1"})
	worker = _worker_carrying("XLib/overseer-1")
	try:
		f.free(910001)
		xtest.equal(f.read("ids.json"), {}, "the owner exiting frees the number")
	finally:
		worker.terminate()
		worker.wait()

@_fixture
def test_a_live_launcher_keeps_its_number(f):
	xtest.equal(f.allocate(os.getpid()), "XLib/secretary-1", "the live launcher takes 1")
	xtest.equal(f.allocate(os.getppid()), "XLib/secretary-2", "and the next window takes 2")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
