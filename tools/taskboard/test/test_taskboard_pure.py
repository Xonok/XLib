"""The pure functions of taskboard: order, summary, payload and due grammar.

Every test passes `now` explicitly, so none of them reads the wall clock. The
requirement each test traces to is in its name.
"""
import datetime,os,sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "dev" / "xtest"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import xtest
from _harness import load_board

TODAY = datetime.date(2026, 10, 27)
NOW = int(datetime.datetime(2026, 10, 27, 9, 0).timestamp())

def _ts(year, month, day, hour=12, minute=0):
	return int(datetime.datetime(year, month, day, hour, minute).timestamp())

def _task(task_id, due_ts=None, **fields):
	task = {"id": task_id, "status": "open", "title": f"task {task_id}", "due_ts": due_ts, "chg_ts": 1000, "category": "", "tags": set(), "importance": "", "description": ""}
	task.update(fields)
	return task

def _ids(tasks):
	return [task["id"] for task in tasks]

def _find(payload, task_id):
	return next(task for task in payload["tasks"] if task["id"] == task_id)

def _invalid_message(module, value, current_due_ts, now):
	try:
		module.parse_due_edit(value, current_due_ts, now)
	except module.InvalidDue as error:
		return str(error)
	raise AssertionError(f"parse_due_edit({value!r}) did not raise InvalidDue")

def test_R4_due_dates_sort_ascending():
	board = load_board()
	tasks = [_task(1, _ts(2026, 10, 29)), _task(2, _ts(2026, 10, 27)), _task(3, _ts(2026, 10, 28))]
	xtest.equal(_ids(board.order_tasks(tasks)), [2, 3, 1])

def test_R4_undated_tasks_sort_last():
	board = load_board()
	tasks = [_task(1, None), _task(2, _ts(2026, 11, 30)), _task(3, None)]
	xtest.equal(_ids(board.order_tasks(tasks)), [2, 1, 3])

def test_R4_ties_break_by_id():
	board = load_board()
	tasks = [_task(9, _ts(2026, 10, 27)), _task(3, _ts(2026, 10, 27)), _task(6, _ts(2026, 10, 27))]
	xtest.equal(_ids(board.order_tasks(tasks)), [3, 6, 9])

def test_R4_same_calendar_day_orders_by_id_not_by_time():
	board = load_board()
	tasks = [_task(2, _ts(2026, 10, 27, 8)), _task(1, _ts(2026, 10, 27, 20))]
	xtest.equal(_ids(board.order_tasks(tasks)), [1, 2])

def test_R4_order_does_not_depend_on_importance_or_category():
	board = load_board()
	tasks = [_task(1, _ts(2026, 10, 28), importance="high", category="a"), _task(2, _ts(2026, 10, 27), importance="low", category="b")]
	xtest.equal(_ids(board.order_tasks(tasks)), [2, 1])

def test_R4_returns_a_new_list_without_mutating_the_input():
	board = load_board()
	tasks = [_task(2, _ts(2026, 10, 28)), _task(1, _ts(2026, 10, 27))]
	ordered = board.order_tasks(tasks)
	xtest.equal(_ids(tasks), [2, 1], "the input list must keep its order")
	xtest.true(ordered is not tasks, "order_tasks must return a new list")

def test_R4_order_is_deterministic_for_equal_input():
	board = load_board()
	tasks = [_task(3, None), _task(1, _ts(2026, 10, 27)), _task(2, _ts(2026, 10, 27))]
	xtest.equal(_ids(board.order_tasks(tasks)), _ids(board.order_tasks(tasks)))

def test_R4_empty_input_orders_to_an_empty_list():
	board = load_board()
	xtest.equal(board.order_tasks([]), [])

def test_R5_summary_has_the_documented_keys():
	board = load_board()
	xtest.equal(set(board.summarise([], NOW)), {"open", "overdue", "today", "this_week", "later", "undated"})

