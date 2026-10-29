"""The site check: what counts as up, degraded and down."""
import os,sys,urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk._ import event
from tools.marduk._.sources import site

class Config:
	def __init__(self, sites=None, site_interval=60.0, site_timeout=5.0):
		self.sites = sites if sites is not None else [
			{"name": "a", "url": "https://a/"},
			{"name": "b", "url": "https://b/"},
		]
		self.site_interval = site_interval
		self.site_timeout = site_timeout

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
	conditions = site.check(Config(), now=1000.0, opener=_opener(200))
	xtest.equal(conditions[0].state, event.STATE_OK, "a 200 is ok")
	xtest.equal(conditions[0].key, "site:a", "the key names the site")
	xtest.contains("HTTP 200", conditions[0].detail, "the status code is in the detail")
	xtest.contains(" ms)", conditions[0].detail, "the elapsed time is in milliseconds")

def test_a_404_is_a_warning():
	conditions = site.check(Config(), now=1000.0, opener=_opener(404))
	xtest.equal(conditions[0].state, event.STATE_WARN, "a 404 is a warning, not a down")

def test_a_503_is_an_alert():
	conditions = site.check(Config(), now=1000.0, opener=_opener(503))
	xtest.equal(conditions[0].state, event.STATE_ALERT, "a 503 is an alert")
	xtest.contains("HTTP 503", conditions[0].detail, "the status code is in the detail")

def test_a_connection_error_is_an_alert():
	conditions = site.check(Config(), now=1000.0, opener=_failing(urllib.error.URLError("refused")))
	xtest.equal(conditions[0].state, event.STATE_ALERT, "a refused connection is down")
	xtest.contains("refused", conditions[0].detail, "the reason is in the detail")

def test_a_timeout_is_an_alert():
	conditions = site.check(Config(), now=1000.0, opener=_failing(TimeoutError("timed out")))
	xtest.equal(conditions[0].state, event.STATE_ALERT, "a timeout is down")
	xtest.contains("timed out", conditions[0].detail, "the reason is in the detail")

def test_every_configured_site_gets_a_condition():
	conditions = site.check(Config(), now=1000.0, opener=_opener(200))
	xtest.equal([condition.key for condition in conditions], ["site:a", "site:b"],
		"one condition per site, in config order")

def test_the_interval_and_stale_after_come_from_the_config():
	xtest.equal(site.interval(Config(site_interval=30.0)), 30.0, "the interval is the config's")
	xtest.equal(site.stale_after(Config(site_interval=30.0)), 180.0,
		"the stale threshold has a floor")
	xtest.equal(site.stale_after(Config(site_interval=120.0)), 360.0,
		"the stale threshold is three intervals")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
