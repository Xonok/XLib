"""The player feed: a seed, a first join, a return and a quiet idle day."""
import json,os,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk._ import event
from tools.marduk._.sources import players

DAY = 86400

def _write(folder, people):
	os.makedirs(os.path.join(folder, "users"), exist_ok=True)
	with open(os.path.join(folder, "users.json"), "w", encoding="utf-8") as file:
		json.dump(sorted(people), file)
	for name, (created, last_active) in people.items():
		with open(os.path.join(folder, "users", f"{name}.json"), "w", encoding="utf-8") as file:
			json.dump({"name": name, "props": {"created": created, "last_active": last_active}}, file)

def _source(folder, **options):
	options.setdefault("data_path", folder)
	return players.Players("players", options)

def test_the_first_run_seeds_without_announcing_anyone():
	with tempfile.TemporaryDirectory() as folder:
		_write(folder, {"a": (1000, 2000)})
		memory = {}
		conditions = _source(folder).check(3000.0, memory)
		xtest.equal(conditions, [], "the seed is not news")
		xtest.equal(memory["seen"], {"a": 2000}, "last-active is remembered")

def test_a_player_not_seen_before_is_one_news_item():
	with tempfile.TemporaryDirectory() as folder:
		_write(folder, {"a": (1000, 2000), "b": (2500, 2500)})
		memory = {"seeded": True, "seen": {"a": 2000}}
		conditions = _source(folder).check(3000.0, memory)
		xtest.equal(len(conditions), 1, "one item for the new player")
		condition = conditions[0]
		xtest.equal(condition.state, event.STATE_INFO, "a join is information")
		xtest.equal(condition.kind, "news", "a player is not a health row")
		xtest.equal(condition.key, "players:new:b", "the key names the source, the kind and the player")
		xtest.contains("new player: b", condition.title, "the title says what happened")

def test_a_return_after_the_threshold_is_one_news_item():
	with tempfile.TemporaryDirectory() as folder:
		_write(folder, {"a": (1000, 2000 + 20 * DAY)})
		memory = {"seeded": True, "seen": {"a": 2000}}
		conditions = _source(folder, absence_days=14).check(3000.0, memory)
		xtest.equal(len(conditions), 1, "the return is one item")
		xtest.contains("returned after 20 days", conditions[0].title, "the title says how long")
		xtest.equal(memory["seen"]["a"], 2000 + 20 * DAY, "the new last-active is remembered")

def test_an_absence_below_the_threshold_is_quiet():
	with tempfile.TemporaryDirectory() as folder:
		_write(folder, {"a": (1000, 2000 + 2 * DAY)})
		memory = {"seeded": True, "seen": {"a": 2000}}
		xtest.equal(_source(folder, absence_days=14).check(3000.0, memory), [],
			"an idle player is not news")
		xtest.equal(memory["seen"]["a"], 2000 + 2 * DAY, "the time still moves")

def test_a_player_who_disappears_keeps_their_memory():
	with tempfile.TemporaryDirectory() as folder:
		_write(folder, {})
		memory = {"seeded": True, "seen": {"a": 2000}}
		xtest.equal(_source(folder).check(3000.0, memory), [], "a missing player is not news")
		xtest.equal(memory["seen"], {"a": 2000}, "the memory keeps the last-active time")

def test_a_broken_player_file_is_skipped_not_fatal():
	with tempfile.TemporaryDirectory() as folder:
		_write(folder, {"a": (1000, 2000)})
		with open(os.path.join(folder, "users", "a.json"), "w", encoding="utf-8") as file:
			file.write("not json")
		xtest.equal(_source(folder).check(3000.0, {}), [], "the seed survives a broken record")

def test_the_absence_days_and_interval_come_from_the_options():
	source = _source("/tmp", absence_days=30, interval_seconds=600, stale_after_seconds=1800)
	xtest.equal(source.absence_seconds, 30 * DAY, "the absence is configured in days")
	xtest.equal(source.interval(), 600, "the interval is configured")
	xtest.equal(source.stale_after(), 1800, "stale_after is configured")

def test_the_data_path_is_required():
	raised = False
	try:
		players.Players("players", {})
	except ValueError as exc:
		raised = "data_path" in str(exc)
	xtest.true(raised, "a player feed without a data path is refused")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
