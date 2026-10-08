#!/usr/bin/env python3
"""
taskupdate — Append-only task state updates for taskview.
Writes to tasks.csv resolved via R30: --csv > $TASKVIEW_CSV > <data-dir>/tasks.csv
"""

import argparse,csv,datetime,os,sys,time
from pathlib import Path
from tools.taskview.taskview import resolve_data_dir,resolve_csv

# Kept for backwards compatibility with existing tests that mock it
DEFAULT_CSV = Path.home() / ".local" / "share" / "taskview" / "tasks.csv"
FIELDNAMES = ["id", "status", "title", "due_ts", "chg_ts", "category", "tags", "importance", "description"]

def ensure_csv(path):
	path.parent.mkdir(parents=True, exist_ok=True)
	if not path.exists():
		with path.open("w", encoding="utf-8", newline="") as f:
			f.write("// tasks.csv — append-only, last-write-wins by id\n")
			f.write("// Schema: id,status,title,due_ts,chg_ts,category,tags,importance,description\n")
			f.write("id,status,title,due_ts,chg_ts,category,tags,importance,description\n")

def read_last_id(path):
	if not path.exists():
		return 0
	last_id = 0
	try:
		with path.open("r", encoding="utf-8") as f:
			reader = csv.reader(f)
			for row in reader:
				if not row or row[0].startswith("//") or row[0] == "id":
					continue
				try:
					last_id = max(last_id, int(row[0]))
				except ValueError:
					pass
	except OSError:
		pass
	return last_id

def escape_description(text: str) -> str:
	"""Escape newlines in description for CSV storage."""
	return text.replace("\n", "\\n")

def unescape_description(text: str) -> str:
	"""Unescape newlines in description from CSV storage."""
	return text.replace("\\n", "\n")

def append_row(path, task_id, status, title, due_ts, chg_ts, category="", tags="", importance="", description=""):
	ensure_csv(path)
	with path.open("a", encoding="utf-8", newline="") as f:
		writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
		writer.writerow([task_id, status, title or "", due_ts or "", chg_ts, category or "", tags or "", importance or "", escape_description(description or "")])
	print(f"Appended: id={task_id} status={status} title={title}")

def read_task(path, task_id):
	"""
	Return the last row for task_id as a dict, or None if there is no such row.
	Short rows read as empty (R33), so a legacy 5-column row has no category.
	"""
	current = {}
	with path.open("r", encoding="utf-8") as f:
		reader = csv.reader(f)
		for row in reader:
			if not row or row[0].startswith("//") or row[0] == "id":
				continue
			if len(row) >= 2 and row[0].isdigit() and int(row[0]) == task_id:
				current = {
					"id": int(row[0]), "status": row[1],
					"title": row[2] if len(row) > 2 else "",
					"due_ts": row[3] if len(row) > 3 else "",
					"chg_ts": row[4] if len(row) > 4 else "",
					"category": row[5] if len(row) > 5 else "",
					"tags": row[6] if len(row) > 6 else "",
					"importance": row[7] if len(row) > 7 else "",
					"description": unescape_description(row[8] if len(row) > 8 else ""),
				}
	return current or None

def read_all(path):
	"""
	Every task by id, last row per id winning (R34). Same row shape as read_task.
	"""
	state = {}
	with path.open("r", encoding="utf-8") as f:
		reader = csv.reader(f)
		for row in reader:
			if not row or row[0].startswith("//") or row[0] == "id":
				continue
			if len(row) >= 2 and row[0].isdigit():
				state[int(row[0])] = {
					"id": int(row[0]), "status": row[1],
					"title": row[2] if len(row) > 2 else "",
					"due_ts": row[3] if len(row) > 3 else "",
					"chg_ts": row[4] if len(row) > 4 else "",
					"category": row[5] if len(row) > 5 else "",
					"tags": row[6] if len(row) > 6 else "",
					"importance": row[7] if len(row) > 7 else "",
					"description": unescape_description(row[8] if len(row) > 8 else ""),
				}
	return state

