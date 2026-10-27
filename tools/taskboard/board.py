"""The taskboard's model: selection, order, summary, due grammar and the write path.

The read path is taskview's: `read_csv` folds the store and `select_tasks`
applies the never-show rule, so the board is a second renderer over the one
selection layer rather than a second source. The write path is taskupdate's
`append_row` for the same reason — one row shape, one fold.

Every function that needs the clock takes `now` (epoch seconds), which is what
lets the suite run without one. The store is never created here: a board that
started against a missing store would present "you have no tasks" as a fact.
"""
import datetime,re,sys,threading
from pathlib import Path

_here = Path(__file__).resolve().parent
_root = _here.parent.parent
if str(_root) not in sys.path:
	sys.path.insert(0, str(_root))

from tools.taskview import taskupdate,taskview

_ABSOLUTE_DATE = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")
_MONTH_DAY_DATE = re.compile(r"^(\d{1,2})[-/](\d{1,2})$")
_BUMP = re.compile(r"^([+-])(\d+)([dw])$", re.IGNORECASE)
_GRAMMAR = "expected a date (YYYY-MM-DD or MM-DD), a bump (+Nd, +Nw, -Nd, -Nw) or none"
_WRITE_LOCK = threading.Lock()

class InvalidDue(Exception):
	"""A due value the grammar does not accept; the message is written for the page."""

class StoreMissing(Exception):
	"""The resolved store does not exist or vanished. The board never creates it."""

class TaskNotFound(Exception):
	"""No row in the store carries the requested id."""

class TaskNotOpen(Exception):
	"""The row exists and is done or cancelled, so the board does not edit it."""

class TaskChanged(Exception):
	"""The write's version token is not the stored one; `current` is the row in payload shape."""
	def __init__(self, current: dict):
		super().__init__("the task changed since the page read it")
		self.current = current

def parse_due_edit(value: str, current_due_ts: int | None, now: int) -> int | None:
	"""R10: turn one edit into a due timestamp at noon local, or None to clear it.

	Raises InvalidDue with the message the page shows. A bump is measured from
	the task's stored due date when it has one, and from today when it has not,
	so bumping an overdue task moves it by the amount asked for rather than
	back to the future.
	"""
	text = value.strip()
	if not text or text.lower() == "none":
		return None
	day = _absolute_day(text)
	if day is None:
		day = _month_day(text, now)
	if day is not None:
		return _noon(day)
	match = _BUMP.match(text)
	if match is not None:
		return _bumped(text, match, current_due_ts, now)
	raise InvalidDue(f"{text} is not a due date; {_GRAMMAR}")

def order_tasks(tasks: list[dict]) -> list[dict]:
	"""R4: a new list in board order — due day ascending, undated last, ties by id.

	The day, not the instant: two tasks due at different hours of the same
	calendar day order by id, because a due date is a day.
	"""
	return sorted(tasks, key=_due_key)

def summarise(tasks: list[dict], now: int) -> dict:
	"""R5: count the open tasks it is given by calendar day around `now`.

	The buckets are date comparisons, so a task due today is in `today` at
	09:00 as well as at 23:00. `open` is the sum, which holds because
	`read_board` has already restricted the list to open tasks.
	"""
	today = datetime.date.fromtimestamp(now)
	summary = {"open": 0, "overdue": 0, "today": 0, "this_week": 0, "later": 0, "undated": 0}
	for task in tasks:
		summary["open"] += 1
		due_ts = task["due_ts"]
		if due_ts is None:
			summary["undated"] += 1
			continue
		days = (datetime.date.fromtimestamp(int(due_ts)) - today).days
		if days < 0:
			summary["overdue"] += 1
		elif days == 0:
			summary["today"] += 1
		elif days <= 7:
			summary["this_week"] += 1
		else:
			summary["later"] += 1
	return summary

def task_payload(task: dict, now: int) -> dict:
	"""R6: one task in the shape the page receives; `chg_ts` is the write token.

	The description is left out because the wide view does not show it and it
	is the largest field, and `importance` because nothing here orders or
	filters by it.
	"""
	due_ts = task["due_ts"]
	reference = datetime.date.fromtimestamp(now)
	return {
		"id": int(task["id"]),
		"title": task["title"],
		"due_ts": int(due_ts) if due_ts is not None else None,
		"due_date": _date_text(due_ts),
		"due_label": taskupdate.fmt_due(int(due_ts) if due_ts is not None else None, today=reference),
		"category": task["category"],
		"tags": sorted(task["tags"]),
		"chg_ts": int(task["chg_ts"]),
	}

