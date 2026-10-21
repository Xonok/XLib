"""A harness run can be re-graded from opencode's session database, without the model.

The corpus's rule is that a measurement is not edited: a correction is a NEW record
beside the old one. That rule needs a way to produce the new record, and re-measuring
is the wrong way — it costs a model call, a provider's quota, and it measures the
model again rather than reading what was already measured.

**The database holds the raw end of the measurement.** opencode keeps every session:
the prompt, the reasoning, the tool calls with their inputs and outputs, the exit code
of every command, the model's own text. So a row whose mapping was broken can be
re-derived by rebuilding the event stream the mapping reads and applying the LANDED
mapping to it.

**These tests are about the five places the database and the stream disagree**, because
each of those silently moves a turn, and four of the five read as "the model did
something slightly different" rather than as a shape this tool does not know:

1. the tool's name is `name` in the database and `tool` in the stream;
2. the output is `state.content` (a list) in the database and `state.output` (a
   string) in the stream, and the rendered content carries an extra line the stream
   never had;
3. the exit code is hoisted one level up in the database;
4. a `step_finish` is emitted only for a step that made tool calls;
5. tool calls come out in completion order in the stream and in creation order in the
   database — and the order decides which turn a write landed on.

Plus the one that is not a shape difference but a fact: a session with a refused step
exits non-zero even when it recovers, so it reads as unfinished.
"""
import json,os,sqlite3,sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import db_regrade

def _db():
	"""A session database with the two tables this reads."""
	db = sqlite3.connect(":memory:")
	db.row_factory = sqlite3.Row
	db.execute("create table session_v2 (id text primary key, directory text, time_created integer)")
	db.execute("create table session_message (id text primary key, session_id text, type text, "
		"seq integer, data text)")
	return db

def _session(db,sid,messages,directory="/tmp/opencode/ep-invoicer-abc123"):
	db.execute("insert into session_v2 values (?,?,?)",(sid,directory,0))
	for seq,(mtype,data) in enumerate(messages):
		db.execute("insert into session_message values (?,?,?,?,?)",
			(f"msg_{seq}",sid,mtype,seq,json.dumps(data)))

def _tool(name,path=None,exit_code=0,output="ok",created=0,completed=0):
	state = {"status":"completed","input":{"path":path} if path else {},
		"content":[{"type":"text","text":output}],"metadata":{"status":"completed",
			"truncated":False,"exit":exit_code}}
	return {"type":"tool","id":"call_x","name":name,
		"time":{"created":created,"ran":created,"completed":completed},"state":state}

def test_the_exit_code_is_read_out_of_the_database():
	"""The one the ticket asked about: is the exit code there? It is."""
	db = _db()
	_session(db,"ses_a",[("assistant",{"finish":"tool-calls","content":[_tool("shell",exit_code=0)],
		"tokens":{"input":10,"output":5,"reasoning":0,"cache":{"read":0,"write":0}}})])
	events,info = db_regrade.session_events(db,"ses_a")
	tool = [e for e in events if e["type"] == "tool_use"][0]
	xtest.equal(tool["part"]["state"]["metadata"]["metadata"]["exit"],0,
		"the exit code is in the database, one level up from the stream's")

def test_a_command_that_failed_keeps_its_exit_code():
	db = _db()
	_session(db,"ses_a",[("assistant",{"finish":"tool-calls","content":[_tool("shell",exit_code=1)],
		"tokens":{}})])
	events,_ = db_regrade.session_events(db,"ses_a")
	tool = [e for e in events if e["type"] == "tool_use"][0]
	xtest.equal(tool["part"]["state"]["metadata"]["metadata"]["exit"],1)

def test_the_output_does_not_carry_the_line_the_stream_never_had():
	"""opencode renders 'Exited with code N' into the content; the stream's output lacks it."""
	state = {"status":"completed","input":{},"content":[{"type":"text","text":"hello\n"},
		{"type":"text","text":"Exited with code 3"}],"metadata":{"exit":3}}
	xtest.equal(db_regrade.output_of(state),"hello\n")

def test_a_command_that_succeeded_keeps_all_of_its_output():
	state = {"status":"completed","input":{},"content":[{"type":"text","text":"pass recon-1\n"}],
		"metadata":{"exit":0}}
	xtest.equal(db_regrade.output_of(state),"pass recon-1\n")

