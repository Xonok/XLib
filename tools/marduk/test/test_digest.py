"""The news digest: a cheap pull, a daily evaluation, and one item a week."""
import os,sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk._ import event
from tools.marduk._.sources import digest

FEEDS = [{"name": "A", "url": "https://a.example/rss"}]
PULL = "cheap"
EVAL = ["good", "fallback"]

def _source(**options):
	options.setdefault("feeds", FEEDS)
	options.setdefault("pull_model", PULL)
	options.setdefault("eval_models", EVAL)
	return digest.Digest("digest", options)

def _item(n, title, source="A", published=1000.0):
	return {"title": title, "summary": f"summary {n}",
		"url": f"https://a.example/{n}", "source": source, "published": published}

def _candidate(n, title="A candidate"):
	return {"title": title, "summary": "why it matters", "url": f"https://a.example/{n}",
		"source": "A", "at": 1000.0}

def _call(pull=None, evaluate=None):
	calls = []
	def call(model, prompt, timeout):
		calls.append((model, prompt))
		if model == PULL:
			if pull is None:
				raise ValueError("the pull model was not expected")
			return pull(prompt) if callable(pull) else pull
		if evaluate is None:
			raise ValueError(f"the evaluation model {model} was not expected")
		return evaluate(model, prompt) if callable(evaluate) else evaluate
	return call, calls

def _pull_json(*entries):
	return '{"candidates":[' + ",".join(
		'{"item":%d,"title":"%s","summary":"summary"}' % (index, title)
		for index, title in entries) + "]}"

def _eval_json(*entries):
	return '{"items":[' + ",".join(
		'{"candidate":%d,"title":"%s","why":"why","exceptional":%s}' % (index, title, "true" if exceptional else "false")
		for index, title, exceptional in entries) + "]}"

def test_the_first_pull_sends_new_items_to_the_cheap_model():
	call,calls = _call(pull=_pull_json((0, "The quake")))
	memory = {}
	conditions = _source().check(1000.0, memory, items=[_item(0, "Quake"), _item(1, "Football")], call=call)
	xtest.equal(conditions, [], "the pull is not news")
	xtest.equal(len(calls), 1, "one cheap call for the batch")
	xtest.equal(calls[0][0], PULL, "the cheap model does the pulling")
	xtest.contains("Quake", calls[0][1], "the prompt carries the item")
	xtest.contains("Football", calls[0][1], "the prompt carries every new item")
	xtest.equal(len(memory["candidates"]), 1, "only the model's candidate is kept")
	xtest.equal(memory["candidates"][0]["title"], "The quake", "the model's title is used")
	xtest.equal(len(memory["seen"]), 2, "every new item is marked seen, including the dropped one")

def test_an_item_seen_before_is_not_sent_again():
	memory = {"seen": {"https://a.example/0": 1000.0}}
	call,calls = _call()
	conditions = _source().check(1000.0, memory, items=[_item(0, "Quake")], call=call)
	xtest.equal(conditions, [], "nothing is news")
	xtest.equal(calls, [], "no model call without a new item")

def test_an_old_item_is_marked_seen_without_a_call():
	memory = {}
	call,calls = _call()
	_source(max_age_days=1.0).check(100000.0, memory,
		items=[_item(0, "Old", published=1000.0)], call=call)
	xtest.equal(calls, [], "an old item is not worth a model call")
	xtest.equal("https://a.example/0" in memory["seen"], True, "the old item is not retried")

def test_the_evaluation_waits_for_its_interval():
	memory = {"candidates": [_candidate(0)], "last_eval": 80000.0}
	call,calls = _call(evaluate=_eval_json((0, "The quake", False)))
	conditions = _source().check(90000.0, memory, items=[], call=call)
	xtest.equal(conditions, [], "one item is not due yet")
	xtest.equal(calls, [], "the better model is not called before its interval")

def test_a_due_evaluation_publishes_one_item():
	memory = {"candidates": [_candidate(0)], "last_eval": 0.0}
	call,calls = _call(evaluate=_eval_json((0, "The quake", False)))
	conditions = _source().check(90000.0, memory, items=[], call=call)
	xtest.equal(len(conditions), 1, "one item is published")
	condition = conditions[0]
	xtest.equal(condition.state, event.STATE_INFO, "a digest item is information")
	xtest.equal(condition.kind, "news", "a digest item is not a health row")
	xtest.equal(condition.title, "The quake", "the model's title is the headline")
	xtest.contains("why", condition.detail, "the why is in the detail")
	xtest.contains("https://a.example/0", condition.detail, "the link is in the detail")
	xtest.equal(calls[0][0], "good", "the first evaluation model is preferred")
	xtest.equal(memory["last_model"], "good", "the model that answered is remembered")

def test_big_pickle_is_preferred_and_the_fallback_is_used_when_it_fails():
	def evaluate(model, prompt):
		if model == "good":
			raise ValueError("quota exhausted")
		return _eval_json((0, "The quake", False))
	memory = {"candidates": [_candidate(0)], "last_eval": 0.0}
	call,calls = _call(evaluate=evaluate)
	conditions = _source().check(90000.0, memory, items=[], call=call)
	xtest.equal(len(conditions), 1, "the fallback still publishes")
	xtest.equal([entry[0] for entry in calls], ["good", "fallback"], "the preferred model is tried first")
	xtest.equal(memory["last_model"], "fallback", "the fallback is named in the memory")

