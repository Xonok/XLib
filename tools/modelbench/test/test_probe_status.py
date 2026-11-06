"""What a probe observed, in one word, without pretending it is a verdict.

The old probe called everything it did not recognise "upstream/other", and the registry
carried that as `gating` — which is how Big Pickle was reported dead on a day a real
episode graded it `autonomy` 6/6. The fix is not a better guess about liveness; it is to
keep the provider's own words and classify only the shapes that have a name.
"""
import sys,os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest,transport

def _deferred(message="quota"):
	return transport.Deferred(message,status=429,quota={"quota_id":"FreeTier",
		"quota_value":"20","retry_delay":67880})

def test_a_day_quota_is_a_quota_not_a_dead_model():
	xtest.equal(transport.probe_state(_deferred()),"quota")

def test_a_geo_block_is_named():
	xtest.equal(transport.probe_state(
		transport.TransportError("This model is not available in your country")),"geo")

def test_a_harness_gate_is_named():
	xtest.equal(transport.probe_state(
		transport.TransportError("only available on agentic harnesses")),"harness-only")

def test_capacity_is_not_a_rate_limit():
	xtest.equal(transport.probe_state(transport.TransportError(
		"zai: HTTP 429 The service may be temporarily overloaded, please try again later")),
		"capacity","a 429 with an overload message is the provider's capacity, not our quota")
	xtest.equal(transport.probe_state(transport.TransportError(
		"google: HTTP 503 high demand")),"capacity")

def test_auth_is_named_before_rate_limit():
	xtest.equal(transport.probe_state(
		transport.TransportError("openrouter: HTTP 401 unauthorized")),"auth")

def test_a_timeout_is_a_timeout():
	xtest.equal(transport.probe_state(
		transport.TransportError("nim: The read operation timed out")),"timeout")

def test_an_unrecognised_failure_says_error_and_keeps_the_detail():
	xtest.equal(transport.probe_state(
		transport.TransportError("something new happened")),"error")

def test_the_probe_returns_data_not_a_printed_verdict():
	saved = transport._probe_one
	transport._probe_one = lambda model: {"state":"open","detail":"3 tokens","quota":{}}
	try:
		rows = transport.probe({"m":{"id":"x","provider":"nim","transport":"http",
			"rpm":40,"aggregate":"nim","aggregate_rpm":35,"reasoning":True}})
	finally:
		transport._probe_one = saved
	row = rows[0]
	xtest.equal(row["name"],"m")
	xtest.equal(row["state"],"open")
	xtest.equal(row["rpm"],40)
	xtest.equal(row["aggregate_rpm"],35)
	xtest.equal(row["detail"],"3 tokens")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
