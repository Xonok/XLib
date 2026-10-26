"""A day quota is a deferral, not a sleep; a minute quota is a wait.

**E32 (`QB4DYHJ`), measured 2026-10-26.** SBEA654's 429 branch waited the delay the
provider names. That is right for a *minute* quota (1s and 47s measured on 2026-10-22) and
wrong for a *day* quota, which arrives on the same path with the wait to the next midnight
Pacific — **67,682s measured**. The paced wave went to sleep for 21 hours, and because the
branch slept before raising, the refusal body was lost.

**5REVVZE.** The same branch has to classify the refusal, so a queue can defer one model
and carry on with the rest: a day allowance is a deferral, a minute allowance is a wait,
and the upstream provider's own pool is transient. And a `:free` model that answers with a
non-zero cost is being served from the account's paid deposit — a refusal, not a
measurement.

The discriminator is the metric in the body (`quotaId` / `quotaMetric`), with the provider's
text as the fallback for bodies that carry no `details[]`. The delay is only a safety net.
"""
import io,json,os,sys,tempfile,urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import transport

DAY_BODY = json.dumps([{"error":{"code":429,"message":(
	"Quota exceeded for metric: generativelanguage.googleapis.com/"
	"generate_content_free_tier_requests, limit: 20, model: gemini-3-flash-preview. "
	"Please retry in 67880s."),
	"status":"RESOURCE_EXHAUSTED",
	"details":[
		{"@type":"type.googleapis.com/google.rpc.QuotaFailure","violations":[{
			"quotaMetric":"generativelanguage.googleapis.com/generate_content_free_tier_requests",
			"quotaId":"GenerateRequestsPerDayPerProjectPerModel-FreeTier",
			"quotaDimensions":{"location":"global","model":"gemini-3-flash-preview"},
			"quotaValue":"20"}]},
		{"@type":"type.googleapis.com/google.rpc.RetryInfo","retryDelay":"67880s"}]}}])

MINUTE_BODY = json.dumps([{"error":{"code":429,"message":(
	"Quota exceeded for metric: generativelanguage.googleapis.com/"
	"generate_content_free_tier_requests, limit: 15, model: gemini-3.5-flash-lite. "
	"Please retry in 47.745831562s."),
	"status":"RESOURCE_EXHAUSTED",
	"details":[
		{"@type":"type.googleapis.com/google.rpc.QuotaFailure","violations":[{
			"quotaMetric":"generativelanguage.googleapis.com/generate_content_free_tier_requests",
			"quotaId":"GenerateRequestsPerMinutePerProjectPerModel-FreeTier",
			"quotaValue":"15"}]},
		{"@type":"type.googleapis.com/google.rpc.RetryInfo","retryDelay":"47s"}]}}])

GOOGLE_MODEL = {"id":"gemini-3-flash-preview","provider":"google","transport":"http",
	"endpoint":"https://example.invalid"}
OPENROUTER_MODEL = {"id":"poolside/laguna-xs-2.1:free","provider":"openrouter",
	"transport":"http","endpoint":"https://example.invalid"}

class FakeTime:
	"""A clock the transport can spend without the suite spending real minutes."""
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

def _refuse_with(body,calls=None,retries=1,model=GOOGLE_MODEL):
	"""Call `call_chat` with a `_post` that always refuses, and return the exception."""
	saved = transport._post
	def refuse(url,payload,headers,timeout):
		if calls is not None:
			calls["n"] = calls.get("n",0) + 1
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

def test_a_day_quota_is_deferred_and_is_not_slept():
	"""E32's exact failure: 67,682s is the next midnight Pacific, not a minute quota."""
	def check(fake):
		calls = {}
		err = _refuse_with(DAY_BODY,calls=calls,retries=3)
		xtest.true(isinstance(err,transport.Deferred),
			"a day quota must be a Deferred, so a queue can move on")
		xtest.equal(calls["n"],1,"it must not retry into the same spent day")
		xtest.equal(fake.sleeps,[],"and it must not sleep for 18 hours")
		xtest.equal(err.body,DAY_BODY,"the body survives the deferral")
		xtest.equal(err.quota["quota_id"],"GenerateRequestsPerDayPerProjectPerModel-FreeTier")
		xtest.contains("retry in 67880.0s",str(err))
	_with_time(check)

def test_a_long_wait_without_a_metric_is_still_a_deferral():
	"""The metric is the discriminator; the delay is the safety net for a body without one."""
	body = json.dumps({"error":{"code":429,"message":"slow down","details":[
		{"@type":"type.googleapis.com/google.rpc.RetryInfo","retryDelay":"600s"}]}})
	def check(fake):
		err = _refuse_with(body,retries=3)
		xtest.true(isinstance(err,transport.Deferred),
			"a wait of ten minutes is not a minute quota")
		xtest.equal(fake.sleeps,[],"and it must not be slept inside a run")
	_with_time(check)

