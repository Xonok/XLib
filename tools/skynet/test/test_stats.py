"""A watch redraw parses only the messages that changed.

The 28-day window is roughly 45k assistant rows and 300 MB of JSON, and
unpacking it takes about 0.8 s — a cost an active agent triggers several times
per tool call. `StatsCache` keeps the parsed rows between draws and asks the
database only which `(id, time_updated)` pairs moved, so a redraw re-parses the
message being written and nothing else.
"""
import contextlib,json,os,sqlite3,sys,tempfile,time
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, os.path.join(REPO, "tools"))

import xtest
import skynet

_SCHEMA = """CREATE TABLE session_message (
	id text PRIMARY KEY,
	session_id text NOT NULL,
	type text NOT NULL,
	seq integer NOT NULL,
	time_created integer NOT NULL,
	time_updated integer NOT NULL,
	data text NOT NULL
)"""

def _message(created, output):
	"""The JSON opencode 2 stores for one assistant message."""
	return json.dumps({
		"model": {"id": "model-a"},
		"tokens": {"input": 10, "output": output},
		"time": {"created": created},
		"finish": "stop",
	})

def _insert(conn, message_id, created, output=5, updated=None):
	conn.execute(
		"INSERT INTO session_message (id, session_id, type, seq, time_created, time_updated, data) VALUES (?, 'session', 'assistant', 0, ?, ?, ?)",
		(message_id, created, created if updated is None else updated, _message(created, output)),
	)
	conn.commit()

def _update(conn, message_id, created, updated, output):
	conn.execute(
		"UPDATE session_message SET data = ?, time_updated = ? WHERE id = ?",
		(_message(created, output), updated, message_id),
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

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
