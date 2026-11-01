"""The store-facing functions of taskboard: the board payload and the write path.

Every test uses a temporary store and an explicit `now`; the real store is
never opened. The requirement each test traces to is in its name.
"""
import datetime,os,sys,tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "dev" / "xtest"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import xtest
from _harness import PAYLOAD_KEYS,Store,load_board,seed_store

NOW = int(datetime.datetime(2026, 10, 27, 9, 0).timestamp())

def _ts(year, month, day, hour=12, minute=0):
	return int(datetime.datetime(year, month, day, hour, minute).timestamp())

def _ids(payload):
	return [task["id"] for task in payload["tasks"]]

def _find(payload, task_id):
	return next(task for task in payload["tasks"] if task["id"] == task_id)

def _error(exception_type, fn):
	try:
		fn()
	except exception_type as error:
		return error
	raise AssertionError(f"expected {exception_type.__name__}")

def test_R2_read_board_raises_StoreMissing_for_a_missing_store():
	board = load_board()
	with Store() as store:
		xtest.raises(board.StoreMissing, lambda: board.read_board(store.csv, NOW))

def test_R3_only_open_tasks_are_shown():
	board = load_board()
	with Store() as store:
		store.add(1, status="open")
		store.add(2, status="done")
		store.add(3, status="cancelled")
		xtest.equal(_ids(board.read_board(store.csv, NOW)), [1])

def test_R3_a_done_task_is_hidden_even_with_a_critical_tag():
	board = load_board()
	with Store() as store:
		store.add(1, status="done", tags="critical")
		store.add(2, status="open")
		xtest.equal(_ids(board.read_board(store.csv, NOW)), [2])

def test_R3_a_cancelled_task_is_hidden_even_with_an_emergency_tag():
	board = load_board()
	with Store() as store:
		store.add(1, status="cancelled", tags="emergency")
		store.add(2, status="open")
		xtest.equal(_ids(board.read_board(store.csv, NOW)), [2])

def test_R3_a_never_show_tag_hides_an_open_task():
	board = load_board()
	with Store() as store:
		store.add(1, tags="archived")
		store.add(2)
		xtest.equal(_ids(board.read_board(store.csv, NOW)), [2])

def test_R3_a_cancelled_tag_hides_an_open_task():
	board = load_board()
	with Store() as store:
		store.add(1, tags="cancelled")
		store.add(2)
		xtest.equal(_ids(board.read_board(store.csv, NOW)), [2])

def test_R3_an_uncategorised_task_is_shown():
	board = load_board()
	with Store() as store:
		store.add(1, category="")
		xtest.equal(_ids(board.read_board(store.csv, NOW)), [1])

def test_R3_a_category_outside_any_filter_is_shown():
	board = load_board()
	with Store() as store:
		store.add(1, category="not-in-any-filter")
		store.add(2, category="another-category")
		xtest.equal(_ids(board.read_board(store.csv, NOW)), [1, 2])

def test_R3_board_order_is_the_R4_order():
	board = load_board()
	with Store() as store:
		store.add(1, due_ts=_ts(2026, 10, 29))
		store.add(2, due_ts=_ts(2026, 10, 27))
		store.add(3, due_ts=None)
		xtest.equal(_ids(board.read_board(store.csv, NOW)), [2, 1, 3])

def test_R7_read_board_has_the_documented_top_level_keys():
	board = load_board()
	with Store() as store:
		store.add(1)
		xtest.equal(set(board.read_board(store.csv, NOW)), {"now", "store", "summary", "tasks"})

def test_R7_read_board_now_is_the_argument():
	board = load_board()
	with Store() as store:
		store.add(1)
		xtest.equal(board.read_board(store.csv, NOW)["now"], NOW)

def test_R7_read_board_store_path_is_the_csv_it_read():
	board = load_board()
	with Store() as store:
		store.add(1)
		payload = board.read_board(store.csv, NOW)
		xtest.equal(Path(payload["store"]["path"]).resolve(), store.csv.resolve())

