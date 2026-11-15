"""The age counter under the header: a reading of when the visible data moved.

The counter ticks in seconds while the panel is idle, so the watch redraws on
the tick and not only on a database write. It restarts when what the tables or
the quota lines show changes, and it does not restart for what only the clock
moves — a refusal's age, the pace.
"""
import io,os,sys,time
from contextlib import redirect_stdout

# xtest and the tool under test are found relative to this file rather than to
# the working directory: a test that passes from one directory and fails from
# another is worse than one that never runs.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, os.path.join(REPO, "tools"))
import xtest,skynet

NOW = time.time()

def _rows(count=2):
	"""`count` assistant messages, one per model."""
	return [("model-%02d" % i, NOW - 60, 100, 50, 150, 0, 0, 0, None, None, "stop", "ses")
		for i in range(count)]

def _view(rows):
	"""The two tables' sums for `rows`, as the watch holds them."""
	return skynet.stats_view(rows, NOW, skynet.aggregate(rows, NOW))

def _quota():
	"""A Go and OpenRouter reading, so the header has a line per source."""
	return {
		"go": {"state": "ok", "product": "go", "used": 100_000_000, "limit": 6_000_000_000, "days_left": 5},
		"openrouter": {"state": "ok", "used": 10, "limit": 1000},
		"pace": {"used_percent": 2, "overall": 72, "today": 10},
	}

def test_the_age_keeps_counting_in_seconds():
	xtest.equal(skynet.elapsed_text(0), "0s", "zero is a reading, not an absence")
	xtest.equal(skynet.elapsed_text(59), "59s", "under a minute is seconds")
	xtest.equal(skynet.elapsed_text(60), "1m00s", "a minute keeps its seconds")
	xtest.equal(skynet.elapsed_text(192), "3m12s", "minutes and seconds")
	xtest.equal(skynet.elapsed_text(3600), "1h00m", "an hour keeps its minutes")
	xtest.equal(skynet.elapsed_text(3661), "1h01m", "an hour and a minute")
	xtest.equal(skynet.elapsed_text(86400 + 4 * 3600), "1d04h", "a day keeps its hours")
	xtest.equal(skynet.elapsed_text(-5), "0s", "a clock that gone backwards is still now")

def test_the_counter_sits_under_the_header():
	text = skynet.render(_rows(), NOW, height=24, width=100, quota=_quota(), changed_ago=192)
	lines = text.splitlines()
	xtest.equal(lines[2], "data 3m12s ago", "the counter follows every quota line")
	xtest.true(lines[3].startswith("=== Models (Today) ==="), "and comes before the first table")

def test_no_counter_without_a_baseline():
	text = skynet.render(_rows(), NOW, height=24, width=100, quota=_quota())
	lines = text.splitlines()
	xtest.true(lines[2].startswith("=== Models (Today) ==="), "one-shot has no previous frame, so no line")

def test_the_counter_costs_a_row_of_height():
	plain = skynet.render(_rows(2), NOW, height=9, width=100)
	counted = skynet.render(_rows(2), NOW, height=9, width=100, changed_ago=5)
	xtest.true(
		counted.count("model-") < plain.count("model-"),
		"the line is spent from the tables' room, not added beyond the pane")

def test_the_counter_never_widens_the_pane():
	for width in range(5, 40):
		text = skynet.render(_rows(), NOW, height=24, width=width, changed_ago=10 * 86400)
		for line in text.splitlines():
			xtest.true(len(line) <= width, f"width {width}: {line!r} is wider than the pane")

def test_the_key_ignores_what_only_the_clock_moves():
	rows = [("model-a", NOW - 7200, 100, 50, 150, 0, 0, 0, "rate_limit", "429", "stop", "ses")]
	early = skynet.visible_key(*_view(rows), _quota())
	late = skynet.visible_key(*_view(rows), _quota())
	xtest.equal(early, late, "the same data read at two moments is the same picture")
	xtest.equal(
		skynet.visible_key(*_view(rows), dict(_quota(), pace={"used_percent": 2, "overall": 80, "today": 10})),
		early, "the pace moving on its own is not a change")

def test_the_key_follows_new_usage():
	one = _view(_rows(1))
	two = _view(_rows(1) + [("model-00", NOW - 30, 100, 50, 150, 0, 0, 0, None, None, "stop", "ses")])
	xtest.not_equal(skynet.visible_key(*one, _quota()), skynet.visible_key(*two, _quota()),
		"a token that moved is a change")

def test_the_key_follows_the_quota_counters():
	saved = _quota()
	moved = _quota()
	moved["openrouter"]["used"] = 11
	xtest.not_equal(skynet.visible_key(*_view(_rows()), saved), skynet.visible_key(*_view(_rows()), moved),
		"a quota number that moved is a change")

class _Cache:
	"""A warm stats cache over a row list the test can grow."""

	def __init__(self, rows):
		self.rows = rows

	def load(self, seconds):
		return self.rows

	def stats(self):
		return skynet.aggregate(self.rows, NOW)

def test_the_watch_ticks_without_a_write_and_restarts_the_counter_on_one():
	frames = []
	cache = _Cache(_rows(1))
	state = {"call": 0}
	stop = RuntimeError("stop")

	def fake_draw(text):
		frames.append(text)

	def fake_changed(watcher, stamp, timeout=1.0):
		state["call"] += 1
		if state["call"] == 1:
			return stamp, False
		if state["call"] == 2:
			cache.rows = _rows(2)
			return ("written",), True
		raise stop

	saved = (skynet.draw, skynet._db_changed, skynet.db_stamp, skynet._db_watcher,
		skynet.StatsCache, skynet.sample_quota, skynet._REDRAW_FLOOR_SECONDS,
		skynet._COUNTER_TICK_SECONDS)
	skynet.draw = fake_draw
	skynet._db_changed = fake_changed
	skynet.db_stamp = lambda: ("stamp",)
	skynet._db_watcher = lambda: None
	skynet.StatsCache = lambda: cache
	skynet.sample_quota = lambda *args, **kwargs: None
	skynet._REDRAW_FLOOR_SECONDS = 0.0
	skynet._COUNTER_TICK_SECONDS = 0.0
	try:
		with redirect_stdout(io.StringIO()):
			try:
				skynet.watch(24)
			except RuntimeError:
				pass
	finally:
		(skynet.draw, skynet._db_changed, skynet.db_stamp, skynet._db_watcher,
			skynet.StatsCache, skynet.sample_quota, skynet._REDRAW_FLOOR_SECONDS,
			skynet._COUNTER_TICK_SECONDS) = saved
	xtest.equal(len(frames), 3, "the first frame, a tick frame and the frame that shows the change")
	xtest.contains("data 0s ago", frames[2], "the frame that shows the change shows it at zero")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
