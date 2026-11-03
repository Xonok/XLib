"""A watch redraw parses only the messages that changed.

The 28-day window is tens of thousands of assistant rows and hundreds of MB of
JSON, and unpacking it takes most of a second — a cost an active agent would
trigger several times per tool call. `StatsCache` keeps the parsed rows between
draws and re-reads only the recently created tail and the messages that have
not finished; a full window scan is a reconcile, taken when the row count
changes or every ten minutes.
"""
import contextlib,json,os,sqlite3,sys,tempfile,time
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, os.path.join(REPO, "tools"))

import xtest,skynet

_SCHEMA = """CREATE TABLE session_message (
	id text PRIMARY KEY,
	session_id text NOT NULL,
	type text NOT NULL,
	seq integer NOT NULL,
	time_created integer NOT NULL,
	time_updated integer NOT NULL,
	data text NOT NULL
)"""

def _message(created, output, finish="stop", error=None):
	"""The JSON opencode 2 stores for one assistant message."""
	message = {
		"model": {"id": "model-a"},
		"tokens": {"input": 10, "output": output},
		"time": {"created": created},
		"finish": finish,
	}
	if error is not None:
		message["error"] = error
	return json.dumps(message)

def _insert(conn, message_id, created, output=5, updated=None, finish="stop", error=None):
	conn.execute(
		"INSERT INTO session_message (id, session_id, type, seq, time_created, time_updated, data) VALUES (?, 'session', 'assistant', 0, ?, ?, ?)",
		(message_id, created, created if updated is None else updated, _message(created, output, finish, error)),
	)
	conn.commit()

def _update(conn, message_id, created, updated, output, finish="stop", error=None):
	conn.execute(
		"UPDATE session_message SET data = ?, time_updated = ? WHERE id = ?",
		(_message(created, output, finish, error), updated, message_id),
	)
	conn.commit()

@contextlib.contextmanager
def _database():
	"""A message database the tool reads as its own, and the connection to fill it."""
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "opencode.db"
		conn = sqlite3.connect(path)
		conn.execute(_SCHEMA)
		saved = skynet.DB_PATH
		skynet.DB_PATH = str(path)
		try:
			yield conn
		finally:
			skynet.DB_PATH = saved
			conn.close()

def test_an_unchanged_row_is_not_parsed_again():
	now_ms = int(time.time() * 1000)
	with _database() as conn:
		_insert(conn, "msg_1", now_ms - 60_000)
		cache = skynet.StatsCache()
		first = cache.load(3600)
		second = cache.load(3600)
	xtest.equal(len(first), 1, "the window holds the one message")
	xtest.true(first[0] is second[0], "an unchanged row keeps the tuple it was parsed into")

def test_only_the_changed_row_is_parsed_again():
	now_ms = int(time.time() * 1000)
	with _database() as conn:
		_insert(conn, "msg_1", now_ms - 120_000)
		_insert(conn, "msg_2", now_ms - 60_000)
		cache = skynet.StatsCache()
		first = cache.load(3600)
		untouched = next(row for row in first if row[3] == 5)
		_update(conn, "msg_2", now_ms - 60_000, now_ms - 30_000, 42)
		second = cache.load(3600)
	xtest.true(any(row is untouched for row in second), "the untouched row was not parsed again")
	xtest.true(any(row[3] == 42 for row in second), "the changed row carries its new token count")

def test_a_new_message_appears():
	now_ms = int(time.time() * 1000)
	with _database() as conn:
		_insert(conn, "msg_1", now_ms - 60_000)
		cache = skynet.StatsCache()
		xtest.equal(len(cache.load(3600)), 1, "the window starts with one message")
		_insert(conn, "msg_2", now_ms - 30_000, output=7)
		rows = cache.load(3600)
	xtest.equal(len(rows), 2, "the second message is in the next window")

def test_a_deleted_message_disappears():
	now_ms = int(time.time() * 1000)
	with _database() as conn:
		_insert(conn, "msg_1", now_ms - 120_000)
		_insert(conn, "msg_2", now_ms - 60_000)
		cache = skynet.StatsCache()
		cache.load(3600)
		conn.execute("DELETE FROM session_message WHERE id = 'msg_1'")
		conn.commit()
		rows = cache.load(3600)
	xtest.equal(len(rows), 1, "the deleted message is gone from the cache")

def test_a_message_that_leaves_the_window_is_dropped():
	now_ms = int(time.time() * 1000)
	with _database() as conn:
		_insert(conn, "msg_1", now_ms - 60_000)
		cache = skynet.StatsCache()
		xtest.equal(len(cache.load(3600)), 1, "the message is inside the window")
		conn.execute("UPDATE session_message SET time_created = ? WHERE id = 'msg_1'", (now_ms - 7200_000,))
		conn.commit()
		xtest.equal(len(cache.load(3600)), 0, "the window slid past the message")

