"""The state file and the fold from one check into conditions and news."""
import os,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk._ import event,store

def _condition(state, key="site:a", name="a", checked=1000.0):
	return event.Condition("site", key, "health", name, state, f"{name} is {state}", checked=checked)

def _store(folder):
	state = store.Store(os.path.join(folder, "state.json"))
	state.load()
	return state

def test_a_new_alert_is_stored_and_becomes_news():
	with tempfile.TemporaryDirectory() as folder:
		state = _store(folder)
		state.apply("site", [_condition(event.STATE_ALERT)], 1000.0)
		xtest.equal(len(state.conditions), 1, "the condition is stored")
		xtest.equal(len(state.news), 1, "the alert is news")
		xtest.equal(state.news[0]["state"], event.STATE_ALERT, "the news carries the state")

def test_an_unchanged_check_keeps_since_and_adds_no_news():
	with tempfile.TemporaryDirectory() as folder:
		state = _store(folder)
		state.apply("site", [_condition(event.STATE_ALERT, checked=1000.0)], 1000.0)
		first = state.conditions["site:a"].since
		state.apply("site", [_condition(event.STATE_ALERT, checked=1060.0)], 1060.0)
		xtest.equal(len(state.news), 1, "the second identical check is quiet")
		xtest.equal(state.conditions["site:a"].since, first,
			"since is the start of the state, not the last check")
		xtest.equal(state.conditions["site:a"].checked, 1060.0, "checked moves with the check")

def test_a_recovery_updates_the_state_and_adds_news():
	with tempfile.TemporaryDirectory() as folder:
		state = _store(folder)
		state.apply("site", [_condition(event.STATE_ALERT, checked=1000.0)], 1000.0)
		state.apply("site", [_condition(event.STATE_OK, checked=1060.0)], 1060.0)
		xtest.equal(len(state.news), 2, "the recovery is news too")
		xtest.true(state.news[0]["recovered"], "newest first, and the recovery is newest")
		xtest.equal(state.conditions["site:a"].state, event.STATE_OK, "the condition is ok again")

def test_a_key_the_source_no_longer_returns_is_dropped():
	with tempfile.TemporaryDirectory() as folder:
		state = _store(folder)
		state.apply("site", [_condition(event.STATE_OK)], 1000.0)
		state.apply("site", [], 1060.0)
		xtest.equal(len(state.conditions), 0, "a key the source stopped returning is gone")

def test_a_failed_source_keeps_its_conditions():
	with tempfile.TemporaryDirectory() as folder:
		state = _store(folder)
		state.apply("site", [_condition(event.STATE_ALERT)], 1000.0)
		state.fail("site", 1060.0, "timeout")
		xtest.equal(len(state.conditions), 1, "the last condition is kept")
		xtest.equal(state.sources["site"]["last_error"], "timeout", "the error is recorded")

def test_the_state_roundtrips_through_the_file():
	with tempfile.TemporaryDirectory() as folder:
		state = _store(folder)
		state.apply("site", [_condition(event.STATE_ALERT, checked=1000.0)], 1000.0)
		state.save()
		again = _store(folder)
		xtest.equal(len(again.conditions), 1, "the condition is read back")
		xtest.equal(again.conditions["site:a"].state, event.STATE_ALERT, "the state is read back")
		xtest.equal(len(again.news), 1, "the news is read back")

def test_a_corrupt_state_is_reported_not_raised():
	with tempfile.TemporaryDirectory() as folder:
		path = os.path.join(folder, "state.json")
		with open(path, "w", encoding="utf-8") as file:
			file.write("not json")
		state = store.Store(path)
		state.load()
		xtest.true(state.load_error, "the corrupt file is reported")
		xtest.equal(len(state.conditions), 0, "the store starts empty")

def test_news_ages_out():
	with tempfile.TemporaryDirectory() as folder:
		state = _store(folder)
		state.retention_seconds = 60
		state.apply("site", [_condition(event.STATE_ALERT, checked=1000.0)], 1000.0)
		state.apply("site", [_condition(event.STATE_ALERT, checked=1100.0)], 1100.0)
		xtest.equal(len(state.news), 0, "an event older than the retention is gone")

def test_source_state_reports_waiting_stale_error_ok():
	xtest.equal(store.source_state(None, 1000.0, 60.0), "waiting", "no record is waiting")
	xtest.equal(store.source_state({"last_run": 1000.0}, 1000.0, 60.0), "stale",
		"a run that never succeeded is stale")
	xtest.equal(store.source_state({"last_run": 1000.0, "last_ok": 990.0, "last_error": "boom"},
		1000.0, 60.0), "error", "a failed run is an error")
	xtest.equal(store.source_state({"last_run": 1000.0, "last_ok": 990.0, "last_error": ""},
		1000.0, 60.0), "ok", "a recent success is ok")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