def fmt_due(ts):
	"""Human form of a due timestamp, matching taskview's pane wording."""
	if not ts:
		return "no due"
	try:
		due_date = datetime.datetime.fromtimestamp(int(ts)).date()
	except (ValueError, OSError, OverflowError):
		return f"unparseable due ({ts})"
	day_diff = (due_date - datetime.date.today()).days
	if day_diff < 0:
		return f"overdue {abs(day_diff)}d"
	if day_diff == 0:
		return "today"
	if day_diff == 1:
		return "tomorrow"
	if day_diff < 7:
		return f"{day_diff}d"
	return due_date.strftime("%Y-%m-%d")

def parse_due(arg):
	if not arg or arg.lower() == "none":
		return ""
	try:
		return str(int(arg))
	except ValueError:
		pass
	# Date only — store noon, not midnight. A due date stored at 00:00 lands
	# exactly on the day boundary ("due at the start of that day"), which is
	# an off-by-one trap for the calendar-day math in taskview's fmt_due.
	try:
		dt = time.strptime(arg, "%Y-%m-%d")
		return str(int(time.mktime(dt)) + 12 * 3600)
	except ValueError:
		pass
	# Month-day without year — current year (strptime alone would default to
	# year 1900 and produce a nonsense timestamp), same noon rule.
	try:
		dt = time.strptime(f"{time.localtime().tm_year}-{arg}", "%Y-%m-%d")
		return str(int(time.mktime(dt)) + 12 * 3600)
	except ValueError:
		pass
	# Date + explicit time — keep the given time as-is.
	try:
		dt = time.strptime(arg, "%Y-%m-%d %H:%M")
		return str(int(time.mktime(dt)))
	except ValueError:
		pass
	try:
		dt = time.strptime(f"{time.localtime().tm_year}-{arg}", "%Y-%m-%d %H:%M")
		return str(int(time.mktime(dt)))
	except ValueError:
		pass
	print(f"Invalid due date: {arg}", file=sys.stderr)
	sys.exit(1)

def resolve_csv_path(args) -> Path:
	"""
	Resolve CSV path per R30: --csv > $TASKVIEW_CSV > <data-dir>/tasks.csv (R17/R18).
	args.csv is the explicit --csv argument (Path or None).
	"""
	# R30: explicit --csv wins
	if args.csv is not None:
		return args.csv
	# R30: $TASKVIEW_CSV next
	if "TASKVIEW_CSV" in os.environ:
		return Path(os.environ["TASKVIEW_CSV"])
	# R30: fallback to <data-dir>/tasks.csv per R17/R18
	data_dir = resolve_data_dir(args.data_dir, os.environ)
	return resolve_csv(data_dir, None)