def test_a_quiet_evaluation_publishes_nothing():
	memory = {"candidates": [_candidate(0)], "last_eval": 0.0}
	call,calls = _call(evaluate='{"items":[]}')
	conditions = _source().check(90000.0, memory, items=[], call=call)
	xtest.equal(conditions, [], "a quiet week adds no item")
	xtest.equal(memory["last_eval"], 90000.0, "the evaluation is remembered")
	xtest.equal(memory["published"], [], "nothing is published")

def test_a_second_item_needs_to_be_exceptional():
	memory = {"week": digest._week(90000.0), "candidates": [_candidate(0), _candidate(1)],
		"last_eval": 0.0, "published": [{"title": "First", "why": "why",
			"url": "https://a.example/0", "candidate": 0, "exceptional": False, "at": 1000.0}]}
	call,calls = _call(evaluate=_eval_json((0, "First", False), (1, "Second", False)))
	conditions = _source().check(90000.0, memory, items=[], call=call)
	xtest.equal(len(conditions), 1, "a non-exceptional second is not shown")
	memory["last_eval"] = 0.0
	call,calls = _call(evaluate=_eval_json((1, "Second", True)))
	conditions = _source().check(90000.0, memory, items=[], call=call)
	xtest.equal(len(conditions), 2, "an exceptional second is shown")
	xtest.equal(conditions[1].title, "Second", "the second item is the exceptional one")

def test_two_items_on_the_first_evaluation_need_the_second_exceptional():
	memory = {"candidates": [_candidate(0), _candidate(1)], "last_eval": 0.0}
	call,calls = _call(evaluate=_eval_json((0, "First", False), (1, "Second", False)))
	conditions = _source().check(90000.0, memory, items=[], call=call)
	xtest.equal(len(conditions), 1, "only the first is published")
	xtest.equal(memory["published"][0]["title"], "First", "the first item is kept")

def test_a_recheck_returns_the_published_conditions_and_does_not_duplicate_news():
	memory = {"week": digest._week(90000.0), "last_eval": 90000.0,
		"published": [{"title": "The quake", "why": "why", "url": "https://a.example/0",
			"candidate": 0, "exceptional": False, "at": 1000.0}]}
	call,calls = _call()
	conditions = _source().check(90000.0, memory, items=[], call=call)
	xtest.equal(len(conditions), 1, "the published item is still returned")
	xtest.equal(calls, [], "no model call on a recheck")
	xtest.equal(len(memory["published"]), 1, "the item is not published twice")

def test_a_new_week_drops_the_old_keys():
	memory = {"week": "2025-W01", "last_eval": 90000.0,
		"published": [{"title": "Old", "why": "why", "url": "https://a.example/0",
			"candidate": 0, "exceptional": False, "at": 1000.0}]}
	call,calls = _call()
	conditions = _source().check(90000.0, memory, items=[], call=call)
	xtest.equal(conditions, [], "the old week is not returned")
	xtest.equal(memory["published"], [], "the old week's items are cleared")

def test_a_malformed_pull_is_a_source_error_and_the_items_are_not_marked_seen():
	call,calls = _call(pull="not json")
	memory = {}
	raised = False
	try:
		_source().check(1000.0, memory, items=[_item(0, "Quake")], call=call)
	except ValueError as exc:
		raised = "JSON" in str(exc)
	xtest.true(raised, "the malformed answer is a source error")
	xtest.equal(memory.get("seen", {}), {}, "the failed pull does not mark the items seen")

def test_a_malformed_evaluation_is_a_source_error():
	memory = {"candidates": [_candidate(0)], "last_eval": 0.0}
	call,calls = _call(evaluate="not json")
	raised = False
	try:
		_source().check(90000.0, memory, items=[], call=call)
	except ValueError as exc:
		raised = "JSON" in str(exc)
	xtest.true(raised, "the malformed evaluation is a source error")

def test_the_pull_model_defaults_to_openrouter_nemotron_ultra():
	source = digest.Digest("digest", {"feeds": FEEDS})
	xtest.equal(source.pull_model, "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
		"the cheap pool is OpenRouter's free nemotron")

def test_rss_and_atom_are_both_read():
	rss = """<rss><channel><item><title>Quake</title><link>https://a.example/rss-1</link>
		<description>Big</description><pubDate>Thu, 29 Oct 2026 10:00:00 GMT</pubDate>
		</item></channel></rss>"""
	atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Vote</title>
		<link rel="alternate" href="https://a.example/atom-1"/><summary>Close</summary>
		<published>2026-10-29T10:00:00Z</published></entry></feed>"""
	rss_items = digest._parse(rss, "A")
	atom_items = digest._parse(atom, "B")
	xtest.equal(rss_items[0]["title"], "Quake", "an RSS title is read")
	xtest.equal(rss_items[0]["url"], "https://a.example/rss-1", "an RSS link is read")
	xtest.equal(atom_items[0]["title"], "Vote", "an Atom title is read")
	xtest.equal(atom_items[0]["url"], "https://a.example/atom-1", "an Atom href is read")
	xtest.true(atom_items[0]["published"] > 0, "an Atom date is read")

def test_feeds_are_required_and_validated():
	xtest.raises(ValueError, lambda: digest.Digest("digest", {}),
		"a digest needs feeds")
	xtest.raises(ValueError, lambda: digest.Digest("digest", {"feeds": [{"name": "A"}]}),
		"a feed needs a url")
	xtest.raises(ValueError, lambda: digest.Digest("digest", {"feeds": FEEDS, "eval_models": []}),
		"at least one evaluation model is needed")
	xtest.raises(ValueError, lambda: digest.Digest("digest", {"feeds": FEEDS, "pull_model": ""}),
		"the pull model cannot be empty")
