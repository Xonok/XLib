"""The daily digest: pull once, pick one item from yesterday, keep today's for tomorrow."""
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
NOW = 1793270400.0
YESTERDAY = NOW - 86400

def _source(**options):
	options.setdefault("feeds", FEEDS)
	options.setdefault("pull_model", PULL)
	options.setdefault("eval_models", EVAL)
	return digest.Digest("digest", options)

def _item(n, title, published, source="A"):
	return {"title": title, "summary": f"summary {n}",
		"url": f"https://a.example/{n}", "source": source, "published": published}

def _candidate(n, title, day, summary="why it matters"):
	return {"title": title, "summary": summary, "url": f"https://a.example/{n}",
		"source": "A", "day": day, "at": NOW}

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
		'{"candidate":%d,"title":"%s","why":"why"}' % (index, title)
		for index, title in entries) + "]}"

def test_a_today_only_pull_keeps_candidates_and_does_not_evaluate():
	call,calls = _call(pull=_pull_json((0, "Today candidate")))
	memory = {}
	conditions = _source().check(NOW, memory, items=[_item(0, "Today story", NOW)], call=call)
	xtest.equal(conditions, [], "today's items are not shown yet")
	xtest.equal(memory["version"], 2, "the daily memory shape is recorded")
	xtest.equal(len(memory["candidates"]), 1, "the candidate is kept")
	xtest.equal(memory["candidates"][0]["day"], digest._day(NOW), "the candidate's day is the publication day")
	xtest.equal([entry[0] for entry in calls], [PULL], "only the cheap pull ran")

def test_the_daily_run_picks_one_item_from_yesterday_and_keeps_today():
	call,calls = _call(pull=_pull_json((0, "Yesterday pick"), (1, "Today candidate")),
		evaluate=_eval_json((0, "Yesterday pick")))
	memory = {}
	items = [_item(0, "Yesterday story", YESTERDAY), _item(1, "Today story", NOW)]
	conditions = _source().check(NOW, memory, items=items, call=call)
	xtest.equal(len(conditions), 1, "exactly one item is published")
	condition = conditions[0]
	xtest.equal(condition.state, event.STATE_INFO, "a daily pick is information")
	xtest.equal(condition.kind, "news", "a daily pick is not a health row")
	xtest.equal(condition.key, f"digest:{digest._day(YESTERDAY)}", "the key is the day")
	xtest.equal(condition.title, "Yesterday pick", "the model's title is the headline")
	xtest.equal(condition.checked, digest._day_end(NOW), "the entry is dated to the day it covers")
	xtest.contains("Pick for", condition.detail, "the detail says which day it is for")
	xtest.contains("https://a.example/0", condition.detail, "the link is in the detail")
	xtest.equal(memory["last_eval_day"], digest._day(YESTERDAY), "the day is remembered")
	xtest.equal([item["day"] for item in memory["candidates"]], [digest._day(NOW)],
		"today's candidate is kept for tomorrow")
	xtest.equal([entry[0] for entry in calls], [PULL, "good"], "the pull then the better model")

def test_exactly_one_item_even_if_the_model_returns_two():
	call,calls = _call(pull=_pull_json((0, "First")),
		evaluate=_eval_json((0, "First"), (0, "Second")))
	memory = {}
	conditions = _source().check(NOW, memory,
		items=[_item(0, "Yesterday story", YESTERDAY)], call=call)
	xtest.equal(len(conditions), 1, "a second item is ignored")
	xtest.equal(conditions[0].title, "First", "the first item is the pick")

def test_a_day_with_no_candidates_publishes_nothing():
	call,calls = _call()
	conditions = _source().check(NOW, {"version": 2}, items=[], call=call)
	xtest.equal(conditions, [], "a quiet day has no entry")
	xtest.equal(calls, [], "no model is called without candidates")

