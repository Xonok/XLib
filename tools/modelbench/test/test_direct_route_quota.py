"""The direct path can reach Google, pace to its quota, and keep the refusal whole.

Three defects met in the Google hole (SBEA654, E31):

1. `call_chat` built an `Authorization` header only for OpenRouter, so Google's own
   route — the one every Google row in the corpus was measured on — had no route in the
   instrument.
2. An error body was cut to 200 characters and the message to 120. The metric sentence,
   the `details[]`, the `quotaValue` and the `RetryInfo` all begin after that cut, so a
   15-request-a-minute refusal and a spent day arrived as the same string.
3. A 429 was retried on the transport's own clock, three attempts inside the same minute
   window, and the wave then deferred the model for the day. The wait the provider names
   was in the body the whole time.

Measured 2026-10-22: 13 calls answered, the 14th refused with
`GenerateRequestsPerMinutePerProjectPerModel-FreeTier`, `quotaValue` 15, and a
`RetryInfo.retryDelay` of **1s on one run and 47s on the next** — the window slides.
"""
import io,json,os,sys,tempfile,urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import agent
import episodes_run
import transport

# The measured refusal, trimmed only in the help link. The shape is Google's
# OpenAI-compatible path: the error is wrapped in a one-element LIST.
QUOTA_BODY = json.dumps([{"error":{"code":429,"message":(
	"You exceeded your current quota, please check your plan and billing details. "
	"* Quota exceeded for metric: generativelanguage.googleapis.com/"
	"generate_content_free_tier_requests, limit: 15, model: gemini-3.5-flash-lite\n"
	"Please retry in 47.745831562s."),
	"status":"RESOURCE_EXHAUSTED",
	"details":[
		{"@type":"type.googleapis.com/google.rpc.QuotaFailure","violations":[{
			"quotaMetric":"generativelanguage.googleapis.com/generate_content_free_tier_requests",
			"quotaId":"GenerateRequestsPerMinutePerProjectPerModel-FreeTier",
			"quotaDimensions":{"location":"global","model":"gemini-3.5-flash-lite"},
			"quotaValue":"15"}]},
		{"@type":"type.googleapis.com/google.rpc.RetryInfo","retryDelay":"47s"}]}}])

GOOGLE_MODEL = {"id":"gemini-3.5-flash-lite","provider":"google","transport":"http",
	"endpoint":"https://example.invalid"}

class FakeTime:
	"""A clock the pacer can spend without the suite spending real minutes."""
	def __init__(self):
		self.now = 1000.0
		self.sleeps = []
	def time(self):
		return self.now
	def sleep(self,seconds):
		self.sleeps.append(seconds)
		self.now += seconds

def _http_error(code,body):
	return urllib.error.HTTPError("https://example.invalid/chat/completions",code,
		"refused",{},io.BytesIO(body.encode()))

def _with_time(fn):
	saved = transport.time
	fake = FakeTime()
	transport.time = fake
	try:
		fn(fake)
	finally:
		transport.time = saved

def _auth_file():
	f = tempfile.NamedTemporaryFile("w",suffix=".json",delete=False)
	json.dump({"openrouter":{"key":"or-key"},"google":{"key":"g-key"}},f)
	f.close()
	return f.name

def _refusal(model,body,retries=1):
	"""Call `call_chat` with a `_post` that always refuses, and return the exception."""
	saved = transport._post
	def refuse(url,payload,headers,timeout):
		raise _http_error(429,body)
	transport._post = refuse
	caught = None
	try:
		transport.call_chat(model,[{"role":"user","content":"hi"}],retries=retries)
	except transport.TransportError as e:
		caught = e
	finally:
		transport._post = saved
	return caught

def test_the_quota_is_read_out_of_the_measured_body():
	q = transport.parse_quota(QUOTA_BODY)
	xtest.equal(q["quota_id"],"GenerateRequestsPerMinutePerProjectPerModel-FreeTier",
		"the quota's own name is what tells a minute limit from a day's")
	xtest.equal(q["quota_value"],"15")
	xtest.equal(q["retry_delay"],47.0,"the wait the provider named")
	xtest.contains("generate_content_free_tier_requests",q["quota_metric"],
		"and the metric it is measured on")

