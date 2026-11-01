"""A pid key records the process's start time, so a recycled pid frees the slot.

`pid_max` on this machine is 32768, so a pid is handed to an unrelated process
within hours. The old reaper asked only whether the pid existed, which meant a
slot whose owner was hard-killed was judged alive forever (epiq `JC5VSP0`).
The key now carries field 22 of `/proc/<pid>/stat` beside the pid, and a key
whose start time does not match the live process is a different process.

These are the reaping tests; the launcher's allocation is in
`test_agent_launch_name.py`.
"""
import importlib.util,json,os,sys,tempfile
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
		self.tool.agent_role = lambda: "secretary"

	def write(self, name, data):
		Path(self.tool.DIR, name).write_text(json.dumps(data), encoding="utf-8")

	def read(self, name):
		path = Path(self.tool.DIR, name)
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

def _key(pid, ticks):
	return "pid-%d@%d" % (pid, ticks)

@_fixture
def test_a_key_with_a_wrong_start_time_is_reaped(f):
	"""(JC5VSP0) The pid is live, but it is not the process the key names."""
	pid = os.getpid()
	f.write("ids.json", {_key(pid, f.tool.proc_starttime(pid) + 1): "ws/secretary-1"})
	f.write("claims.json", {"ws/secretary-1": ["/tmp/other.py"]})
	f.write("rule-cursor.json", {"ws/secretary-1": {"AGENTS.md": "abc"}})
	f.tool.recycle_dead_slots()
	xtest.equal(f.read("ids.json"), {}, "the number is free again")
	xtest.equal(f.read("claims.json"), {}, "and its claims went with it")
	xtest.equal(f.read("rule-cursor.json"), {}, "and its rule cursor")

@_fixture
def test_a_key_with_the_right_start_time_is_kept(f):
	pid = os.getpid()
	f.write("ids.json", {_key(pid, f.tool.proc_starttime(pid)): "ws/secretary-1"})
	f.tool.recycle_dead_slots()
	xtest.equal(f.read("ids.json"), {_key(pid, f.tool.proc_starttime(pid)): "ws/secretary-1"},
		"the live process keeps its number")

@_fixture
def test_a_legacy_key_still_reaps_when_its_pid_is_gone(f):
	"""Keys written before start times were recorded keep the old rule."""
	f.write("ids.json", {"pid-999999": "ws/secretary-1"})
	f.tool.recycle_dead_slots()
	xtest.equal(f.read("ids.json"), {}, "a dead pid without a start time is still dead")

@_fixture
def test_a_legacy_key_is_taken_over_rather_than_replaced(f):
	"""A live session keeps its name when its key gains a start time."""
	pid = os.getpid()
	f.tool.session_client_pid = lambda: pid
	f.write("ids.json", {"pid-%d" % pid: "ws/secretary-3"})
	xtest.equal(f.tool.my_id(), "ws/secretary-3", "the identity is the one it already had")
	xtest.equal(f.read("ids.json").get(_key(pid, f.tool.proc_starttime(pid))), "ws/secretary-3",
		"and it is written under the new key")

@_fixture
def test_the_session_key_records_the_start_time(f):
	f.tool.session_client_pid = lambda: os.getpid()
	xtest.equal(f.tool.session_key(), _key(os.getpid(), f.tool.proc_starttime(os.getpid())),
		"a session key names the process, not just its number")

def test_a_key_for_no_process_is_not_a_pid_key():
	tool = load_tool()
	xtest.equal(tool.pid_key_parts("ses-abc"), (None, None), "a session id is not a pid")
	xtest.equal(tool.pid_key_parts("pid-12@34"), (12, 34), "and the start time is read")
	xtest.equal(tool.pid_key_parts("pid-12"), (12, None), "a legacy key has no start time")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