def test_R5_buckets_are_calendar_days():
	board = load_board()
	tasks = [
		_task(1, _ts(2026, 10, 26)),
		_task(2, _ts(2026, 10, 27)),
		_task(3, _ts(2026, 10, 28)),
		_task(4, _ts(2026, 11, 3)),
		_task(5, _ts(2026, 11, 4)),
		_task(6, None),
	]
	summary = board.summarise(tasks, NOW)
	xtest.equal(summary["overdue"], 1)
	xtest.equal(summary["today"], 1)
	xtest.equal(summary["this_week"], 2)
	xtest.equal(summary["later"], 1)
	xtest.equal(summary["undated"], 1)
	xtest.equal(summary["open"], 6)

def test_R5_due_today_is_not_overdue_in_the_morning():
	board = load_board()
	summary = board.summarise([_task(1, _ts(2026, 10, 27, 23, 59))], NOW)
	xtest.equal(summary["today"], 1)
	xtest.equal(summary["overdue"], 0)

def test_R5_a_due_instant_before_now_on_the_same_day_is_still_today():
	board = load_board()
	summary = board.summarise([_task(1, _ts(2026, 10, 27, 8, 0))], NOW)
	xtest.equal(summary["today"], 1)
	xtest.equal(summary["overdue"], 0)

def test_R5_seven_days_ahead_is_this_week():
	board = load_board()
	summary = board.summarise([_task(1, _ts(2026, 11, 3))], NOW)
	xtest.equal(summary["this_week"], 1)
	xtest.equal(summary["later"], 0)

def test_R5_eight_days_ahead_is_later():
	board = load_board()
	summary = board.summarise([_task(1, _ts(2026, 11, 4))], NOW)
	xtest.equal(summary["later"], 1)
	xtest.equal(summary["this_week"], 0)

def test_R5_open_is_the_sum_of_the_buckets():
	board = load_board()
	summary = board.summarise([_task(1, _ts(2026, 10, 26)), _task(2, None), _task(3, _ts(2026, 10, 27))], NOW)
	xtest.equal(summary["open"], summary["overdue"] + summary["today"] + summary["this_week"] + summary["later"] + summary["undated"])

def test_R5_an_empty_board_summarises_to_zero():
	board = load_board()
	xtest.equal(board.summarise([], NOW), {"open": 0, "overdue": 0, "today": 0, "this_week": 0, "later": 0, "undated": 0})

def test_R6_payload_has_exactly_the_documented_keys():
	board = load_board()
	payload = board.task_payload(_task(1, _ts(2026, 10, 27)), NOW)
	xtest.equal(set(payload), {"id", "title", "due_ts", "due_date", "due_label", "category", "tags", "chg_ts"})

def test_R6_id_and_title_are_preserved():
	board = load_board()
	payload = board.task_payload(_task(7, None, title="a title"), NOW)
	xtest.equal(payload["id"], 7)
	xtest.equal(payload["title"], "a title")

def test_R6_due_date_is_the_local_calendar_date():
	board = load_board()
	payload = board.task_payload(_task(1, _ts(2026, 10, 27)), NOW)
	xtest.equal(payload["due_date"], "2026-10-27")
	xtest.equal(payload["due_ts"], _ts(2026, 10, 27))

def test_R6_undated_payload_has_null_due_fields():
	board = load_board()
	payload = board.task_payload(_task(1, None), NOW)
	xtest.equal(payload["due_ts"], None)
	xtest.equal(payload["due_date"], None)

def test_R6_due_label_is_computed_for_now_not_the_wall_clock():
	board = load_board()
	payload = board.task_payload(_task(1, _ts(2026, 10, 27)), NOW)
	xtest.equal(payload["due_label"], "today")

def test_R6_tags_are_a_sorted_list():
	board = load_board()
	payload = board.task_payload(_task(1, None, tags={"zeta", "alpha", "beta"}), NOW)
	xtest.equal(payload["tags"], ["alpha", "beta", "zeta"])

def test_R6_category_is_an_empty_string_when_absent():
	board = load_board()
	payload = board.task_payload(_task(1, None), NOW)
	xtest.equal(payload["category"], "")