def test_a_same_day_recheck_does_not_evaluate_again():
	memory = {"version": 2, "last_eval_day": digest._day(YESTERDAY),
		"published": [{"title": "Yesterday pick", "why": "why",
			"url": "https://a.example/0", "day": digest._day(YESTERDAY), "at": NOW}]}
	call,calls = _call()
	conditions = _source().check(NOW, memory, items=[], call=call)
	xtest.equal(len(conditions), 1, "the published pick is still returned")
	xtest.equal(conditions[0].title, "Yesterday pick", "the same pick")
	xtest.equal(calls, [], "no second evaluation on the same day")

def test_a_new_day_evaluates_the_new_previous_day():
	memory = {"version": 2, "last_eval_day": digest._day(YESTERDAY),
		"published": [{"title": "Old pick", "why": "why",
			"url": "https://a.example/0", "day": digest._day(YESTERDAY), "at": NOW}],
		"candidates": [_candidate(1, "Held today", digest._day(NOW))],
		"seen": {"https://a.example/1": NOW}}
	call,calls = _call(pull=_pull_json((0, "New yesterday")),
		evaluate=_eval_json((0, "New pick")))
	conditions = _source().check(NOW + 86400, memory,
		items=[_item(2, "New yesterday story", NOW)], call=call)
	xtest.equal(len(conditions), 1, "the new day has one entry")
	xtest.equal(conditions[0].key, f"digest:{digest._day(NOW)}", "the key moves to the new day")
	xtest.equal(conditions[0].title, "New pick", "the new pick is published")
	xtest.equal([entry[0] for entry in calls], [PULL, "good"], "the new day is evaluated")

def test_big_pickle_is_preferred_and_the_fallback_is_used_when_it_fails():
	def evaluate(model, prompt):
		if model == "good":
			raise ValueError("quota exhausted")
		return _eval_json((0, "Fallback pick"))
	memory = {"version": 2, "candidates": [_candidate(0, "Yesterday", digest._day(YESTERDAY))]}
	call,calls = _call(evaluate=evaluate)
	conditions = _source().check(NOW, memory, items=[], call=call)
	xtest.equal(len(conditions), 1, "the fallback still publishes")
	xtest.equal([entry[0] for entry in calls], ["good", "fallback"], "the preferred model is tried first")
	xtest.equal(memory["last_model"], "fallback", "the fallback is named in the memory")

def test_a_malformed_pull_is_a_source_error_and_the_items_are_not_marked_seen():
	call,calls = _call(pull="not json")
	memory = {}
	raised = False
	try:
		_source().check(NOW, memory, items=[_item(0, "Today story", NOW)], call=call)
	except ValueError as exc:
		raised = "JSON" in str(exc)
	xtest.true(raised, "the malformed answer is a source error")
	xtest.equal(memory.get("seen", {}), {}, "the failed pull does not mark the items seen")

def test_a_malformed_evaluation_is_a_source_error():
	memory = {"version": 2, "candidates": [_candidate(0, "Yesterday", digest._day(YESTERDAY))]}
	call,calls = _call(evaluate="not json")
	raised = False
	try:
		_source().check(NOW, memory, items=[], call=call)
	except ValueError as exc:
		raised = "JSON" in str(exc)
	xtest.true(raised, "the malformed evaluation is a source error")

def test_a_model_that_picks_nothing_is_a_source_error():
	memory = {"version": 2, "candidates": [_candidate(0, "Yesterday", digest._day(YESTERDAY))]}
	call,calls = _call(evaluate='{"items":[]}')
	raised = False
	try:
		_source().check(NOW, memory, items=[], call=call)
	except ValueError as exc:
		raised = "did not pick" in str(exc)
	xtest.true(raised, "an empty pick is a source error, not a silent day")

def test_old_weekly_memory_is_reset():
	memory = {"week": "2026-W44", "last_eval": 1000.0,
		"published": [{"title": "Old weekly", "why": "why", "url": "https://a.example/0"}]}
	call,calls = _call()
	conditions = _source().check(NOW, memory, items=[], call=call)
	xtest.equal(conditions, [], "the old weekly condition is not returned")
	xtest.equal(memory.get("version"), 2, "the memory is migrated")
	xtest.equal("week" in memory, False, "the weekly fields are gone")

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