def main():
	parser = argparse.ArgumentParser(description="Update taskview tasks (append-only)")
	parser.add_argument("--csv", type=Path, default=None, help="Path to tasks.csv (default: resolved via $TASKVIEW_CSV or data dir)")
	parser.add_argument("--data-dir", type=Path, default=None, help="Data directory (default: $TASKVIEW_DATA_DIR or $XDG_DATA_HOME/taskview or ~/.local/share/taskview)")
	sub = parser.add_subparsers(dest="cmd", required=True)

	p_add = sub.add_parser("add", help="Add new task")
	p_add.add_argument("title")
	p_add.add_argument("--due", help="Due date (timestamp or YYYY-MM-DD)")
	p_add.add_argument("--status", default="open", choices=["open", "done", "cancelled"])
	p_add.add_argument("--category", default=None)
	p_add.add_argument("--tags", default=None)
	p_add.add_argument("--importance", default=None, choices=["low", "medium", "high", ""])
	p_add.add_argument("--description", default=None)

	p_upd = sub.add_parser("update", help="Update existing task (by id)")
	p_upd.add_argument("id", type=int)
	p_upd.add_argument("--status", choices=["open", "done", "cancelled"])
	p_upd.add_argument("--title")
	p_upd.add_argument("--due", help="Due date (timestamp or YYYY-MM-DD)")
	p_upd.add_argument("--category", default=None)
	p_upd.add_argument("--tags", default=None)
	p_upd.add_argument("--importance", default=None, choices=["low", "medium", "high", ""])
	p_upd.add_argument("--description", default=None)

	p_done = sub.add_parser("done", help="Mark task done")
	p_done.add_argument("id", type=int)

	p_cancel = sub.add_parser("cancel", help="Mark task cancelled")
	p_cancel.add_argument("id", type=int)

	p_show = sub.add_parser("show", help="Show one task by id")
	p_show.add_argument("id", type=int)
	p_show.add_argument("--field", help="Print just this field (id, status, title, due_ts, chg_ts, category, tags, importance)")

	p_list = sub.add_parser("list", help="List tasks, id first")
	p_list.add_argument("--status", help="Only tasks with this status (default: all)")
	p_list.add_argument("--category", help="Only tasks in this category")

	args = parser.parse_args()
	now = int(time.time())

	# Resolve CSV path per R30
	csv_path = resolve_csv_path(args)

	if args.cmd == "add":
		task_id = read_last_id(csv_path) + 1
		due_ts = parse_due(args.due) if args.due else ""
		append_row(csv_path, task_id, args.status, args.title, due_ts, now, args.category, args.tags, args.importance, args.description)

	elif args.cmd == "update":
		if (args.status is None and args.title is None and args.due is None
			and args.category is None and args.tags is None and args.importance is None and args.description is None):
			print("Nothing to update", file=sys.stderr)
			sys.exit(1)
		current = read_task(csv_path, args.id)
		if not current:
			print(f"Task {args.id} not found", file=sys.stderr)
			sys.exit(1)
		status = args.status or current["status"]
		title = args.title if args.title is not None else current["title"]
		due_ts = parse_due(args.due) if args.due is not None else current["due_ts"]
		category = args.category if args.category is not None else current["category"]
		tags = args.tags if args.tags is not None else current["tags"]
		importance = args.importance if args.importance is not None else current["importance"]
		description = args.description if args.description is not None else current["description"]
		append_row(csv_path, args.id, status, title, due_ts, now, category, tags, importance, description)

	elif args.cmd == "done":
		current = read_task(csv_path, args.id)
		if not current:
			print(f"Task {args.id} not found", file=sys.stderr)
			sys.exit(1)
		append_row(csv_path, args.id, "done", current["title"], current["due_ts"], now, current["category"], current["tags"], current["importance"], current["description"])

	elif args.cmd == "cancel":
		current = read_task(csv_path, args.id)
		if not current:
			print(f"Task {args.id} not found", file=sys.stderr)
			sys.exit(1)
		append_row(csv_path, args.id, "cancelled", current["title"], current["due_ts"], now, current["category"], current["tags"], current["importance"], current["description"])

	elif args.cmd == "show":
		current = read_task(csv_path, args.id)
		if not current:
			print(f"Task {args.id} not found", file=sys.stderr)
			sys.exit(1)
		if args.field:
			# Field names are the CSV columns, so --field prints what is stored.
			# The human-readable due form is in the full view, not here: an agent
			# resolving a field usually wants the value it can pass back to update.
			if args.field not in current:
				print(f"Unknown field: {args.field}. Choose from: {', '.join(sorted(current))}", file=sys.stderr)
				sys.exit(1)
			print(current[args.field])
		else:
			print(f"#{current['id']}  {current['status']}")
			print(f"  title:       {current['title']}")
			print(f"  due:         {fmt_due(current['due_ts']) if current['due_ts'] else 'no due'}")
			if current["due_ts"]:
				print(f"  due_ts:      {current['due_ts']}")
			print(f"  category:    {current['category'] or '(none)'}")
			print(f"  tags:        {current['tags'] or '(none)'}")
			print(f"  importance:  {current['importance'] or '(none)'}")
			print(f"  description: {current['description'] or '(none)'}")

	elif args.cmd == "list":
		state = read_all(csv_path) if csv_path.exists() else {}
		rows_out = []
		for task_id in sorted(state):
			t = state[task_id]
			if args.status and t["status"] != args.status:
				continue
			if args.category and t["category"] != args.category:
				continue
			rows_out.append(t)
		if not rows_out:
			print("No matching tasks", file=sys.stderr)
			sys.exit(1)
		for t in rows_out:
			due = fmt_due(t["due_ts"]) if t["due_ts"] else "no due"
			print(f"#{t['id']}  {t['status']:<9}  {due:<12}  {t['title']}")

if __name__ == "__main__":
	main()