def test_R6_due_label_comes_from_taskupdate_fmt_due():
	board = load_board()
	from tools.taskview import taskupdate
	due = _ts(2026, 11, 10)
	payload = board.task_payload(_task(1, due), NOW)
	xtest.equal(payload["due_label"], taskupdate.fmt_due(due, today=TODAY))
	xtest.equal(payload["due_label"], "11-10")

def test_R6_the_board_and_pane_word_far_dates_identically():
	from tools.taskview import taskupdate,taskview
	today = datetime.date.today()
	due = today + datetime.timedelta(days=14)
	stamp = int(datetime.datetime(due.year, due.month, due.day, 12, 0).timestamp())
	xtest.equal(taskupdate.fmt_due(stamp, today=today), taskview.fmt_due(stamp))

def test_R6_chg_ts_is_an_integer():
	board = load_board()
	payload = board.task_payload(_task(1, None, chg_ts=1234), NOW)
	xtest.equal(payload["chg_ts"], 1234)
	xtest.kind(payload["chg_ts"], int)

def test_R6_description_and_importance_are_not_in_the_payload():
	board = load_board()
	payload = board.task_payload(_task(1, None, description="long text", importance="high"), NOW)
	xtest.true("description" not in payload)
	xtest.true("importance" not in payload)

def test_fmt_due_accepts_a_pinned_today():
	from tools.taskview import taskupdate
	xtest.equal(taskupdate.fmt_due(_ts(2026, 10, 27), today=TODAY), "today")
	xtest.equal(taskupdate.fmt_due(_ts(2026, 10, 28), today=TODAY), "tomorrow")
	xtest.equal(taskupdate.fmt_due(_ts(2026, 10, 24), today=TODAY), "overdue 3d")
	xtest.equal(taskupdate.fmt_due(_ts(2026, 11, 10), today=TODAY), "11-10")

def test_fmt_due_omitting_today_still_uses_the_wall_clock():
	from tools.taskview import taskupdate
	today = datetime.date.today()
	stamp = int(datetime.datetime(today.year, today.month, today.day, 12, 0).timestamp())
	xtest.equal(taskupdate.fmt_due(stamp), taskupdate.fmt_due(stamp, today=today))

def test_R10_absolute_dash_date_is_noon_local():
	board = load_board()
	xtest.equal(board.parse_due_edit("2026-10-27", None, NOW), _ts(2026, 10, 27))

def test_R10_absolute_slash_date_is_the_same_day():
	board = load_board()
	xtest.equal(board.parse_due_edit("2026/10/27", None, NOW), _ts(2026, 10, 27))

def test_R10_month_day_uses_the_current_year_from_now():
	board = load_board()
	now = int(datetime.datetime(2026, 3, 5, 9, 0).timestamp())
	xtest.equal(board.parse_due_edit("10-27", None, now), _ts(2026, 10, 27))

def test_R10_month_day_accepts_the_slash_form():
	board = load_board()
	xtest.equal(board.parse_due_edit("10/27", None, NOW), _ts(2026, 10, 27))

def test_R10_month_day_uses_the_year_from_now_not_the_wall_clock():
	board = load_board()
	now = int(datetime.datetime(2030, 1, 2, 9, 0).timestamp())
	xtest.equal(board.parse_due_edit("12-31", None, now), _ts(2030, 12, 31))

def test_R10_day_bump_is_measured_from_the_current_due_date():
	board = load_board()
	xtest.equal(board.parse_due_edit("+7d", _ts(2026, 10, 20), NOW), _ts(2026, 10, 27))

def test_R10_week_bump_is_measured_from_the_current_due_date():
	board = load_board()
	xtest.equal(board.parse_due_edit("+2w", _ts(2026, 10, 13), NOW), _ts(2026, 10, 27))

def test_R10_negative_day_bump():
	board = load_board()
	xtest.equal(board.parse_due_edit("-3d", _ts(2026, 10, 30), NOW), _ts(2026, 10, 27))