def test_an_object_wrapped_body_parses_too():
	"""The native shape is an object; the compatible path wraps it in a list."""
	body = json.dumps({"error":{"code":429,"message":"quota","details":[
		{"@type":"type.googleapis.com/google.rpc.RetryInfo","retryDelay":"1.5s"}]}})
	xtest.equal(transport.parse_quota(body)["retry_delay"],1.5)

def test_a_body_that_is_not_json_is_not_an_error():
	"""A refusal still has to be a hole with a reason, not a parser traceback."""
	xtest.equal(transport.parse_quota("<html>gateway</html>"),{})

def test_the_whole_body_survives_and_the_message_names_the_quota():
	"""A quota lives past the old 200-character cut, so nothing may cut it."""
	err = _refusal(GOOGLE_MODEL,QUOTA_BODY)
	xtest.true(err is not None,"the refusal must raise rather than return empty")
	xtest.equal(err.body,QUOTA_BODY,"the body is kept whole, not a prefix")
	xtest.equal(err.status,429)
	xtest.equal(err.quota["quota_value"],"15","the structured quota reaches the record")
	xtest.contains("GenerateRequestsPerMinutePerProjectPerModel-FreeTier",str(err),
		"and the message names it, so a log line tells the two quotas apart")
	xtest.contains("retry in 47.0s",str(err))

def test_a_429_waits_the_delay_the_provider_names():
	"""Retrying on our own clock lands inside the same minute window — E31."""
	def check(fake):
		calls = {"n":0}
		saved = transport._post
		def flaky(url,payload,headers,timeout):
			calls["n"] += 1
			if calls["n"] == 1:
				raise _http_error(429,QUOTA_BODY)
			return ({"choices":[{"message":{"content":"ok"},"finish_reason":"stop"}],
				"usage":{"total_tokens":3}},'{"ok":1}')
		transport._post = flaky
		try:
			out = transport.call_chat(GOOGLE_MODEL,[{"role":"user","content":"hi"}],retries=2)
		finally:
			transport._post = saved
		xtest.equal(out["text"],"ok","the retry after the wait is the answer")
		xtest.equal(calls["n"],2)
		xtest.equal(fake.sleeps,[47.5],"the provider's 47s plus a margin, not 1s then 2s")
	_with_time(check)

def test_a_429_without_a_named_delay_keeps_the_body_too():
	body = json.dumps({"error":{"code":429,"message":"slow down"}})
	err = _refusal(GOOGLE_MODEL,body)
	xtest.true(err is not None,"an unparsed refusal is still a refusal")
	xtest.equal(err.body,body,"it is kept whole even when the quota cannot be read")
	xtest.equal(err.quota.get("quota_id"),None,"no quota id was named, and none is invented")
	xtest.equal(err.quota.get("retry_delay"),None,"and no wait either")

def test_google_and_openrouter_get_their_own_keys():
	path = _auth_file()
	saved = transport.AUTH_PATH
	transport.AUTH_PATH = path
	try:
		xtest.equal(transport._auth_headers({"provider":"google"})["Authorization"],
			"Bearer g-key","Google's OpenAI-compatible path takes the API key as a bearer")
		xtest.equal(transport._auth_headers({"provider":"openrouter"})["Authorization"],
			"Bearer or-key")
		xtest.equal(transport._auth_headers({"provider":"zen"}),{},
			"space-bunny is unauthenticated by design")
		xtest.raises(transport.UnseenShape,lambda: transport._auth_headers(
			{"id":"m","provider":"mystery"}),"an unknown provider is loud, not a 401")
	finally:
		transport.AUTH_PATH = saved
		os.unlink(path)

