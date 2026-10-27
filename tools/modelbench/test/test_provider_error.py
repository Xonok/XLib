"""The provider's own explanation of a failed session reaches the record.

opencode reports a provider-side failure as an **event in the stream**, not on stderr:
`{"type":"error","error":{"type":"provider.quota","message":"Rate limit exceeded..."}}`.
The harness mapping ignored those events, so a session the provider refused produced a
record saying only `not-measurable` with an empty stderr — and a reader could not tell a
quota exhaustion from a model that refused to answer, from a transport that died.

Measured 2026-10-20: the console's own free tier ran out mid-wave and four models' six
runs each came back `not-measurable` with no reason at all. The explanation was in the
stream the whole time.
"""
import json,os,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import agent
import transport

QUOTA_EVENT = {"type":"error","timestamp":1,"sessionID":"ses_x","error":{
	"type":"provider.quota","message":"Rate limit exceeded. Please try again later.",
	"status":429,"response":{"body":"{\"type\":\"error\",\"error\":{\"type\":\"FreeUsageLimitError\"}}"}}}

def test_the_provider_error_is_read_out_of_the_event_stream():
	text = transport.provider_error([QUOTA_EVENT])
	xtest.contains("provider.quota",text,"the kind of failure is named")
	xtest.contains("Rate limit exceeded",text,"and so is what it said")

def test_a_stream_with_no_error_says_nothing():
	xtest.equal(transport.provider_error([{"type":"text","part":{"text":"hi"}}]),"")

def test_an_empty_stream_says_nothing():
	xtest.equal(transport.provider_error([]),"")

def test_the_record_carries_the_reason():
	"""A session the provider refused must not come out as a bare 'not-measurable'."""
	saved = transport.harness_stream
	transport.harness_stream = lambda model,prompt,workdir,timeout: ([QUOTA_EVENT],
		{"returncode":0,"timed_out":False,"stderr":"","provider_error":
			transport.provider_error([QUOTA_EVENT])})
	try:
		with tempfile.TemporaryDirectory() as sandbox:
			raw = agent.run_episode_harness({"id":"m","provider":"zen","transport":"harness"},
				"do the thing",sandbox)
	finally:
		transport.harness_stream = saved
	xtest.contains("provider.quota",raw.get("provider_error",""),
		"the record says why the session produced nothing")
	xtest.equal(raw["n_turns"],0,"and it still produced no turns")

def test_the_reason_survives_into_the_stored_row():
	"""The record is what a reader reads later, so the reason has to be in it."""
	import episodes_run
	real = episodes_run.trace.analyse
	real_stream = transport.harness_stream
	episodes_run.trace.analyse = lambda raw,baseline=None,**kw: {
		"detail":{"n_turns":0,"checker":{"cases":[]}},"gates":{},"grade":"not-measurable"}
	transport.harness_stream = lambda model,prompt,workdir,timeout: ([QUOTA_EVENT],
		{"returncode":0,"timed_out":False,"stderr":"",
			"provider_error":transport.provider_error([QUOTA_EVENT])})
	try:
		with tempfile.TemporaryDirectory() as sandbox:
			with tempfile.TemporaryDirectory() as episode_dir:
				result = episodes_run.run_once({"id":"m","provider":"zen","transport":"harness"},
					{"name":"e","request":"r","baseline":{},"dir":episode_dir},sandbox)
	finally:
		episodes_run.trace.analyse = real
		transport.harness_stream = real_stream
	xtest.contains("provider.quota",result["provenance"].get("provider_error",""),
		"the stored row carries the provider's explanation")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
