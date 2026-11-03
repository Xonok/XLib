"""The daily digest: pull once, filter yesterday's candidates, keep what passes."""
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
RULES = ["Keep structural change.", "Drop routine accidents."]
NOW = 1793270400.0
YESTERDAY = NOW - 86400

def _source(**options):
	options.setdefault("feeds", FEEDS)
	options.setdefault("pull_model", PULL)
	options.setdefault("eval_models", EVAL)
	options.setdefault("rules", RULES)
	return digest.Digest("digest", options)

def _item(n, title, published, source="A"):
	return {"title": title, "summary": f"summary {n}",
		"url": f"https://a.example/{n}", "source": source, "published": published}

def _candidate(n, title, day, summary="why it matters"):
	return {"title": title, "summary": summary, "url": f"https://a.example/{n}",
		"source": "A", "day": day, "at": NOW}

def _call(pull=None, keep=None):
	calls = []
	def call(model, prompt, timeout):
		calls.append((model, prompt))
		if model == PULL:
			if pull is None:
				raise ValueError("the pull model was not expected")
			return pull(prompt) if callable(pull) else pull
		if keep is None:
			raise ValueError(f"the filter model {model} was not expected")
		return keep(model, prompt) if callable(keep) else keep
	return call, calls

def _pull_json(*entries):
	return '{"candidates":[' + ",".join(
		'{"item":%d,"title":"%s","summary":"summary"}' % (index, title)
		for index, title in entries) + "]}"

def _keep_json(*entries):
	return '{"keep":[' + ",".join(
		'{"candidate":%d,"why":"%s"}' % (index, why)
		for index, why in entries) + "]}"

def test_a_today_only_pull_keeps_candidates_and_does_not_filter():
	call,calls = _call(pull=_pull_json((0, "Today candidate")))
	memory = {}
	conditions = _source().check(NOW, memory, items=[_item(0, "Today story", NOW)], call=call)
	xtest.equal(len(conditions), 1, "a day with no candidates returns a clearing condition")
	xtest.equal(conditions[0].state, event.STATE_OK, "the clearing condition is not news")
	xtest.true(conditions[0].replace, "it asks the store to replace the source's news")
	xtest.equal(memory["version"], 2, "the daily memory shape is recorded")
	xtest.equal(len(memory["candidates"]), 1, "the candidate is kept")
	xtest.equal(memory["candidates"][0]["day"], digest._day(NOW), "the candidate's day is the publication day")
	xtest.true(memory.get("last_eval_day") != digest._day(YESTERDAY),
		"a day with no candidates is not marked done")
	xtest.equal([entry[0] for entry in calls], [PULL], "only the cheap pull ran")

def test_the_daily_run_publishes_every_kept_item():
	call,calls = _call(pull=_pull_json((0, "First story"), (1, "Second story"), (2, "Today story")),
		keep=_keep_json((1, "passes the scale rule"), (0, "passes the change rule")))
	memory = {}
	items = [_item(0, "First story", YESTERDAY), _item(1, "Second story", YESTERDAY),
		_item(2, "Today story", NOW)]
	conditions = _source().check(NOW, memory, items=items, call=call)
	xtest.equal(len(conditions), 2, "every kept item is published; there is no quota")
	xtest.equal(conditions[0].key, f"digest:{digest._day(YESTERDAY)}:0", "the first kept item is keyed")
	xtest.equal(conditions[1].key, f"digest:{digest._day(YESTERDAY)}:1", "the second kept item is keyed")
	xtest.equal(conditions[0].title, "First story", "the candidate order is kept")
	xtest.equal(conditions[1].title, "Second story", "the second title is kept")
	xtest.contains("Kept for", conditions[0].detail, "the detail says which day it is for")
	xtest.contains("https://a.example/0", conditions[0].detail, "the link is in the detail")
	xtest.equal(memory["last_eval_day"], digest._day(YESTERDAY), "the day is remembered")
	xtest.equal(memory["last_model"], "good", "the model that filtered is remembered")
	xtest.equal([item["day"] for item in memory["candidates"]], [digest._day(NOW)],
		"today's candidate is kept for tomorrow")
	xtest.equal([entry[0] for entry in calls], [PULL, "good"], "the pull then the better model")

