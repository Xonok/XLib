#!/usr/bin/env python3
"""
taskupdate — Append-only task state updates for taskview.
Writes to ~/.local/share/taskview/tasks.csv (last-write-wins by id).
"""

import argparse,csv,os,sys,time
from pathlib import Path

DEFAULT_CSV = Path.home() / ".local" / "share" / "taskview" / "tasks.csv"
FIELDNAMES = ["id", "status", "title", "due_ts", "chg_ts", "category", "tags", "importance"]

def ensure_csv(path):
	path.parent.mkdir(parents=True, exist_ok=True)
	if not path.exists():
		with path.open("w", encoding="utf-8", newline="") as f:
			f.write("// tasks.csv — append-only, last-write-wins by id\n")
			f.write("// Schema: id,status,title,due_ts,chg_ts,category,tags,importance\n")
			f.write("id,status,title,due_ts,chg_ts,category,tags,importance\n")

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

def append_row(path, task_id, status, title, due_ts, chg_ts, category="", tags="", importance=""):
	ensure_csv(path)
	with path.open("a", encoding="utf-8", newline="") as f:
		writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
		writer.writerow([task_id, status, title or "", due_ts or "", chg_ts, category or "", tags or "", importance or ""])
	print(f"Appended: id={task_id} status={status} title={title}")

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

def main():
	parser = argparse.ArgumentParser(description="Update taskview tasks (append-only)")
	parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
	sub = parser.add_subparsers(dest="cmd", required=True)

	p_add = sub.add_parser("add", help="Add new task")
	p_add.add_argument("title")
	p_add.add_argument("--due", help="Due date (timestamp or YYYY-MM-DD)")
	p_add.add_argument("--status", default="open", choices=["open", "done", "cancelled"])
	p_add.add_argument("--category", default=None)
	p_add.add_argument("--tags", default=None)
	p_add.add_argument("--importance", default=None, choices=["low", "medium", "high", ""])

	p_upd = sub.add_parser("update", help="Update existing task (by id)")
	p_upd.add_argument("id", type=int)
	p_upd.add_argument("--status", choices=["open", "done", "cancelled"])
	p_upd.add_argument("--title")
	p_upd.add_argument("--due", help="Due date (timestamp or YYYY-MM-DD)")
	p_upd.add_argument("--category", default=None)
	p_upd.add_argument("--tags", default=None)
	p_upd.add_argument("--importance", default=None, choices=["low", "medium", "high", ""])

	p_done = sub.add_parser("done", help="Mark task done")
	p_done.add_argument("id", type=int)

	p_cancel = sub.add_parser("cancel", help="Mark task cancelled")
	p_cancel.add_argument("id", type=int)

	args = parser.parse_args()
	now = int(time.time())

	if args.cmd == "add":
		task_id = read_last_id(args.csv) + 1
		due_ts = parse_due(args.due) if args.due else ""
		append_row(args.csv, task_id, args.status, args.title, due_ts, now, args.category, args.tags, args.importance)

	elif args.cmd == "update":
		if (args.status is None and args.title is None and args.due is None
			and args.category is None and args.tags is None and args.importance is None):
			print("Nothing to update", file=sys.stderr)
			sys.exit(1)
		current = {}
		with args.csv.open("r", encoding="utf-8") as f:
			reader = csv.reader(f)
			for row in reader:
				if not row or row[0].startswith("//") or row[0] == "id":
					continue
				if len(row) >= 2 and row[0].isdigit() and int(row[0]) == args.id:
					current = {
						"id": int(row[0]), "status": row[1],
						"title": row[2] if len(row) > 2 else "",
						"due_ts": row[3] if len(row) > 3 else "",
						"chg_ts": row[4] if len(row) > 4 else "",
						"category": row[5] if len(row) > 5 else "",
						"tags": row[6] if len(row) > 6 else "",
						"importance": row[7] if len(row) > 7 else "",
					}
		if not current:
			print(f"Task {args.id} not found", file=sys.stderr)
			sys.exit(1)
		status = args.status or current["status"]
		title = args.title if args.title is not None else current["title"]
		due_ts = parse_due(args.due) if args.due is not None else current["due_ts"]
		category = args.category if args.category is not None else current["category"]
		tags = args.tags if args.tags is not None else current["tags"]
		importance = args.importance if args.importance is not None else current["importance"]
		append_row(args.csv, args.id, status, title, due_ts, now, category, tags, importance)

	elif args.cmd == "done":
		current = {}
		with args.csv.open("r", encoding="utf-8") as f:
			reader = csv.reader(f)
			for row in reader:
				if not row or row[0].startswith("//") or row[0] == "id":
					continue
				if len(row) >= 2 and row[0].isdigit() and int(row[0]) == args.id:
					current = {
						"title": row[2] if len(row) > 2 else "",
						"due_ts": row[3] if len(row) > 3 else "",
						"category": row[5] if len(row) > 5 else "",
						"tags": row[6] if len(row) > 6 else "",
						"importance": row[7] if len(row) > 7 else "",
					}
		if not current:
			print(f"Task {args.id} not found", file=sys.stderr)
			sys.exit(1)
		append_row(args.csv, args.id, "done", current["title"], current["due_ts"], now, current["category"], current["tags"], current["importance"])

	elif args.cmd == "cancel":
		current = {}
		with args.csv.open("r", encoding="utf-8") as f:
			reader = csv.reader(f)
			for row in reader:
				if not row or row[0].startswith("//") or row[0] == "id":
					continue
				if len(row) >= 2 and row[0].isdigit() and int(row[0]) == args.id:
					current = {
						"title": row[2] if len(row) > 2 else "",
						"due_ts": row[3] if len(row) > 3 else "",
						"category": row[5] if len(row) > 5 else "",
						"tags": row[6] if len(row) > 6 else "",
						"importance": row[7] if len(row) > 7 else "",
					}
		if not current:
			print(f"Task {args.id} not found", file=sys.stderr)
			sys.exit(1)
		append_row(args.csv, args.id, "cancelled", current["title"], current["due_ts"], now, current["category"], current["tags"], current["importance"])

if __name__ == "__main__":
	main()
