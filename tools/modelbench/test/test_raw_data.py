"""The measurement layer has to stand on its own, or a benchmark cannot be built over it.

The human's structure, 2026-10-20:

  * **Measurement** — the actual runs, with the full data: prompt, turns, model, settings,
    timestamps.
  * **Benchmark** — the bar to measure against. If measurements are available, benchmarks
    can be constructed later, over data already collected.
  * **Evaluation** — the synthesis of the two: what it all means.

So the measurement is the part that has to be complete, and the part that must not depend
on the benchmark or the evaluation being the way they are today. Three things were missing
and are fixed here:

  1. **The harness path threw the session away.** The mapping reads opencode's event
     stream, so the stream IS the raw end of that measurement — and it was not kept. A
     change to the mapping therefore could not be re-applied to a stored harness row, and
     the model's own text between turns was gone entirely.
  2. **Both paths truncated what they stored** — the reply at 1500 characters, the tool
     output at 400. The cut is not harmless: the checker's own verdict is the evidence for
     G2, and a report longer than 1500 characters is most of a report.
  3. **The record did not say what it was.** No prompt, no settings, no timestamps, no
     episode content, and the state's path was an absolute path on this machine.

**The rule underneath all of it**, from the human, 2026-10-20: *for every experiment, keep
as much data as possible. Deciding that some data is irrelevant can easily be done after
the fact, but the reverse is impossible, so keeping more than needed is a safe default.*
"""
import json,os,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import agent
import episodes_run
import transport

def test_the_episode_hash_says_what_the_model_was_asked():
	"""A name does not survive the episode being edited. `invoicer` was the same name
	before and after its reconciliation table was re-aligned."""
	with tempfile.TemporaryDirectory() as d:
		with open(os.path.join(d,"REQUEST.md"),"w") as fh:
			fh.write("fix the tax rule")
		first = episodes_run.episode_hash(d)
		xtest.true(first.startswith("ep-"))
		with open(os.path.join(d,"SPEC.md"),"w") as fh:
			fh.write("| 7 | 10 | 20 | 2160 |")
		xtest.not_equal(episodes_run.episode_hash(d),first,
			"a changed episode must not keep the old hash")
	with tempfile.TemporaryDirectory() as d:
		with open(os.path.join(d,"REQUEST.md"),"w") as fh:
			fh.write("fix the tax rule")
		xtest.equal(episodes_run.episode_hash(d),first,
			"the same content must hash the same")

def test_a_direct_measurement_keeps_the_prompt_and_the_settings():
	"""The direct path, with the provider stubbed out."""
	saved = transport.call_chat
	replies = [
		{"text":"ACTION: finish\nSUMMARY: done\nSTATUS: done","raw_tokens":10,
			"finish_reason":"stop","raw":'{"choices":[]}'},
	]
	def stub(model,messages,**kw):
		return replies.pop(0)
	transport.call_chat = stub
	try:
		with tempfile.TemporaryDirectory() as sandbox:
			raw = agent.run_episode({"id":"m","provider":"zen","transport":"http"},
				"fix the tax rule",sandbox)
	finally:
		transport.call_chat = saved
	xtest.true("fix the tax rule" in raw["prompt"],
		"a measurement must say what it asked")
	xtest.true(raw["messages"] and raw["messages"][0]["role"] == "system",
		"and the request it was made in")
	xtest.equal(raw["turns"][0]["raw"],'{"choices":[]}',
		"the provider's own response is kept, not only what was parsed out of it")
	xtest.equal(raw["turns"][0]["finish_reason"],"stop",
		"a truncated-by-budget answer and an empty answer are different things")

def test_nothing_stored_is_cut_short():
	"""The reply was cut at 1500 characters and the tool output at 400. The cut can hide
	the checker's own verdict, which is the evidence for G2."""
	long_reply = "x" * 5000
	long_result = "all 5 cases pass\n" + ("y" * 5000)
	saved = transport.call_chat
	saved_execute = agent.execute
	def stub(model,messages,**kw):
		return {"text":long_reply,"raw_tokens":1,"finish_reason":"stop","raw":"{}"}
	def fake_execute(action,root):
		return long_result
	transport.call_chat = stub
	agent.execute = fake_execute
	try:
		with tempfile.TemporaryDirectory() as sandbox:
			raw = agent.run_episode({"id":"m","provider":"zen","transport":"http"},
				"fix it",sandbox)
	finally:
		transport.call_chat = saved
		agent.execute = saved_execute
	xtest.equal(len(raw["turns"][0]["reply"]),5000,"the reply is kept whole")
	xtest.equal(len(raw["turns"][0]["result"]),len(long_result),
		"the tool output is kept whole")