def test_R10_negative_week_bump():
	board = load_board()
	xtest.equal(board.parse_due_edit("-1w", _ts(2026, 11, 3), NOW), _ts(2026, 10, 27))

def test_R10_bump_without_a_due_date_is_measured_from_today():
	board = load_board()
	xtest.equal(board.parse_due_edit("+3d", None, NOW), _ts(2026, 10, 30))

def test_R10_negative_bump_without_a_due_date_is_measured_from_today():
	board = load_board()
	xtest.equal(board.parse_due_edit("-2d", None, NOW), _ts(2026, 10, 25))

def test_R10_overdue_bump_is_measured_from_the_stored_date():
	board = load_board()
	xtest.equal(board.parse_due_edit("+7d", _ts(2026, 10, 24), NOW), _ts(2026, 10, 31))

def test_R10_the_unit_is_case_insensitive():
	board = load_board()
	xtest.equal(board.parse_due_edit("+2D", _ts(2026, 10, 20), NOW), _ts(2026, 10, 22))

def test_R10_none_clears_the_due_date():
	board = load_board()
	xtest.equal(board.parse_due_edit("none", _ts(2026, 10, 20), NOW), None)

def test_R10_the_empty_string_clears_the_due_date():
	board = load_board()
	xtest.equal(board.parse_due_edit("", _ts(2026, 10, 20), NOW), None)

def test_R10_none_is_case_insensitive():
	board = load_board()
	xtest.equal(board.parse_due_edit("NoNe", _ts(2026, 10, 20), NOW), None)

def test_R10_whitespace_is_trimmed():
	board = load_board()
	xtest.equal(board.parse_due_edit("  2026-10-27  ", None, NOW), _ts(2026, 10, 27))
	xtest.equal(board.parse_due_edit("  none  ", None, NOW), None)

def test_R10_absolute_date_ignores_the_current_due_date():
	board = load_board()
	xtest.equal(board.parse_due_edit("2026-10-27", _ts(2026, 11, 1), NOW), _ts(2026, 10, 27))

def test_R10_zero_day_bump_is_invalid():
	board = load_board()
	xtest.raises(board.InvalidDue, lambda: board.parse_due_edit("+0d", None, NOW))

def test_R10_zero_week_bump_is_invalid():
	board = load_board()
	xtest.raises(board.InvalidDue, lambda: board.parse_due_edit("-0w", None, NOW))

def test_R10_month_bump_is_invalid():
	board = load_board()
	xtest.raises(board.InvalidDue, lambda: board.parse_due_edit("+1m", None, NOW))

def test_R10_a_bump_without_a_sign_is_invalid():
	board = load_board()
	xtest.raises(board.InvalidDue, lambda: board.parse_due_edit("7d", None, NOW))

def test_R10_a_fractional_bump_is_invalid():
	board = load_board()
	xtest.raises(board.InvalidDue, lambda: board.parse_due_edit("+1.5d", None, NOW))

def test_R10_a_word_is_invalid():
	board = load_board()
	xtest.raises(board.InvalidDue, lambda: board.parse_due_edit("tomorrow", None, NOW))

def test_R10_an_impossible_date_is_invalid():
	board = load_board()
	xtest.raises(board.InvalidDue, lambda: board.parse_due_edit("2026-02-30", None, NOW))
	xtest.raises(board.InvalidDue, lambda: board.parse_due_edit("2026-13-01", None, NOW))

def test_R10_a_year_bump_is_invalid():
	board = load_board()
	xtest.raises(board.InvalidDue, lambda: board.parse_due_edit("+1y", None, NOW))

def test_R10_the_invalid_message_names_the_accepted_forms():
	board = load_board()
	message = _invalid_message(board, "tomorrow", None, NOW)
	xtest.contains("YYYY-MM-DD", message)
	xtest.contains("+N", message)

def test_R10_a_parsed_date_is_stored_at_noon():
	board = load_board()
	parsed = board.parse_due_edit("2026-10-27", None, NOW)
	xtest.equal(datetime.datetime.fromtimestamp(parsed).hour, 12)

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