def test_tool_calls_come_out_in_completion_order():
	"""The stream printed a call when it completed; the database keeps creation order."""
	db = _db()
	tools = [_tool("read","a.md",created=10,completed=90),
		_tool("read","b.md",created=20,completed=50),
		_tool("read","c.md",created=30,completed=70)]
	_session(db,"ses_a",[("assistant",{"finish":"tool-calls","content":tools,"tokens":{}})])
	events,_ = db_regrade.session_events(db,"ses_a")
	paths = [e["part"]["state"]["input"]["path"] for e in events if e["type"] == "tool_use"]
	xtest.equal(paths,["b.md","c.md","a.md"],"completion order, not creation order")

def test_only_a_step_with_tool_calls_ends_a_step():
	"""The final text step carries no step_finish, so the session's last token total
	in the stream is the last TOOL-CALLING step's."""
	db = _db()
	_session(db,"ses_a",[
		("assistant",{"finish":"tool-calls","content":[_tool("read","a.md")],"tokens":{"input":1}}),
		("assistant",{"finish":"stop","content":[{"type":"text","text":"done"}],
			"tokens":{"input":2}}),
	])
	events,_ = db_regrade.session_events(db,"ses_a")
	finishes = [e for e in events if e["type"] == "step_finish"]
	xtest.equal(len(finishes),1,"one step_finish, for the step that made tool calls")
	xtest.equal(finishes[0]["part"]["tokens"],{"input":1})

def test_a_session_that_spoke_exited_cleanly():
	db = _db()
	_session(db,"ses_a",[("assistant",{"finish":"stop","content":[{"type":"text","text":"done"}],
		"tokens":{}})])
	_,info = db_regrade.session_events(db,"ses_a")
	xtest.equal(info["returncode"],0)

def test_a_refused_step_means_the_run_did_not_exit_cleanly():
	"""Even when the session recovered and spoke: the CLI exits non-zero."""
	db = _db()
	_session(db,"ses_a",[
		("assistant",{"finish":"error","content":[],"tokens":{},
			"error":{"type":"provider.invalid-output","message":"stream ended without finish_reason"}}),
		("assistant",{"finish":"stop","content":[{"type":"text","text":"done"}],"tokens":{}}),
	])
	events,info = db_regrade.session_events(db,"ses_a")
	xtest.equal(info["returncode"],None,"a run with a refused step is not a clean exit")
	xtest.equal([e["type"] for e in events].count("error"),1,"and the refusal is an event")

def test_a_session_that_never_spoke_did_not_exit_cleanly():
	db = _db()
	_session(db,"ses_a",[("assistant",{"finish":"tool-calls","content":[_tool("read","a.md")],"tokens":{}})])
	_,info = db_regrade.session_events(db,"ses_a")
	xtest.equal(info["returncode"],None)

def test_the_prompt_is_the_session_s_own_first_user_message():
	db = _db()
	_session(db,"ses_a",[("user",{"text":"do the thing"}),
		("assistant",{"finish":"stop","content":[{"type":"text","text":"done"}],"tokens":{}})])
	xtest.equal(db_regrade.session_prompt(db,"ses_a"),"do the thing")

def test_a_session_is_found_by_its_sandbox_name():
	"""The record carries the sandbox; the session's directory is that sandbox."""
	db = _db()
	_session(db,"ses_zzz",[("assistant",{"finish":"stop","content":[],"tokens":{}})],
		directory="/tmp/opencode/ep-billing-xyz789")
	xtest.equal(db_regrade.find_session(db,"ep-billing-xyz789"),"ses_zzz")
	xtest.equal(db_regrade.find_session(db,"ep-nothing-here"),None)

def test_a_record_with_no_session_is_reported_as_such():
	db = _db()
	_session(db,"ses_a",[("assistant",{"finish":"stop","content":[],"tokens":{}})])
	got = db_regrade.regrade(db,{"sandbox":"/tmp/opencode/ep-gone-000000",
		"model":"m","transport":"harness"},"/tmp",None)
	xtest.equal(got,None,"a row whose session is not in the database cannot be re-graded")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