def test_R7_read_board_rereads_the_store_on_every_call():
	board = load_board()
	with Store() as store:
		store.add(1)
		first = board.read_board(store.csv, NOW)
		store.add(2)
		second = board.read_board(store.csv, NOW)
		xtest.equal(len(second["tasks"]), len(first["tasks"]) + 1)

def test_R27_a_taskview_filter_file_is_not_read():
	board = load_board()
	with Store() as store, tempfile.TemporaryDirectory() as folder:
		store.add(1, category="outside-the-filter")
		(Path(folder) / ".taskview.yaml").write_text("categories: [only-this]\ntags: [only-this]\n", encoding="utf-8")
		old = os.getcwd()
		os.chdir(folder)
		try:
			payload = board.read_board(store.csv, NOW)
		finally:
			os.chdir(old)
		xtest.equal(_ids(payload), [1])

def test_R11_set_due_appends_the_new_due_date():
	board = load_board()
	with Store() as store:
		store.add(1, due_ts=_ts(2026, 10, 20), chg_ts=1000)
		payload = board.set_due(store.csv, 1, _ts(2026, 10, 27), 1000, NOW)
		xtest.equal(_find(payload, 1)["due_date"], "2026-10-27")

def test_R11_set_due_returns_the_payload_after_the_append():
	board = load_board()
	with Store() as store:
		store.add(1, due_ts=None, chg_ts=1000)
		payload = board.set_due(store.csv, 1, _ts(2026, 10, 27), 1000, NOW)
		xtest.equal(set(payload), {"now", "store", "summary", "tasks"})
		xtest.equal(_find(payload, 1)["due_ts"], _ts(2026, 10, 27))

def test_R11_every_stored_field_is_copied_to_the_new_row():
	board = load_board()
	with Store() as store:
		store.add(1, title="keep me", due_ts=_ts(2026, 10, 20), chg_ts=1000, category="xlib", tags="one,two", importance="high", description="details")
		board.set_due(store.csv, 1, _ts(2026, 10, 27), 1000, NOW)
		row = store.read_task(1)
		xtest.equal(row, {"id": 1, "status": "open", "title": "keep me", "due_ts": str(_ts(2026, 10, 27)), "chg_ts": str(NOW), "category": "xlib", "tags": "one,two", "importance": "high", "description": "details", "queued_on": ""})

def test_R11_a_description_with_a_newline_survives_the_copy():
	board = load_board()
	with Store() as store:
		store.add(1, chg_ts=1000, description="first line\nsecond line")
		board.set_due(store.csv, 1, _ts(2026, 10, 27), 1000, NOW)
		xtest.equal(store.read_task(1)["description"], "first line\nsecond line")

def test_R11_chg_ts_is_now_when_now_is_later():
	board = load_board()
	with Store() as store:
		store.add(1, chg_ts=1000)
		board.set_due(store.csv, 1, None, 1000, 5000)
		xtest.equal(store.read_task(1)["chg_ts"], "5000")

def test_R11_chg_ts_steps_past_old_when_now_is_not_later():
	board = load_board()
	with Store() as store:
		store.add(1, chg_ts=5000)
		board.set_due(store.csv, 1, None, 5000, 1000)
		xtest.equal(store.read_task(1)["chg_ts"], "5001")

def test_R11_two_writes_in_one_second_have_distinct_tokens():
	board = load_board()
	with Store() as store:
		store.add(1, chg_ts=1000)
		first = board.set_due(store.csv, 1, _ts(2026, 10, 27), 1000, NOW)
		second = board.set_due(store.csv, 1, _ts(2026, 10, 28), first["tasks"][0]["chg_ts"], NOW)
		xtest.equal(second["tasks"][0]["chg_ts"], first["tasks"][0]["chg_ts"] + 1)