def test_a_minute_quota_still_waits_the_delay_the_provider_names():
	"""The behaviour SBEA654 got right, and this must not regress."""
	def check(fake):
		calls = {"n":0}
		saved = transport._post
		def flaky(url,payload,headers,timeout):
			calls["n"] += 1
			if calls["n"] == 1:
				raise _http_error(429,MINUTE_BODY)
			return ({"choices":[{"message":{"content":"ok"},"finish_reason":"stop"}],
				"usage":{"total_tokens":3}},'{"ok":1}')
		transport._post = flaky
		try:
			out = transport.call_chat(GOOGLE_MODEL,[{"role":"user","content":"hi"}],retries=2)
		finally:
			transport._post = saved
		xtest.equal(out["text"],"ok","the retry after the wait is the answer")
		xtest.equal(calls["n"],2)
		xtest.equal(fake.sleeps,[47.5],"the provider's 47s plus a margin")
	_with_time(check)

def test_refusal_kind_names_the_four_cases():
	q = transport.parse_quota(DAY_BODY)
	xtest.equal(transport.refusal_kind(q,DAY_BODY), "daily",
		"a PerDay quotaId is the day allowance")
	xtest.equal(transport.refusal_kind(
		{"message":"Rate limit exceeded: free-models-per-day-high-balance."}),
		"daily","OpenRouter names its daily allowance in the message")
	xtest.equal(transport.refusal_kind(
		{"message":"x is temporarily rate-limited upstream"}), "upstream",
		"the upstream provider's pool is transient, not a daily reset")
	xtest.equal(transport.refusal_kind(transport.parse_quota(MINUTE_BODY)), "minute")
	xtest.equal(transport.refusal_kind({}), "unknown",
		"no quota named is unknown, and the transport's own backoff handles it")

def test_an_upstream_pool_refusal_is_not_deferred():
	"""Waiting for a daily reset does not help another provider's pool."""
	body = json.dumps({"error":{"message":"x is temporarily rate-limited upstream"}})
	err = _refuse_with(body,retries=1)
	xtest.true(err is not None,"it is a hole")
	xtest.true(not isinstance(err,transport.Deferred),
		"but it is not a deferral: it clears on its own, and the queue must not park it")

def test_a_free_model_served_from_the_deposit_is_refused():
	"""A `:free` model with a non-zero cost is spent from the deposit, not the free tier."""
	path = _auth_file()
	saved_path,saved_post = transport.AUTH_PATH,transport._post
	def paid(url,payload,headers,timeout):
		return ({"choices":[{"message":{"content":"ok"},"finish_reason":"stop"}],
			"usage":{"total_tokens":3,"cost":0.0012}},'{"ok":1}')
	transport.AUTH_PATH,transport._post = path,paid
	try:
		caught = None
		try:
			transport.call_chat(OPENROUTER_MODEL,[{"role":"user","content":"hi"}],retries=3)
		except transport.TransportError as e:
			caught = e
	finally:
		transport.AUTH_PATH,transport._post = saved_path,saved_post
		os.unlink(path)
	xtest.true(isinstance(caught,transport.Refused),
		"a paid answer is a refusal, not a measurement")
	xtest.contains("deposit",str(caught))

def test_the_deposit_rule_does_not_touch_google_or_a_zero_cost_answer():
	"""Google calls every model paid; its free allowance is metered apart from the price."""
	path = _auth_file()
	saved_path,saved_post = transport.AUTH_PATH,transport._post
	def answer(url,payload,headers,timeout):
		return ({"choices":[{"message":{"content":"ok"},"finish_reason":"stop"}],
			"usage":{"total_tokens":3,"cost":0.0012}},'{"ok":1}')
	transport.AUTH_PATH,transport._post = path,answer
	try:
		out = transport.call_chat(GOOGLE_MODEL,[{"role":"user","content":"hi"}],retries=1)
		xtest.equal(out["text"],"ok","a Google answer with a cost is still a measurement")
		def zero(url,payload,headers,timeout):
			return ({"choices":[{"message":{"content":"ok"},"finish_reason":"stop"}],
				"usage":{"total_tokens":3,"cost":0}},'{"ok":1}')
		transport._post = zero
		out = transport.call_chat(OPENROUTER_MODEL,[{"role":"user","content":"hi"}],retries=1)
		xtest.equal(out["text"],"ok","a free-tier answer reports zero cost")
	finally:
		transport.AUTH_PATH,transport._post = saved_path,saved_post
		os.unlink(path)

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