def test_call_chat_sends_the_google_header():
	path = _auth_file()
	saved_path = transport.AUTH_PATH
	saved_post = transport._post
	captured = {}
	def post(url,payload,headers,timeout):
		captured.update(headers)
		return ({"choices":[{"message":{"content":"ok"},"finish_reason":"stop"}],
			"usage":{"total_tokens":3}},'{"ok":1}')
	transport.AUTH_PATH = path
	transport._post = post
	try:
		transport.call_chat(GOOGLE_MODEL,[{"role":"user","content":"hi"}],retries=1)
	finally:
		transport.AUTH_PATH = saved_path
		transport._post = saved_post
		os.unlink(path)
	xtest.equal(captured.get("Authorization"),"Bearer g-key",
		"the direct path must authenticate the provider it was pointed at")

def test_pacing_holds_the_request_budget():
	def check(fake):
		transport._pace_state.clear()
		model = {"id":"flash-lite","rpm":2}
		transport._pace(model,10)
		transport._pace(model,10)
		xtest.equal(fake.sleeps,[],"the first two calls fit")
		transport._pace(model,10)
		xtest.equal(len(fake.sleeps),1,"the third waits for the window to slide")
		xtest.true(fake.sleeps[0] > 59,"a minute window, not a second")
	_with_time(check)
	transport._pace_state.clear()

def test_pacing_holds_the_token_budget():
	def check(fake):
		transport._pace_state.clear()
		model = {"id":"gemma","tpm":100}
		transport._pace(model,60)
		xtest.equal(fake.sleeps,[],"one 60-token call fits the allowance")
		transport._pace(model,60)
		xtest.equal(len(fake.sleeps),1,"the second would exceed 100 input tokens")
	_with_time(check)
	transport._pace_state.clear()

def test_an_unpaced_model_never_sleeps():
	def check(fake):
		transport._pace_state.clear()
		transport._pace({"id":"m"},100000)
		xtest.equal(fake.sleeps,[],"no limit in the registry means no pacing")
	_with_time(check)
	transport._pace_state.clear()

def test_the_budget_comes_from_the_reasoning_flag():
	xtest.equal(episodes_run.budget_for({"reasoning":True}),
		episodes_run.REASONING_MAX_TOKENS)
	xtest.equal(episodes_run.budget_for({"reasoning":False}),
		episodes_run.DEFAULT_MAX_TOKENS)
	xtest.equal(episodes_run.budget_for({}),episodes_run.DEFAULT_MAX_TOKENS,
		"a model that does not declare it gets the old budget")

def test_run_once_uses_the_model_s_budget():
	saved_run = agent.run_episode
	saved_analyse = episodes_run.trace.analyse
	saved_grade = episodes_run.trace.grade
	seen = {}
	def fake_run(model,request,root,max_turns=0,max_tokens=0):
		seen["max_tokens"] = max_tokens
		return {"turns":[],"n_turns":0,"usage":0}
	agent.run_episode = fake_run
	episodes_run.trace.analyse = lambda raw,baseline=None,**kw: {
		"detail":{"n_turns":0,"checker":{"cases":[]}},"gates":{},"grade":"not-measurable"}
	episodes_run.trace.grade = lambda result: ("not-measurable",[])
	try:
		with tempfile.TemporaryDirectory() as run_root:
			with tempfile.TemporaryDirectory() as ep_dir:
				result = episodes_run.run_once({"id":"gemma-4-26b-a4b-it",
					"provider":"google","transport":"http","reasoning":True},
					{"name":"e","dir":ep_dir,"request":"r","baseline":{}},run_root)
	finally:
		agent.run_episode = saved_run
		episodes_run.trace.analyse = saved_analyse
		episodes_run.trace.grade = saved_grade
	xtest.equal(seen["max_tokens"],episodes_run.REASONING_MAX_TOKENS,
		"the runner must not under-budget a thinking model (E23)")
	xtest.equal(result["settings"]["max_tokens"],episodes_run.REASONING_MAX_TOKENS,
		"and the record says which budget it actually used")

def test_the_registry_refuses_a_malformed_limit():
	problems = transport.validate_registry({"m":{"id":"m","provider":"google",
		"transport":"http","endpoint":"https://example.invalid","rpm":0,"tpm":"lots",
		"reasoning":"yes"}})
	text = " ".join(problems)
	xtest.contains("rpm",text)
	xtest.contains("tpm",text)
	xtest.contains("reasoning",text)

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
