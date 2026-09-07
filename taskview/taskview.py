#!/usr/bin/env python3
"""
taskview — Read-only task display for tmux pane.
Reads append-only CSV from ~/.local/share/taskview/tasks.csv
"""

import argparse,csv,os,sys,time
from datetime import datetime,timedelta
from pathlib import Path

try:
	import inotify.adapters
	HAS_INOTIFY = True
except ImportError:
	HAS_INOTIFY = False

DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "taskview"
DEFAULT_CSV = DEFAULT_DATA_DIR / "tasks.csv"
POLL_INTERVAL = 1.0

_CLEAR_SCREEN = "\033[2J\033[H"
_HEADER = "=== Tasks ==="

def parse_args():
	parser = argparse.ArgumentParser(description="Display condensed task view")
	parser.add_argument(
		"--csv",
		type=Path,
		default=DEFAULT_CSV,
		help="Path to tasks.csv (default: ~/.local/share/taskview/tasks.csv)",
	)
	parser.add_argument(
		"--watch",
		action="store_true",
		help="Watch for changes and redraw",
	)
	return parser.parse_args()

def ensure_data_dir(path):
	path.parent.mkdir(parents=True, exist_ok=True)

def read_csv(path):
	"""Read and fold CSV into current state per task id."""
	if not path.exists():
		return {}
	state = {}
	try:
		with path.open("r", encoding="utf-8") as f:
			reader = csv.reader(f)
			for row in reader:
				if not row:
					continue
				if row[0].startswith("//"):
					continue
				if len(row) < 5:
					continue
				try:
					task_id = int(row[0])
					status = row[1]
					title = row[2]
					due_ts = int(row[3]) if row[3] else None
					chg_ts = int(row[4])
					state[task_id] = {
						"id": task_id,
						"status": status,
						"title": title,
						"due_ts": due_ts,
						"chg_ts": chg_ts,
					}
				except (ValueError, IndexError):
					continue
	except OSError:
		pass
	return state

def compute_metrics(state):
	"""Compute pace and queue metrics from folded state."""
	now = time.time()
	today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
	week_ago = now - 7 * 86400
	month_ago = now - 30 * 86400

	done_day = 0
	done_week = 0
	done_month = 0
	active_count = 0
	open_tasks = []

	for task in state.values():
		if task["status"] == "done":
			ts = task["chg_ts"]
			if ts >= today_start:
				done_day += 1
			if ts >= week_ago:
				done_week += 1
			if ts >= month_ago:
				done_month += 1
		elif task["status"] == "open":
			active_count += 1
			open_tasks.append(task)

	open_tasks.sort(key=lambda t: -t["chg_ts"])

	this_week = 0
	this_month = 0
	later = 0
	week_limit = now + 7 * 86400
	month_limit = now + 30 * 86400
	for t in open_tasks:
		due = t["due_ts"]
		if due is None:
			later += 1
		elif due <= week_limit:
			this_week += 1
		elif due <= month_limit:
			this_month += 1
		else:
			later += 1

	return {
		"done_day": done_day,
		"done_week": done_week,
		"done_month": done_month,
		"active": active_count,
		"this_week": this_week,
		"this_month": this_month,
		"later": later,
		"open_tasks": open_tasks,
	}

def fmt_time(ts):
	if ts is None:
		return "—"
	dt = datetime.fromtimestamp(ts)
	now = datetime.now()
	diff = now - dt
	if diff < timedelta(hours=1):
		return f"{int(diff.total_seconds() // 60)}m ago"
	if diff < timedelta(hours=24):
		return f"{int(diff.total_seconds() // 3600)}h ago"
	if diff < timedelta(days=7):
		return f"{diff.days}d ago"
	return dt.strftime("%m-%d")

def fmt_due(ts):
	if ts is None:
		return "no due"
	dt = datetime.fromtimestamp(ts)
	now = datetime.now()
	diff = dt - now
	if diff.days < 0:
		return f"overdue {abs(diff.days)}d"
	if diff.days == 0:
		return "today"
	if diff.days == 1:
		return "tomorrow"
	if diff.days < 7:
		return f"{diff.days}d"
	return dt.strftime("%m-%d")

def truncate(text, width):
	if len(text) <= width:
		return text
	return text[: max(0, width - 1)] + "…"

def build_view(state, metrics, width=80):
	lines = []
	lines.append(_HEADER)
	lines.append("")

	open_tasks = metrics["open_tasks"]

	if open_tasks:
		current = open_tasks[0]
		lines.append(f"▸ {current['title']}")
		due_str = fmt_due(current["due_ts"])
		chg_str = fmt_time(current["chg_ts"])
		lines.append(f"  {chg_str}  ·  due: {due_str}")
		lines.append("")
	else:
		lines.append("▸ (no open tasks)")
		lines.append("")

	lines.append("UPCOMING")
	if len(open_tasks) > 1:
		for task in open_tasks[1:4]:
			due_str = fmt_due(task["due_ts"])
			lines.append(f" · {truncate(task['title'], width - 4)}  ({due_str})")
	else:
		lines.append(" · (none)")
	lines.append("")

	lines.append("PACE")
	lines.append(f" Day:   {metrics['done_day']} done, {metrics['active']} active")
	lines.append(f" Week:  {metrics['done_week']} done")
	lines.append(f" Month: {metrics['done_month']} done")
	lines.append("")

	total = metrics["this_week"] + metrics["this_month"] + metrics["later"]
	lines.append(f"QUEUE: {total} remaining ({metrics['this_week']} this week, "
		f"{metrics['this_month']} this month, {metrics['later']} later)")

	return "\n".join(lines)

def draw(view):
	sys.stdout.write(_CLEAR_SCREEN)
	sys.stdout.write(view)
	sys.stdout.flush()

def watch_inotify(csv_path, callback):
	"""Watch file using inotify, call callback on change."""
	parent = csv_path.parent
	filename = csv_path.name
	i = inotify.adapters.Inotify()
	i.add_watch(str(parent))
	try:
		for event in i.event_gen(yield_nones=False):
			_, type_names, _, fname = event
			if fname == filename and ("IN_MODIFY" in type_names or "IN_CLOSE_WRITE" in type_names):
				callback()
	finally:
		i.remove_watch(str(parent))
		i.close()

def watch_poll(csv_path, callback):
	"""Fallback: poll file size/mtime."""
	last_stat = (0, 0)
	while True:
		try:
			st = csv_path.stat()
			cur_stat = (st.st_size, int(st.st_mtime))
			if cur_stat != last_stat:
				last_stat = cur_stat
				callback()
		except OSError:
			pass
		time.sleep(POLL_INTERVAL)

def main():
	args = parse_args()
	ensure_data_dir(args.csv)

	def render():
		state = read_csv(args.csv)
		metrics = compute_metrics(state)
		view = build_view(state, metrics)
		draw(view)

	render()

	if not args.watch:
		return 0

	if HAS_INOTIFY:
		try:
			watch_inotify(args.csv, render)
		except (OSError, PermissionError):
			watch_poll(args.csv, render)
	else:
		watch_poll(args.csv, render)

	return 0

if __name__ == "__main__":
	sys.exit(main())
