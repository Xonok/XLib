"""The site check: what counts as up, degraded and down."""
import os,sys,urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk._ import event
from tools.marduk._.sources import site

def _source(**options):
	options.setdefault("targets", [
		{"name": "a", "url": "https://a/"},
		{"name": "b", "url": "https://b/"},
	])
	return site.Site("site", options)

class Response:
	def __init__(self, status):
		self.status = status
	def __enter__(self):
		return self
	def __exit__(self, *args):
		return False

def _opener(status):
	def open_url(url, timeout=None):
		return Response(status)
	return open_url

def _failing(exc):
	def open_url(url, timeout=None):
		raise exc
	return open_url

def test_a_200_is_ok():
	conditions = _source().check(1000.0, _opener(200))
	xtest.equal(conditions[0].state, event.STATE_OK, "a 200 is ok")
	xtest.equal(conditions[0].key, "site:a", "the key names the source and the site")
	xtest.contains("HTTP 200", conditions[0].detail, "the status code is in the detail")
	xtest.contains(" ms)", conditions[0].detail, "the elapsed time is in milliseconds")

def test_a_404_is_a_warning():
	conditions = _source().check(1000.0, _opener(404))
	xtest.equal(conditions[0].state, event.STATE_WARN, "a 404 is a warning, not a down")

def test_a_503_is_an_alert():
	conditions = _source().check(1000.0, _opener(503))
	xtest.equal(conditions[0].state, event.STATE_ALERT, "a 503 is an alert")
	xtest.contains("HTTP 503", conditions[0].detail, "the status code is in the detail")

def test_a_connection_error_is_an_alert():
	conditions = _source().check(1000.0, _failing(urllib.error.URLError("refused")))
	xtest.equal(conditions[0].state, event.STATE_ALERT, "a refused connection is down")
	xtest.contains("refused", conditions[0].detail, "the reason is in the detail")

def test_a_timeout_is_an_alert():
	conditions = _source().check(1000.0, _failing(TimeoutError("timed out")))
	xtest.equal(conditions[0].state, event.STATE_ALERT, "a timeout is down")
	xtest.contains("timed out", conditions[0].detail, "the reason is in the detail")

def test_every_configured_target_gets_a_condition():
	conditions = _source().check(1000.0, _opener(200))
	xtest.equal([condition.key for condition in conditions], ["site:a", "site:b"],
		"one condition per target, in config order")

def test_a_string_target_gets_an_https_url():
	source = _source(targets=["a"])
	xtest.equal(source.targets[0]["url"], "https://a/", "a name is a host on HTTPS")

def test_the_interval_and_stale_after_come_from_the_options():
	xtest.equal(_source(interval_seconds=30.0).interval(), 30.0, "the interval is the option")
	xtest.equal(_source(interval_seconds=30.0).stale_after(), 180.0,
		"the stale threshold has a floor")
	xtest.equal(_source(interval_seconds=120.0).stale_after(), 360.0,
		"the stale threshold is three intervals")
	xtest.equal(_source(interval_seconds=120.0, stale_after_seconds=90.0).stale_after(), 90.0,
		"an explicit stale threshold wins")

def test_keys_declare_the_health_rows_before_the_first_check():
	xtest.equal(_source().keys(), [("site:a", "a"), ("site:b", "b")],
		"the declared keys carry the source id")

def test_a_second_instance_gets_its_own_keys():
	source = site.Site("internal", {"targets": [{"name": "a"}]})
	xtest.equal(source.keys(), [("internal:a", "a")], "the id prefixes the key")

def test_targets_must_be_a_list():
	raised = False
	try:
		site.Site("site", {"targets": 5})
	except ValueError:
		raised = True
	xtest.true(raised, "a malformed target list is a config error")

def test_a_target_needs_a_name_or_a_url():
	raised = False
	try:
		site.Site("site", {"targets": [{}]})
	except ValueError:
		raised = True
	xtest.true(raised, "an empty target is a config error")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