def read_board(csv_path: Path, now: int) -> dict:
	"""R3, R7: re-read the store and return the whole payload; raises StoreMissing.

	The selection is taskview's and the filter is `None`: an archived or
	cancelled tag hides a task, no `.taskview.yaml` is consulted, and an
	uncategorised task is shown like any other.
	"""
	if not csv_path.exists():
		raise StoreMissing(f"the task store {csv_path} does not exist")
	state = taskview.read_csv(csv_path)
	if not csv_path.exists():
		raise StoreMissing(f"the task store {csv_path} vanished while it was being read")
	selected = taskview.select_tasks(state, None)
	open_tasks = [task for task in selected.values() if task["status"] == "open"]
	ordered = order_tasks(open_tasks)
	return {
		"now": now,
		"store": {"path": str(csv_path)},
		"summary": summarise(ordered, now),
		"tasks": [task_payload(task, now) for task in ordered],
	}

def set_due(csv_path: Path, task_id: int, new_due_ts: int | None, expected_chg_ts: int, now: int) -> dict:
	"""R11, R12: read-check-append as one critical section, then the new payload.

	The row is re-read inside the lock rather than trusted from the page, and
	every field is copied to the new row because the store is last-row-wins: a
	row that omitted `importance` would erase it. The token steps past the old
	one when two writes share a second, so it is a version, not a clock reading.
	"""
	with _WRITE_LOCK:
		row = _current_row(csv_path, task_id)
		if row["status"] != "open":
			raise TaskNotOpen(f"task #{task_id} is {row['status']}; only open tasks are editable")
		stored_chg_ts = _row_chg_ts(row)
		if stored_chg_ts is None or stored_chg_ts != expected_chg_ts:
			raise TaskChanged(_row_payload(row, now))
		if not csv_path.exists():
			raise StoreMissing(f"the task store {csv_path} does not exist")
		taskupdate.append_row(
			csv_path, task_id, row["status"], row["title"], new_due_ts, max(now, stored_chg_ts + 1),
			row["category"], row["tags"], row["importance"], row["description"])
	return read_board(csv_path, now)

def stored_due_ts(row: dict | None) -> int | None:
	"""The due a raw taskupdate row carries; a malformed or empty column reads as undated."""
	if row is None or not row["due_ts"]:
		return None
	try:
		return int(row["due_ts"])
	except ValueError:
		return None

def _due_key(task: dict) -> tuple:
	if task["due_ts"] is None:
		return (1, 0, task["id"])
	return (0, datetime.date.fromtimestamp(int(task["due_ts"])).toordinal(), task["id"])

def _absolute_day(text: str) -> datetime.date | None:
	match = _ABSOLUTE_DATE.match(text)
	if match is None:
		return None
	return _valid_day(text, *match.groups())

def _month_day(text: str, now: int) -> datetime.date | None:
	match = _MONTH_DAY_DATE.match(text)
	if match is None:
		return None
	month, day = match.groups()
	return _valid_day(text, datetime.date.fromtimestamp(now).year, month, day)

def _valid_day(text: str, year: str | int, month: str, day: str) -> datetime.date:
	try:
		return datetime.date(int(year), int(month), int(day))
	except ValueError:
		raise InvalidDue(f"{text} is not a real date; {_GRAMMAR}") from None

def _bumped(text: str, match: re.Match, current_due_ts: int | None, now: int) -> int:
	sign, amount, unit = match.groups()
	count = int(amount)
	if count == 0:
		raise InvalidDue(f"{text} moves by zero days; {_GRAMMAR}")
	days = count * (7 if unit.lower() == "w" else 1)
	base = datetime.date.fromtimestamp(current_due_ts if current_due_ts else now)
	return _noon(base + datetime.timedelta(days=days if sign == "+" else -days))

def _noon(day: datetime.date) -> int:
	return int(datetime.datetime(day.year, day.month, day.day, 12, 0).timestamp())

def _date_text(due_ts: int | None) -> str | None:
	if due_ts is None:
		return None
	return datetime.date.fromtimestamp(int(due_ts)).isoformat()

def _current_row(csv_path: Path, task_id: int) -> dict:
	if not csv_path.exists():
		raise StoreMissing(f"the task store {csv_path} does not exist")
	try:
		row = taskupdate.read_task(csv_path, task_id)
	except OSError:
		raise StoreMissing(f"the task store {csv_path} could not be read") from None
	if row is None:
		raise TaskNotFound(f"there is no task #{task_id}")
	return row

def _row_chg_ts(row: dict) -> int | None:
	try:
		return int(row["chg_ts"])
	except (TypeError, ValueError):
		return None

def _row_payload(row: dict, now: int) -> dict:
	return task_payload(_task_from_row(row), now)

def _task_from_row(row: dict) -> dict:
	tags = {tag.strip() for tag in row["tags"].split(",") if tag.strip()}
	return {
		"id": int(row["id"]),
		"status": row["status"],
		"title": row["title"],
		"due_ts": stored_due_ts(row),
		"chg_ts": _row_chg_ts(row) or 0,
		"category": row["category"],
		"tags": tags,
		"importance": row["importance"],
		"description": row["description"],
	}
