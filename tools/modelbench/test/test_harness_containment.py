"""Harness containment: the episode sandbox must contain every write.

The harness path runs `opencode run` inside a sandbox and relies on opencode to stay
there. A model can write an absolute path and leave the episode directory. Measured,
not inferred: in the stored harness turns there is a successful write to
`/tmp/opencode/verify_invoicer.py`, outside the run's sandbox
(`/tmp/opencode/ep-<episode>-*`).

This test suite verifies:
- A synthetic event stream whose write is inside the root is unaffected
- An absolute path outside the root yields `not-measurable` and names the path
- A `../` escape is caught
- Read/run parts do not false-positive
"""
import os,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest,agent,transport

def _harness_stream_mock(events,info=None):
	"""Mock transport.harness_stream to return our synthetic events."""
	if info is None:
		info = {"returncode":0,"timed_out":False,"stderr":"","provider_error":"","stdout":""}
	return events,info

def test_write_inside_sandbox_is_unaffected():
	"""A write whose target is inside the sandbox root proceeds normally."""
	with tempfile.TemporaryDirectory() as sandbox:
		# Create a file inside the sandbox for the model to edit
		target = os.path.join(sandbox,"app.py")
		with open(target,"w") as f:
			f.write("x = 1\n")

		events = [
			{"type":"step_start","part":{}},
			{"type":"tool_use","part":{
				"tool":"edit",
				"state":{"input":{"filePath":target},"status":"completed","output":"wrote"}
			}},
			{"type":"step_finish","part":{"reason":"tool-calls","tokens":{"input":100,"output":50}}},
			{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
		]
		saved = transport.harness_stream
		transport.harness_stream = lambda m,p,w,t: _harness_stream_mock(events)
		try:
			raw = agent.run_episode_harness(
				{"id":"m","provider":"zen","transport":"harness"},
				"fix it",sandbox)
		finally:
			transport.harness_stream = saved

		# Normal completion, no containment failure
		xtest.not_contains("outside_sandbox", raw,
			"a write inside the sandbox does not trigger containment failure")
		xtest.equal(len(raw["turns"]),2,"the write and finish turns are present")

def test_absolute_path_outside_sandbox_yields_not_measurable():
	"""An absolute path outside the sandbox root yields not-measurable with provenance."""
	with tempfile.TemporaryDirectory() as sandbox:
		# Target is completely outside the sandbox
		outside = "/tmp/opencode/verify_invoicer.py"

		events = [
			{"type":"step_start","part":{}},
			{"type":"tool_use","part":{
				"tool":"write",
				"state":{"input":{"filePath":outside},"status":"completed","output":"wrote"}
			}},
			{"type":"step_finish","part":{"reason":"tool-calls","tokens":{"input":100,"output":50}}},
			{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
		]
		saved = transport.harness_stream
		transport.harness_stream = lambda m,p,w,t: _harness_stream_mock(events)
		try:
			raw = agent.run_episode_harness(
				{"id":"m","provider":"zen","transport":"harness"},
				"fix it",sandbox)
		finally:
			transport.harness_stream = saved

		xtest.true("outside_sandbox" in raw,"containment failure is recorded")
		xtest.equal(len(raw["outside_sandbox"]),1,"exactly one outside write recorded")
		xtest.equal(raw["outside_sandbox"][0]["tool"],"write","tool name is recorded")
		xtest.equal(raw["outside_sandbox"][0]["path"],outside,"the absolute path is named")
		# Turns and raw session are kept for the audit trail
		xtest.true(len(raw["turns"]) >= 1,"turns are kept in the trace")
		xtest.true(raw["session"] != "" or True,"session id field exists")

def test_dotdot_escape_is_caught():
	"""A `../` escape from the sandbox is caught."""
	with tempfile.TemporaryDirectory() as sandbox:
		# Target uses ../ to escape the sandbox
		escape = os.path.join(sandbox,"subdir","..","..","outside.txt")

		events = [
			{"type":"step_start","part":{}},
			{"type":"tool_use","part":{
				"tool":"edit",
				"state":{"input":{"filePath":escape},"status":"completed","output":"wrote"}
			}},
			{"type":"step_finish","part":{"reason":"tool-calls","tokens":{"input":100,"output":50}}},
			{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
		]
		saved = transport.harness_stream
		transport.harness_stream = lambda m,p,w,t: _harness_stream_mock(events)
		try:
			raw = agent.run_episode_harness(
				{"id":"m","provider":"zen","transport":"harness"},
				"fix it",sandbox)
		finally:
			transport.harness_stream = saved

		xtest.true("outside_sandbox" in raw,"dotdot escape triggers containment failure")
		xtest.equal(raw["outside_sandbox"][0]["tool"],"edit")
		# The resolved absolute path should be outside the sandbox
		xtest.true(not raw["outside_sandbox"][0]["path"].startswith(os.path.realpath(sandbox) + os.sep),
			"resolved path is outside the sandbox root")

def test_read_outside_sandbox_does_not_trigger():
	"""A read tool call outside the sandbox does NOT trigger containment (only writes)."""
	with tempfile.TemporaryDirectory() as sandbox:
		outside = "/etc/passwd"

		events = [
			{"type":"step_start","part":{}},
			{"type":"tool_use","part":{
				"tool":"read",
				"state":{"input":{"filePath":outside},"status":"completed","output":"content"}
			}},
			{"type":"step_finish","part":{"reason":"tool-calls","tokens":{"input":100,"output":50}}},
			{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
		]
		saved = transport.harness_stream
		transport.harness_stream = lambda m,p,w,t: _harness_stream_mock(events)
		try:
			raw = agent.run_episode_harness(
				{"id":"m","provider":"zen","transport":"harness"},
				"fix it",sandbox)
		finally:
			transport.harness_stream = saved

		xtest.not_contains("outside_sandbox", raw,
			"a read outside the sandbox does not trigger containment failure")

def test_run_outside_sandbox_does_not_trigger():
	"""A run (bash) tool call does not trigger containment (it has no file path)."""
	with tempfile.TemporaryDirectory() as sandbox:
		events = [
			{"type":"step_start","part":{}},
			{"type":"tool_use","part":{
				"tool":"bash",
				"state":{"input":{"command":"ls /tmp"},
					"status":"completed","output":"files",
					"metadata":{"metadata":{"exit":0}}}
			}},
			{"type":"step_finish","part":{"reason":"tool-calls","tokens":{"input":100,"output":50}}},
			{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
		]
		saved = transport.harness_stream
		transport.harness_stream = lambda m,p,w,t: _harness_stream_mock(events)
		try:
			raw = agent.run_episode_harness(
				{"id":"m","provider":"zen","transport":"harness"},
				"fix it",sandbox)
		finally:
			transport.harness_stream = saved

		xtest.not_contains("outside_sandbox", raw,
			"a run tool does not trigger containment failure")

def test_multiple_write_tools_all_checked():
	"""All write-like tools (write, edit, patch, multiedit, apply_patch) are checked."""
	with tempfile.TemporaryDirectory() as sandbox:
		outside = "/tmp/outside.txt"

		for tool in ("write","edit","patch","multiedit","apply_patch"):
			events = [
				{"type":"step_start","part":{}},
				{"type":"tool_use","part":{
					"tool":tool,
					"state":{"input":{"filePath":outside},"status":"completed","output":"wrote"}
				}},
				{"type":"step_finish","part":{"reason":"tool-calls","tokens":{"input":100,"output":50}}},
				{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
			]
			saved = transport.harness_stream
			transport.harness_stream = lambda m,p,w,t: _harness_stream_mock(events)
			try:
				raw = agent.run_episode_harness(
					{"id":"m","provider":"zen","transport":"harness"},
					"fix it",sandbox)
			finally:
				transport.harness_stream = saved

			xtest.true("outside_sandbox" in raw,
				f"tool {tool!r} outside sandbox triggers containment failure")
			xtest.equal(raw["outside_sandbox"][0]["tool"],tool)

def test_path_field_variants_are_handled():
	"""opencode uses filePath, path, and file — all are checked."""
	with tempfile.TemporaryDirectory() as sandbox:
		outside = "/tmp/outside.txt"

		for field in ("filePath","path","file"):
			events = [
				{"type":"step_start","part":{}},
				{"type":"tool_use","part":{
					"tool":"write",
					"state":{"input":{field:outside},"status":"completed","output":"wrote"}
				}},
				{"type":"step_finish","part":{"reason":"tool-calls","tokens":{"input":100,"output":50}}},
				{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
			]
			saved = transport.harness_stream
			transport.harness_stream = lambda m,p,w,t: _harness_stream_mock(events)
			try:
				raw = agent.run_episode_harness(
					{"id":"m","provider":"zen","transport":"harness"},
					"fix it",sandbox)
			finally:
				transport.harness_stream = saved

			xtest.true("outside_sandbox" in raw,
				f"field {field!r} outside sandbox triggers containment failure")

def test_inside_write_after_outside_write_still_fails():
	"""If any write is outside, the whole run is not-measurable, even if later writes are inside."""
	with tempfile.TemporaryDirectory() as sandbox:
		inside = os.path.join(sandbox,"app.py")
		outside = "/tmp/outside.txt"
		with open(inside,"w") as f:
			f.write("x = 1\n")

		events = [
			{"type":"step_start","part":{}},
			{"type":"tool_use","part":{
				"tool":"write",
				"state":{"input":{"filePath":outside},"status":"completed","output":"wrote"}
			}},
			{"type":"step_start","part":{}},
			{"type":"tool_use","part":{
				"tool":"edit",
				"state":{"input":{"filePath":inside},"status":"completed","output":"wrote"}
			}},
			{"type":"step_finish","part":{"reason":"tool-calls","tokens":{"input":200,"output":100}}},
			{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
		]
		saved = transport.harness_stream
		transport.harness_stream = lambda m,p,w,t: _harness_stream_mock(events)
		try:
			raw = agent.run_episode_harness(
				{"id":"m","provider":"zen","transport":"harness"},
				"fix it",sandbox)
		finally:
			transport.harness_stream = saved

		xtest.true("outside_sandbox" in raw)
		# Both writes should be recorded in outside_sandbox
		xtest.equal(len(raw["outside_sandbox"]),1,"only the outside write is recorded")

def test_symlink_escape_is_caught():
	"""A symlink pointing outside the sandbox is caught via realpath resolution."""
	with tempfile.TemporaryDirectory() as sandbox:
		# Create a symlink inside sandbox pointing outside
		outside_dir = tempfile.mkdtemp()
		outside_file = os.path.join(outside_dir,"target.txt")
		link = os.path.join(sandbox,"link.txt")
		os.symlink(outside_file,link)

		events = [
			{"type":"step_start","part":{}},
			{"type":"tool_use","part":{
				"tool":"write",
				"state":{"input":{"filePath":link},"status":"completed","output":"wrote"}
			}},
			{"type":"step_finish","part":{"reason":"tool-calls","tokens":{"input":100,"output":50}}},
			{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
		]
		saved = transport.harness_stream
		transport.harness_stream = lambda m,p,w,t: _harness_stream_mock(events)
		try:
			raw = agent.run_episode_harness(
				{"id":"m","provider":"zen","transport":"harness"},
				"fix it",sandbox)
		finally:
			transport.harness_stream = saved

		xtest.true("outside_sandbox" in raw,
			"symlink escape is caught via realpath resolution")

def test_relative_path_inside_sandbox_is_unaffected():
	"""A relative path inside the sandbox (e.g. 'src/app.py') does not trigger containment."""
	with tempfile.TemporaryDirectory() as sandbox:
		# Create a subdir and file inside sandbox
		subdir = os.path.join(sandbox,"src")
		os.makedirs(subdir)
		target = os.path.join(subdir,"app.py")
		with open(target,"w") as f:
			f.write("x = 1\n")

		# opencode may report relative path
		rel_path = "src/app.py"

		events = [
			{"type":"step_start","part":{}},
			{"type":"tool_use","part":{
				"tool":"edit",
				"state":{"input":{"filePath":rel_path},"status":"completed","output":"wrote"}
			}},
			{"type":"step_finish","part":{"reason":"tool-calls","tokens":{"input":100,"output":50}}},
			{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
		]
		saved = transport.harness_stream
		transport.harness_stream = lambda m,p,w,t: _harness_stream_mock(events)
		try:
			raw = agent.run_episode_harness(
				{"id":"m","provider":"zen","transport":"harness"},
				"fix it",sandbox)
		finally:
			transport.harness_stream = saved

		xtest.not_contains("outside_sandbox", raw,
			"relative path inside sandbox does not trigger containment failure")

def test_relative_dotdot_escape_is_caught():
	"""A relative path with ../ that escapes the sandbox is caught."""
	with tempfile.TemporaryDirectory() as sandbox:
		# Relative path that escapes via ../
		escape = "subdir/../../outside.txt"

		events = [
			{"type":"step_start","part":{}},
			{"type":"tool_use","part":{
				"tool":"write",
				"state":{"input":{"filePath":escape},"status":"completed","output":"wrote"}
			}},
			{"type":"step_finish","part":{"reason":"tool-calls","tokens":{"input":100,"output":50}}},
			{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
		]
		saved = transport.harness_stream
		transport.harness_stream = lambda m,p,w,t: _harness_stream_mock(events)
		try:
			raw = agent.run_episode_harness(
				{"id":"m","provider":"zen","transport":"harness"},
				"fix it",sandbox)
		finally:
			transport.harness_stream = saved

		xtest.true("outside_sandbox" in raw,
			"relative dotdot escape triggers containment failure")
		# The resolved path should be outside the sandbox
		xtest.true(not raw["outside_sandbox"][0]["path"].startswith(os.path.realpath(sandbox) + os.sep),
			"resolved path is outside the sandbox root")

def test_absolute_outside_path_still_caught():
	"""An absolute path outside the sandbox is still caught (regression test)."""
	with tempfile.TemporaryDirectory() as sandbox:
		outside = "/tmp/opencode/verify_invoicer.py"

		events = [
			{"type":"step_start","part":{}},
			{"type":"tool_use","part":{
				"tool":"write",
				"state":{"input":{"filePath":outside},"status":"completed","output":"wrote"}
			}},
			{"type":"step_finish","part":{"reason":"tool-calls","tokens":{"input":100,"output":50}}},
			{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
		]
		saved = transport.harness_stream
		transport.harness_stream = lambda m,p,w,t: _harness_stream_mock(events)
		try:
			raw = agent.run_episode_harness(
				{"id":"m","provider":"zen","transport":"harness"},
				"fix it",sandbox)
		finally:
			transport.harness_stream = saved

		xtest.true("outside_sandbox" in raw,
			"absolute outside path still triggers containment failure")
		xtest.equal(raw["outside_sandbox"][0]["path"],outside)

def test_pipeline_run_once_returns_not_measurable():
	"""Pipeline test: run_once -> analyse -> grade returns not-measurable for outside write."""
	import episodes_run,trace

	with tempfile.TemporaryDirectory() as sandbox:
		# Create a minimal episode structure (just need the directory to exist)
		# The mock will intercept harness_stream so we don't need real episode files
		outside = "/tmp/opencode/verify_invoicer.py"

		events = [
			{"type":"step_start","part":{}},
			{"type":"tool_use","part":{
				"tool":"write",
				"state":{"input":{"filePath":outside},"status":"completed","output":"wrote"}
			}},
			{"type":"step_finish","part":{"reason":"tool-calls","tokens":{"input":100,"output":50}}},
			{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
		]
		saved_stream = transport.harness_stream
		transport.harness_stream = lambda m,p,w,t: _harness_stream_mock(events)
		# Mock check_episode to avoid checker_dead (no check.py in mock sandbox)
		saved_check = trace.check_episode
		trace.check_episode = lambda root, checker="check.py": (True, {"cases":[], "checker_dead":False, "checker_fault":False})
		try:
			# Mock a minimal episode dict
			episode = {"name":"test","dir":sandbox,"request":"fix it",
				"baseline_pass":True,"baseline":{"cases":[]}}
			model = {"id":"m","provider":"zen","transport":"harness"}
			with tempfile.TemporaryDirectory() as run_root:
				result = episodes_run.run_once(model,episode,run_root)
		finally:
			transport.harness_stream = saved_stream
			trace.check_episode = saved_check

		xtest.equal(result["grade"],"not-measurable",
			"pipeline grades outside-sandbox write as not-measurable")
		xtest.equal(result["failed_gates"],["outside_sandbox"],
			"failed_gates names outside_sandbox")
		xtest.true("outside_sandbox" in result["trace"],
			"trace carries the containment marker")
		xtest.equal(len(result["trace"]["outside_sandbox"]),1)
		xtest.equal(result["trace"]["outside_sandbox"][0]["tool"],"write")
		xtest.equal(result["trace"]["outside_sandbox"][0]["path"],outside)

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
