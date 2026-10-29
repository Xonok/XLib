"""The transition rules: what becomes news and what stays quiet."""
import os,sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk._ import event

def _condition(state, key="site:a", name="a", checked=1000.0):
	return event.Condition("site", key, "health", name, state, f"{name} is {state}", checked=checked)

def test_a_first_ok_condition_is_not_news():
	xtest.equal(event.transition(None, _condition(event.STATE_OK)), None,
		"a healthy first check is not an event")

def test_a_first_alert_is_news():
	record = event.transition(None, _condition(event.STATE_ALERT))
	xtest.true(record is not None, "an alert on first sight is news")
	xtest.equal(record["state"], event.STATE_ALERT, "the state is carried")
	xtest.equal(record["title"], "a is alert", "the condition's title is used")
	xtest.true(not record["recovered"], "an alert is not a recovery")

def test_an_unchanged_alert_is_not_news():
	old = _condition(event.STATE_ALERT)
	new = _condition(event.STATE_ALERT)
	xtest.equal(event.transition(old, new), None, "the same state twice is not news")

def test_a_recovery_is_news():
	record = event.transition(_condition(event.STATE_ALERT), _condition(event.STATE_OK))
	xtest.true(record is not None, "a recovery is news")
	xtest.true(record["recovered"], "it is marked as a recovery")
	xtest.equal(record["title"], "a recovered", "the title says recovered")
	xtest.equal(record["state"], event.STATE_OK, "the state is ok")

def test_a_warn_to_alert_is_news():
	record = event.transition(_condition(event.STATE_WARN), _condition(event.STATE_ALERT))
	xtest.true(record is not None, "a change between two non-ok states is news")
	xtest.equal(record["state"], event.STATE_ALERT, "the new state is carried")

def test_the_condition_roundtrips():
	original = _condition(event.STATE_WARN, checked=1234.5)
	copy = event.Condition.from_dict(original.to_dict())
	xtest.equal(copy.to_dict(), original.to_dict(), "the record survives a roundtrip")

def test_replace_is_optional_and_roundtrips():
	plain = _condition(event.STATE_WARN)
	xtest.equal(plain.replace, False, "a condition is not replacing by default")
	replacing = event.Condition("digest", "digest:a", "news", "World news",
		event.STATE_INFO, checked=1234.5, replace=True)
	copy = event.Condition.from_dict(replacing.to_dict())
	xtest.equal(copy.replace, True, "the replace flag survives a roundtrip")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