def test_a_harness_measurement_keeps_the_session():
	"""The harness path's input is opencode's event stream, so the stream is the raw end
	of that measurement — and it was thrown away."""
	events = [
		{"type":"step_start","part":{}},
		{"type":"tool_use","part":{"tool":"bash","state":{"input":{"command":"python3 check.py"},
			"metadata":{"metadata":{"exit":0}},"status":"completed","output":"all 5 cases pass"}}},
		{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
	]
	raw_stdout = "\n".join(json.dumps(e) for e in events)
	saved = transport.harness_stream
	def stub(model,prompt,workdir,timeout):
		return events,{"returncode":0,"timed_out":False,"stderr":"","stdout":raw_stdout}
	transport.harness_stream = stub
	try:
		with tempfile.TemporaryDirectory() as sandbox:
			raw = agent.run_episode_harness({"id":"m","provider":"zen","transport":"harness"},
				"fix it",sandbox)
	finally:
		transport.harness_stream = saved
	xtest.equal(raw["raw"],raw_stdout,
		"the session's own output is the raw end of the measurement and is kept")
	xtest.true("fix it" in raw["prompt"],"and what it was asked")
	xtest.equal(raw["turns"][0]["result"],"all 5 cases pass",
		"the tool output is kept whole, because the checker's verdict is the evidence")

def test_a_harness_measurement_names_its_session():
	"""opencode keeps every session in its own database — the prompt, the reasoning, the
	tool calls and their outputs — so the session id is a handle: the raw data can be
	restored from there, and a record that names its session can be joined to one."""
	events = [
		{"type":"step_start","part":{},"sessionID":"ses_abc123"},
		{"type":"tool_use","part":{"tool":"bash","state":{"input":{"command":"python3 check.py"},
			"metadata":{"metadata":{"exit":0}},"status":"completed","output":"all 5 cases pass"}}},
		{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
	]
	saved = transport.harness_stream
	def stub(model,prompt,workdir,timeout):
		return events,{"returncode":0,"timed_out":False,"stderr":"","stdout":"{}"}
	transport.harness_stream = stub
	try:
		with tempfile.TemporaryDirectory() as sandbox:
			raw = agent.run_episode_harness({"id":"m","provider":"zen","transport":"harness"},
				"fix it",sandbox)
	finally:
		transport.harness_stream = saved
	xtest.equal(raw["session"],"ses_abc123",
		"the record names the session its data can be restored from")

def test_the_record_says_when_it_ran_and_under_what_settings():
	"""A measurement without a timestamp cannot be placed, and one without its settings
	cannot be reproduced."""
	saved = transport.call_chat
	def stub(model,messages,**kw):
		return {"text":"ACTION: finish\nSUMMARY: done\nSTATUS: done","raw_tokens":10,
			"finish_reason":"stop","raw":"{}"}
	transport.call_chat = stub
	try:
		episode = {"name":"invoicer","dir":os.path.join(REPO,"tools","modelbench","episodes","invoicer"),
			"request":"fix the tax rule","baseline":{"cases":[]},"baseline_pass":False}
		with tempfile.TemporaryDirectory() as root:
			result = episodes_run.run_once({"id":"m","provider":"zen","transport":"http",
				"endpoint":"https://example.invalid"},episode,root)
	finally:
		transport.call_chat = saved
	xtest.true(result["started"] > 0 and result["ended"] >= result["started"],
		"the record says when the run happened")
	xtest.equal(result["settings"]["max_turns"],agent.MAX_TURNS)
	xtest.equal(result["settings"]["provider"],"zen")
	xtest.true(result["episode_hash"].startswith("ep-"),
		"the record says which episode CONTENT it ran against, not only its name")
	xtest.true("fix the tax rule" in result["trace"]["prompt"],
		"the prompt is part of the measurement")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