def test_a_filter_can_keep_nothing():
	call,calls = _call(pull=_pull_json((0, "Noise")), keep=_keep_json())
	memory = {}
	conditions = _source().check(NOW, memory,
		items=[_item(0, "Noise story", YESTERDAY)], call=call)
	xtest.equal(len(conditions), 1, "a day that keeps nothing returns one clearing condition")
	xtest.equal(conditions[0].key, f"digest:{digest._day(YESTERDAY)}", "the clearing key is the day")
	xtest.equal(conditions[0].state, event.STATE_OK, "nothing kept is not an error")
	xtest.true(conditions[0].replace, "it clears the previous day's news")
	xtest.equal(memory["published"], [], "no item is published")
	xtest.equal(memory["last_eval_day"], digest._day(YESTERDAY), "the day is still marked done")
	xtest.equal([entry[0] for entry in calls], [PULL, "good"], "the filter ran once")

def test_a_day_with_no_candidates_clears_the_old_published_list_without_filtering():
	memory = {"version": 2, "last_eval_day": digest._day(YESTERDAY),
		"published": [{"title": "Old item", "why": "why", "url": "https://a.example/0",
			"day": digest._day(YESTERDAY), "at": NOW}]}
	call,calls = _call()
	conditions = _source().check(NOW + 86400, memory, items=[], call=call)
	xtest.equal(len(conditions), 1, "the new day returns a clearing condition")
	xtest.equal(conditions[0].key, f"digest:{digest._day(NOW)}", "the clearing key is the new day")
	xtest.equal(memory["published"], [], "the old day's items are gone")
	xtest.true(memory.get("last_eval_day") != digest._day(NOW),
		"a day with no candidates is not marked done")
	xtest.equal(calls, [], "no model is called without candidates")

def test_a_same_day_recheck_does_not_filter_again():
	memory = {"version": 2, "last_eval_day": digest._day(YESTERDAY),
		"published": [{"title": "Yesterday item", "why": "why",
			"url": "https://a.example/0", "day": digest._day(YESTERDAY), "at": NOW}]}
	call,calls = _call()
	conditions = _source().check(NOW, memory, items=[], call=call)
	xtest.equal(len(conditions), 1, "the published item is still returned")
	xtest.equal(conditions[0].title, "Yesterday item", "the same item")
	xtest.equal(calls, [], "no second filter on the same day")

def test_a_new_day_filters_the_new_previous_day():
	memory = {"version": 2, "last_eval_day": digest._day(YESTERDAY),
		"published": [{"title": "Old item", "why": "why",
			"url": "https://a.example/0", "day": digest._day(YESTERDAY), "at": NOW}],
		"candidates": [_candidate(1, "Held today", digest._day(NOW))],
		"seen": {"https://a.example/1": NOW}}
	call,calls = _call(pull=_pull_json((0, "New yesterday")),
		keep=_keep_json((1, "passes the rule")))
	conditions = _source().check(NOW + 86400, memory,
		items=[_item(2, "New yesterday story", NOW)], call=call)
	xtest.equal(len(conditions), 1, "the new day has one entry")
	xtest.equal(conditions[0].key, f"digest:{digest._day(NOW)}", "the key moves to the new day")
	xtest.equal(conditions[0].title, "New yesterday", "the new pick is published")
	xtest.equal([entry[0] for entry in calls], [PULL, "good"], "the new day is filtered")

def test_big_pickle_is_preferred_and_the_fallback_is_used_when_it_fails():
	def keep(model, prompt):
		if model == "good":
			raise ValueError("quota exhausted")
		return _keep_json((0, "passes the rule"))
	memory = {"version": 2, "candidates": [_candidate(0, "Yesterday", digest._day(YESTERDAY))]}
	call,calls = _call(keep=keep)
	conditions = _source().check(NOW, memory, items=[], call=call)
	xtest.equal(len(conditions), 1, "the fallback still filters")
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

