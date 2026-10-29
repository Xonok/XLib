"""The model catalogue: a seeded first run, new models and paid-to-free news."""
import os,sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk._ import event
from tools.marduk._.sources import models

def _source(**options):
	return models.Models("models", options)

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

def test_the_first_run_seeds_without_announcing_the_catalogue():
	memory = {}
	conditions = _check(_source(), 1000.0, memory, ["a/x", "b/y"])
	xtest.equal(conditions, [], "the first run is not news")
	xtest.equal(memory["seeded"], True, "the memory records the seed")
	xtest.equal(memory["seen"], {"a/x": None, "b/y": None}, "the whole catalogue is remembered")

def test_a_model_not_seen_before_is_one_news_item():
	source = _source()
	memory = {"seeded": True, "seen": {"a/x": None}}
	conditions = _check(source, 1000.0, memory, ["a/x", "b/y"])
	xtest.equal(len(conditions), 1, "one item for the new model")
	condition = conditions[0]
	xtest.equal(condition.state, event.STATE_INFO, "a new model is information")
	xtest.equal(condition.kind, "news", "a model is not a health row")
	xtest.equal(condition.key, "models:new:b/y", "the key names the source, the kind and the model")
	xtest.equal(condition.name, "b/y", "the model id is the display name")
	xtest.contains("new model: b/y", condition.title, "the title says what happened")
	xtest.contains("console", condition.detail, "the detail names the catalogue")

def test_a_powerful_new_model_says_so_in_the_title():
	conditions = _check(_source(powerful=["b/"]), 1000.0,
		{"seeded": True, "seen": {}}, ["b/y"])
	xtest.contains("new powerful model: b/y", conditions[0].title, "power is named")

def test_a_powerful_model_that_became_free_is_news():
	conditions = _check(_source(powerful=["mini"]), 1000.0,
		{"seeded": True, "seen": {"acme/mini-x": False}},
		openrouter={"acme/mini-x": {"free": True}})
	xtest.equal(len(conditions), 1, "the transition is one item")
	xtest.equal(conditions[0].key, "models:free:acme/mini-x", "the key names the kind")
	xtest.contains("powerful model now free: acme/mini-x", conditions[0].title, "the title says what happened")
	xtest.contains("openrouter", conditions[0].detail, "the detail names the catalogue")

def test_a_model_that_became_free_but_is_not_powerful_is_quiet():
	conditions = _check(_source(), 1000.0,
		{"seeded": True, "seen": {"acme/x": False}},
		openrouter={"acme/x": {"free": True}})
	xtest.equal(conditions, [], "only a powerful model is worth an item")

def test_free_to_paid_is_quiet_and_updates_the_memory():
	source = _source(powerful=["mini"])
	memory = {"seeded": True, "seen": {"acme/mini-x": True}}
	conditions = _check(source, 1000.0, memory, openrouter={"acme/mini-x": {"free": False}})
	xtest.equal(conditions, [], "free to paid is not news")
	xtest.equal(memory["seen"]["acme/mini-x"], False, "the price is remembered")

def test_a_model_that_disappears_is_not_news_and_its_return_is_not_new():
	source = _source()
	memory = {"seeded": True, "seen": {"a/x": True}}
	xtest.equal(_check(source, 1000.0, memory, []), [], "disappearing is not news")
	xtest.equal(memory["seen"], {"a/x": True}, "the memory keeps it")
	xtest.equal(_check(source, 1060.0, memory, ["a/x"]), [], "its return is not a new model")

def test_a_free_model_is_free_when_either_catalogue_says_so():
	catalogue = models._catalogue(["acme/x"], {"acme/x": {"free": True}},
		{"acme/x": False})
	xtest.equal(catalogue["acme/x"]["free"], True, "free in OpenRouter is enough")
	catalogue = models._catalogue(["acme/y"], {"acme/y": {"free": False}},
		{"acme/y": True})
	xtest.equal(catalogue["acme/y"]["free"], True, "free in the console is enough")

def test_the_same_model_in_both_catalogues_is_one_entry():
	catalogue = models._catalogue(["openrouter/acme/x"], {"acme/x": {"free": True}}, {})
	xtest.equal(list(catalogue), ["acme/x"], "the console's openrouter route is the same model")
	xtest.equal(catalogue["acme/x"]["free"], True, "one free flag")
	xtest.equal(catalogue["acme/x"]["where"], {"console", "openrouter"}, "both routes are named")

def test_the_console_price_comes_from_the_model_database():
	free = models._console_free(
		{"opencode": {"models": {"free-x": {"cost": {"input": 0, "output": 0}},
			"paid-y": {"cost": {"input": 1, "output": 2}}}}},
		["opencode/free-x", "opencode/paid-y", "opencode/unknown"])
	xtest.equal(free, {"opencode/free-x": True, "opencode/paid-y": False},
		"costs become free flags; an unknown model has none")

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

def test_the_openrouter_payload_becomes_free_flags():
	models_by_id = models._openrouter_models({"data": [
		{"id": "a/free", "pricing": {"prompt": "0", "completion": "0"}},
		{"id": "a/paid", "pricing": {"prompt": "1", "completion": "2"}},
		{"id": "a/unknown"},
	]})
	xtest.equal(models_by_id["a/free"]["free"], True, "zero prices are free")
	xtest.equal(models_by_id["a/paid"]["free"], False, "nonzero prices are paid")
	xtest.equal(models_by_id["a/unknown"]["free"], None, "a missing price is unknown")

def test_powerful_must_be_a_list_of_strings():
	for value in ("mini", [1], [""]):
		raised = False
		try:
			models.Models("models", {"powerful": value})
		except ValueError:
			raised = True
		xtest.true(raised, f"powerful={value!r} is refused")

def test_the_interval_and_stale_after_come_from_the_options():
	source = _source(interval_seconds=1800, stale_after_seconds=5400)
	xtest.equal(source.interval(), 1800, "the interval is configured")
	xtest.equal(source.stale_after(), 5400, "stale_after is configured")
	source = _source(interval_seconds=1800)
	xtest.equal(source.stale_after(), 5400, "the default is three intervals")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