def test_load_stats_returns_the_window_oldest_first():
	now_ms = int(time.time() * 1000)
	with _database() as conn:
		_insert(conn, "msg_new", now_ms - 60_000)
		_insert(conn, "msg_old", now_ms - 120_000)
		_insert(conn, "msg_gone", now_ms - 7200_000)
		rows = skynet.load_stats(3600)
	xtest.equal(len(rows), 2, "only the window's messages are read")
	xtest.true(rows[0][1] < rows[1][1], "the rows come oldest first")

def test_the_watch_report_matches_the_one_shot_report():
	now_ms = int(time.time() * 1000)
	with _database() as conn:
		_insert(conn, "msg_1", now_ms - 120_000, output=10)
		_insert(conn, "msg_2", now_ms - 60_000, output=20)
		cache = skynet.StatsCache()
		now = time.time()
		one_shot = skynet.build_report(1, now, height=24, width=80)
		watched = skynet.build_report(1, now, height=24, width=80, cache=cache)
	xtest.equal(watched, one_shot, "the cached rows render exactly as a fresh read")

def test_a_message_still_streaming_is_re_read_outside_the_tail():
	now_ms = int(time.time() * 1000)
	with _database() as conn:
		_insert(conn, "msg_1", now_ms - 7200_000, finish=None)
		cache = skynet.StatsCache()
		cache.load(4 * 3600)
		_update(conn, "msg_1", now_ms - 7200_000, now_ms - 1000, 99, finish=None)
		rows = cache.load(4 * 3600)
	xtest.true(any(row[3] == 99 for row in rows),
		"a message without a finish is read again even outside the tail")

def test_a_row_count_change_reconciles_at_once():
	now_ms = int(time.time() * 1000)
	with _database() as conn:
		_insert(conn, "msg_old", now_ms - 7200_000)
		_insert(conn, "msg_new", now_ms - 60_000)
		cache = skynet.StatsCache()
		cache.load(4 * 3600)
		conn.execute("DELETE FROM session_message WHERE id = 'msg_old'")
		conn.commit()
		rows = cache.load(4 * 3600)
	xtest.equal(len(rows), 1, "a deletion outside the tail is noticed at once")

def test_a_finished_message_written_again_is_caught_by_the_reconcile():
	now_ms = int(time.time() * 1000)
	with _database() as conn:
		_insert(conn, "msg_1", now_ms - 7200_000)
		cache = skynet.StatsCache()
		cache.load(4 * 3600)
		_update(conn, "msg_1", now_ms - 7200_000, now_ms - 1000, 77)
		saved = skynet._RECONCILE_SECONDS
		skynet._RECONCILE_SECONDS = 0
		try:
			rows = cache.load(4 * 3600)
		finally:
			skynet._RECONCILE_SECONDS = saved
	xtest.true(any(row[3] == 77 for row in rows),
		"the periodic reconcile picks up a finished message that moved")

def test_a_warm_redraw_does_not_scan_the_whole_window():
	now_ms = int(time.time() * 1000)
	with _database() as conn:
		_insert(conn, "msg_1", now_ms - 60_000)
		cache = skynet.StatsCache()
		cache.load(3600)
		statements = []
		original = skynet._connect
		def traced():
			connection = original()
			connection.set_trace_callback(statements.append)
			return connection
		skynet._connect = traced
		try:
			cache.load(3600)
		finally:
			skynet._connect = original
	xtest.true(
		not any("SELECT id, time_updated FROM session_message" in statement for statement in statements),
		"a redraw does not read every id in the window")
	xtest.true(
		any("FROM session_message WHERE type = 'assistant' AND time_created >=" in statement
			and "ORDER BY time_created" in statement for statement in statements),
		"it reads the recent tail instead")

def _comparable(stats):
	"""A model's sums without the wall-clock field a fresh aggregate seeds itself with."""
	return {model: {key: value for key, value in sums.items() if key != "first_seen"}
		for model, sums in stats.items()}

def test_the_cached_sums_match_a_fresh_aggregate():
	now_ms = int(time.time() * 1000)
	with _database() as conn:
		_insert(conn, "msg_1", now_ms - 180_000, output=10)
		_insert(conn, "msg_2", now_ms - 120_000, output=20, finish="tool-calls")
		_insert(conn, "msg_refused", now_ms - 60_000, output=0,
			finish=None, error={"type": "aborted", "message": "aborted"})
		cache = skynet.StatsCache()
		cache.load(3600)
		_update(conn, "msg_2", now_ms - 120_000, now_ms - 30_000, 42, finish="tool-calls")
		conn.execute("DELETE FROM session_message WHERE id = 'msg_refused'")
		conn.commit()
		_insert(conn, "msg_limited", now_ms - 20_000, output=1,
			error={"type": "provider.error", "message": "rate limit reached"})
		cache.load(3600)
		_update(conn, "msg_limited", now_ms - 20_000, now_ms - 10_000, 9)
		rows = cache.load(3600)
	xtest.equal(_comparable(cache.stats()), _comparable(skynet.aggregate(rows, time.time())),
		"the folded sums equal a fresh aggregate after updates and deletions")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