def test_a_malformed_filter_is_a_source_error():
	memory = {"version": 2, "candidates": [_candidate(0, "Yesterday", digest._day(YESTERDAY))]}
	call,calls = _call(keep="not json")
	raised = False
	try:
		_source().check(NOW, memory, items=[], call=call)
	except ValueError as exc:
		raised = "JSON" in str(exc)
	xtest.true(raised, "the malformed filter is a source error")

def test_a_filter_that_keeps_no_valid_candidate_is_a_source_error():
	memory = {"version": 2, "candidates": [_candidate(0, "Yesterday", digest._day(YESTERDAY))]}
	call,calls = _call(keep='{"keep":[{"candidate":99,"why":"not a candidate"}]}')
	raised = False
	try:
		_source().check(NOW, memory, items=[], call=call)
	except ValueError as exc:
		raised = "no valid candidate" in str(exc)
	xtest.true(raised, "an answer that names only unknown candidates is an error")

def test_a_filter_that_omits_items_drops_them():
	memory = {"version": 2, "candidates": [
		_candidate(0, "First", digest._day(YESTERDAY)),
		_candidate(1, "Second", digest._day(YESTERDAY))]}
	call,calls = _call(keep=_keep_json((0, "passes the rule")))
	conditions = _source().check(NOW, memory, items=[], call=call)
	xtest.equal(len(conditions), 1, "an omitted candidate is not kept")
	xtest.equal(conditions[0].title, "First", "the named candidate is kept")

def test_accept_all_publishes_every_candidate_without_a_model():
	memory = {"version": 2, "candidates": [
		_candidate(0, "First", digest._day(YESTERDAY)),
		_candidate(1, "Second", digest._day(YESTERDAY))]}
	call,calls = _call()
	conditions = _source(accept_all=True).check(NOW, memory, items=[], call=call)
	xtest.equal(len(conditions), 2, "every candidate is published")
	xtest.equal(memory["last_model"], "accept-all", "the bypass is named in the memory")
	xtest.equal(calls, [], "the bypass calls no model")

def test_old_weekly_memory_is_reset():
	memory = {"week": "2026-W44", "last_eval": 1000.0,
		"published": [{"title": "Old weekly", "why": "why", "url": "https://a.example/0"}]}
	call,calls = _call()
	conditions = _source().check(NOW, memory, items=[], call=call)
	xtest.equal(len(conditions), 1, "the old weekly condition is replaced by a clearing condition")
	xtest.equal(conditions[0].state, event.STATE_OK, "nothing is published from the old memory")
	xtest.equal(memory.get("version"), 2, "the memory is migrated")
	xtest.equal("week" in memory, False, "the weekly fields are gone")

def test_the_pull_model_defaults_to_openrouter_nemotron_ultra():
	source = digest.Digest("digest", {"feeds": FEEDS})
	xtest.equal(source.pull_model, "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
		"the cheap pool is OpenRouter's free nemotron")

def test_the_default_rules_are_generic():
	source = digest.Digest("digest", {"feeds": FEEDS})
	xtest.equal(source.rules, list(digest.DEFAULT_RULES), "the generic brief is the default")

def test_rules_are_validated():
	xtest.raises(ValueError, lambda: digest.Digest("digest", {"feeds": FEEDS, "rules": []}),
		"at least one rule is needed")
	xtest.raises(ValueError, lambda: digest.Digest("digest", {"feeds": FEEDS, "rules": ["", "x"]}),
		"a rule cannot be empty")

def test_the_filter_prompt_carries_the_reader_rules_and_allows_nothing():
	prompt = digest._filter_prompt([_candidate(0, "A story", "2026-10-29")], RULES)
	xtest.contains(RULES[0], prompt, "the reader's rule is in the prompt")
	xtest.contains("empty keep list is a valid answer", prompt, "nothing is a valid answer")
	xtest.contains("no quota", prompt, "there is no quota")
	xtest.contains("do not publish duplicates", prompt, "near-duplicates are merged")

def test_the_pull_prompt_does_not_drop_topics():
	prompt = digest._pull_prompt([_item(0, "A story", NOW)])
	xtest.contains("Keep every item", prompt, "the pull keeps every item")
	xtest.not_contains("drop sport", prompt, "the pull does not make editorial decisions")

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

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
