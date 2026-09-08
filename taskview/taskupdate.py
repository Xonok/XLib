#!/usr/bin/env python3
"""
taskupdate — Append-only task state updates for taskview.
Writes to ~/.local/share/taskview/tasks.csv (last-write-wins by id).
"""

import argparse,csv,os,sys,time
from pathlib import Path

DEFAULT_CSV = Path.home() / ".local" / "share" / "taskview" / "tasks.csv"
FIELDNAMES = ["id", "status", "title", "due_ts", "chg_ts"]

def ensure_csv(path):
	path.parent.mkdir(parents=True, exist_ok=True)
	if not path.exists():
		with path.open("w", encoding="utf-8", newline="") as f:
			f.write("// tasks.csv — append-only, last-write-wins by id\n")
			f.write("id,status,title,due_ts,chg_ts\n")

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

def append_row(path, task_id, status, title, due_ts, chg_ts):
	ensure_csv(path)
	with path.open("a", encoding="utf-8", newline="") as f:
		writer = csv.writer(f)
		writer.writerow([task_id, status, title, due_ts or "", chg_ts])
	print(f"Appended: id={task_id} status={status} title={title}")

def parse_due(arg):
	if not arg or arg.lower() == "none":
		return ""
	try:
		return str(int(arg))
	except ValueError:
		pass
	for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%m-%d", "%m-%d %H:%M"):
		try:
			dt = time.strptime(arg, fmt)
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

	p_upd = sub.add_parser("update", help="Update existing task (by id)")
	p_upd.add_argument("id", type=int)
	p_upd.add_argument("--status", choices=["open", "done", "cancelled"])
	p_upd.add_argument("--title")
	p_upd.add_argument("--due", help="Due date (timestamp or YYYY-MM-DD)")

	p_done = sub.add_parser("done", help="Mark task done")
	p_done.add_argument("id", type=int)

	p_cancel = sub.add_parser("cancel", help="Mark task cancelled")
	p_cancel.add_argument("id", type=int)

	args = parser.parse_args()
	now = int(time.time())

	if args.cmd == "add":
		task_id = read_last_id(args.csv) + 1
		due_ts = parse_due(args.due) if args.due else ""
		append_row(args.csv, task_id, args.status, args.title, due_ts, now)

	elif args.cmd == "update":
		if args.status is None and args.title is None and args.due is None:
			print("Nothing to update", file=sys.stderr)
			sys.exit(1)
		current = {}
		with args.csv.open("r", encoding="utf-8") as f:
			reader = csv.reader(f)
			for row in reader:
				if not row or row[0].startswith("//") or row[0] == "id":
					continue
				if len(row) >= 5 and int(row[0]) == args.id:
					current = {"id": int(row[0]), "status": row[1], "title": row[2], "due_ts": row[3], "chg_ts": row[4]}
		if not current:
			print(f"Task {args.id} not found", file=sys.stderr)
			sys.exit(1)
		status = args.status or current["status"]
		title = args.title or current["title"]
		due_ts = parse_due(args.due) if args.due is not None else current["due_ts"]
		append_row(args.csv, args.id, status, title, due_ts, now)

	elif args.cmd == "done":
		append_row(args.csv, args.id, "done", "", "", now)

	elif args.cmd == "cancel":
		append_row(args.csv, args.id, "cancelled", "", "", now)

if __name__ == "__main__":
	main()