def test_R11_a_missing_task_raises_TaskNotFound():
	board = load_board()
	with Store() as store:
		store.add(1, chg_ts=1000)
		xtest.raises(board.TaskNotFound, lambda: board.set_due(store.csv, 99, None, 1000, NOW))

def test_R11_a_done_task_raises_TaskNotOpen():
	board = load_board()
	with Store() as store:
		store.add(1, status="done", chg_ts=1000)
		xtest.raises(board.TaskNotOpen, lambda: board.set_due(store.csv, 1, None, 1000, NOW))

def test_R11_a_cancelled_task_raises_TaskNotOpen():
	board = load_board()
	with Store() as store:
		store.add(1, status="cancelled", chg_ts=1000)
		xtest.raises(board.TaskNotOpen, lambda: board.set_due(store.csv, 1, None, 1000, NOW))

def test_R11_a_stale_token_raises_TaskChanged():
	board = load_board()
	with Store() as store:
		store.add(1, due_ts=_ts(2026, 10, 20), chg_ts=1000)
		xtest.raises(board.TaskChanged, lambda: board.set_due(store.csv, 1, _ts(2026, 10, 27), 999, NOW))

def test_R12_a_conflict_carries_the_current_task_in_payload_shape():
	board = load_board()
	with Store() as store:
		store.add(1, due_ts=_ts(2026, 10, 20), chg_ts=1000)
		error = _error(board.TaskChanged, lambda: board.set_due(store.csv, 1, _ts(2026, 10, 27), 999, NOW))
		xtest.equal(set(error.current), PAYLOAD_KEYS)

def test_R12_a_conflict_reports_the_current_due_date():
	board = load_board()
	with Store() as store:
		store.add(1, due_ts=_ts(2026, 10, 20), chg_ts=1000)
		error = _error(board.TaskChanged, lambda: board.set_due(store.csv, 1, _ts(2026, 10, 27), 999, NOW))
		xtest.equal(error.current["due_date"], "2026-10-20")

def test_R11_a_non_integer_stored_chg_ts_is_a_conflict():
	board = load_board()
	with Store() as store:
		store.add(1, chg_ts="not-a-number")
		xtest.raises(board.TaskChanged, lambda: board.set_due(store.csv, 1, None, 1000, NOW))

def test_R11_a_missing_store_raises_StoreMissing():
	board = load_board()
	with Store() as store:
		xtest.raises(board.StoreMissing, lambda: board.set_due(store.csv, 1, None, 1000, NOW))

def test_R11_a_missing_store_is_not_recreated():
	board = load_board()
	with Store() as store:
		xtest.raises(board.StoreMissing, lambda: board.set_due(store.csv, 1, None, 1000, NOW))
		xtest.true(not store.csv.exists(), "a failed write must not create the store")

def test_R11_clearing_the_due_date_stores_an_empty_due():
	board = load_board()
	with Store() as store:
		store.add(1, due_ts=_ts(2026, 10, 20), chg_ts=1000)
		payload = board.set_due(store.csv, 1, None, 1000, NOW)
		xtest.equal(_find(payload, 1)["due_ts"], None)
		xtest.equal(store.read_task(1)["due_ts"], "")

def test_R11_an_edit_appends_exactly_one_row():
	board = load_board()
	with Store() as store:
		store.add(1, chg_ts=1000)
		before = len(store.rows())
		board.set_due(store.csv, 1, _ts(2026, 10, 27), 1000, NOW)
		xtest.equal(len(store.rows()), before + 1)

def test_R11_other_tasks_are_unchanged():
	board = load_board()
	with Store() as store:
		store.add(1, chg_ts=1000)
		store.add(2, title="untouched", due_ts=_ts(2026, 11, 1), chg_ts=2000)
		before = store.read_task(2)
		board.set_due(store.csv, 1, _ts(2026, 10, 27), 1000, NOW)
		xtest.equal(store.read_task(2), before)

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
