"""The free-models source: lists currently free models as a free section."""
import os,sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk._ import event
from tools.marduk._.sources import freemodels

def _source(**options):
	return freemodels.FreeModels("free-go", options)

def _console(ids):
	return lambda: ids

def _openrouter(catalogue):
	return lambda: catalogue

def _prices(data):
	return lambda: data

def _check(source, now, memory, console=(), openrouter=None, prices=None):
	return source.check(now, memory,
		console=_console(list(console)),
		openrouter=_openrouter({} if openrouter is None else openrouter),
		prices=_prices({} if prices is None else prices))

def test_a_free_matching_model_becomes_a_free_section_row():
	conditions = _check(_source(prefixes=["opencode-go/"]), 1000.0, {},
		console=["opencode-go/beam-free", "opencode-go/paid-x"],
		prices={"opencode-go": {"models": {
			"beam-free": {"cost": {"input": 0, "output": 0}},
			"paid-x": {"cost": {"input": 1, "output": 2}}}}})
	xtest.equal(len(conditions), 1, "one free matching model")
	condition = conditions[0]
	xtest.equal(condition.kind, "free", "it is a free-section row, not health or news")
	xtest.equal(condition.state, event.STATE_OK, "a free model is ok")
	xtest.equal(condition.name, "opencode-go/beam-free", "the model id is the display name")
	xtest.equal(condition.key, "free-go:opencode-go/beam-free", "the key names the source and the model")

def test_a_paid_matching_model_produces_no_row():
	conditions = _check(_source(prefixes=["opencode-go/"]), 1000.0, {},
		console=["opencode-go/paid-x"],
		prices={"opencode-go": {"models": {"paid-x": {"cost": {"input": 1, "output": 2}}}}})
	xtest.equal(conditions, [], "paid models are not listed")

def test_a_free_model_with_the_wrong_prefix_produces_no_row():
	conditions = _check(_source(prefixes=["opencode-go/"]), 1000.0, {},
		console=["google/gemma-4-26b-a4b-it"],
		prices={"google": {"models": {"gemma-4-26b-a4b-it": {"cost": {"input": 0, "output": 0}}}}})
	xtest.equal(conditions, [], "a model outside the prefix is not listed")

def test_an_empty_prefix_list_lists_every_free_model():
	conditions = _check(_source(), 1000.0, {},
		console=["opencode-go/beam-free", "google/gemma-4-26b-a4b-it"],
		prices={"opencode-go": {"models": {"beam-free": {"cost": {"input": 0, "output": 0}}}},
			"google": {"models": {"gemma-4-26b-a4b-it": {"cost": {"input": 0, "output": 0}}}}})
	xtest.equal(len(conditions), 2, "every free model is listed")

def test_a_failed_console_command_is_a_source_error():
	def console():
		raise ValueError("opencode models exited 1: not logged in")
	raised = False
	try:
		_source().check(1000.0, {}, console=console, openrouter=_openrouter({}), prices=_prices({}))
	except ValueError as exc:
		raised = "not logged in" in str(exc)
	xtest.true(raised, "the failure reaches the scheduler as a source error")

def test_the_prices_are_refreshed_on_their_own_interval():
	calls = []
	source = _source(prices_refresh_seconds=3600)
	def prices():
		calls.append(1)
		return {}
	memory = {}
	source.check(1000.0, memory, console=_console([]), openrouter=_openrouter({}), prices=prices)
	source.check(2000.0, memory, console=_console([]), openrouter=_openrouter({}), prices=prices)
	xtest.equal(len(calls), 1, "a second check inside the window reuses the prices")
	source.check(5000.0, memory, console=_console([]), openrouter=_openrouter({}), prices=prices)
	xtest.equal(len(calls), 2, "the window expiring fetches them again")

def test_prefixes_must_be_a_list_of_strings():
	for value in ("mini", [1], [""]):
		raised = False
		try:
			freemodels.FreeModels("free-go", {"prefixes": value})
		except ValueError:
			raised = True
		xtest.true(raised, f"prefixes={value!r} is refused")

def test_the_interval_and_stale_after_come_from_the_options():
	source = _source(interval_seconds=1800, stale_after_seconds=5400)
	xtest.equal(source.interval(), 1800, "the interval is configured")
	xtest.equal(source.stale_after(), 5400, "stale_after is configured")
	source = _source(interval_seconds=1800)
	xtest.equal(source.stale_after(), 5400, "the default is three intervals")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
