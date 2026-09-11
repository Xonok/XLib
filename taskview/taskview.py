#!/usr/bin/env python3
"""
taskview — Read-only task display for tmux pane.
Reads append-only CSV from ~/.local/share/taskview/tasks.csv

Pipeline: main → parse_args → ensure_data_dir → render → read_csv → load_filter → filter_tasks → compute_metrics → build_view → draw
Watch modes: inotify (primary) → poll (fallback)
"""

import argparse,csv,os,signal,shutil,sys,time,yaml
from datetime import datetime,timedelta
from pathlib import Path

try:
	import inotify.adapters
	HAS_INOTIFY = True
except ImportError:
	HAS_INOTIFY = False

DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "taskview"
DEFAULT_CSV = DEFAULT_DATA_DIR / "tasks.csv"
DEFAULT_FILTER_DIR = DEFAULT_DATA_DIR / "filters"
POLL_INTERVAL = 1.0
DEFAULT_WIDTH = shutil.get_terminal_size().columns or 80

_CLEAR_SCREEN = "\033[2J\033[H"

# Built-in global tags (always active, no config needed)
_ALWAYS_SHOW_TAGS = {"critical", "emergency"}
_NEVER_SHOW_TAGS = {"cancelled", "archived"}

def main() -> int:
	args = parse_args()
	ensure_data_dir(args.csv)
	ensure_filter_dir()

	# Resolve context
	context_name = args.context or os.environ.get("TASKVIEW_CONTEXT", "default")
	filter_path = DEFAULT_FILTER_DIR / f"{context_name}.yaml"
	if not filter_path.exists():
		sys.stderr.write(f"taskview: filter file not found: {filter_path}\n")
		sys.stderr.write(f"taskview: create it or use --context with an existing filter\n")
		return 1

	# Mutable state for watch mode
	filter_data = load_filter(filter_path)

	def render():
		nonlocal filter_data
		state = read_csv(args.csv)
		# Reload filter if mtime changed
		try:
			current_mtime = filter_path.stat().st_mtime
			if current_mtime != filter_data.get("_mtime", 0):
				filter_data = load_filter(filter_path)
				filter_data["_mtime"] = current_mtime
		except OSError:
			pass
		filtered = filter_tasks(state, filter_data)
		metrics = compute_metrics(state, filter_data, filtered)
		view = build_view(filtered, metrics, filter_data)
		draw(view)

	render()

	if not args.watch:
		return 0

	if HAS_INOTIFY:
		try:
			_watch_inotify(args.csv, filter_path, render)
		except Exception:
			_watch_poll(args.csv, filter_path, render)
	else:
		_watch_poll(args.csv, filter_path, render)

	return 0

def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Display condensed task view")
	parser.add_argument(
		"--csv",
		type=Path,
		default=DEFAULT_CSV,
		help="Path to tasks.csv (default: ~/.local/share/taskview/tasks.csv)",
	)
	parser.add_argument(
		"--context",
		default=None,
		help="Context name (loads filters/<name>.yaml, default: 'default' or TASKVIEW_CONTEXT)",
	)
	parser.add_argument(
		"--watch",
		action="store_true",
		help="Watch for changes and redraw",
	)
	return parser.parse_args()

def ensure_data_dir(path):
	path.parent.mkdir(parents=True, exist_ok=True)

def ensure_filter_dir():
	DEFAULT_FILTER_DIR.mkdir(parents=True, exist_ok=True)
	# Create default.yaml from example if it doesn't exist
	default_filter = DEFAULT_FILTER_DIR / "default.yaml"
	if not default_filter.exists():
		example = Path(__file__).parent / "default.yaml.example"
		if example.exists():
			shutil.copy2(example, default_filter)
		else:
			# Fallback: write minimal default
			default_filter.write_text(
				"label: \"Default\"\n"
				"tags:\n"
				"  - \"work\"\n"
				"  - \"personal\"\n"
				"  - \"admin\"\n"
				"  - \"learning\"\n"
				"  - \"house\"\n"
				"  - \"health\"\n"
				"  - \"hobby\"\n"
				"limits:\n"
				"  upcoming: 10\n"
				"  queue_breakdown: true\n"
			)

def load_filter(path):
	"""Load and parse a filter YAML file."""
	with path.open("r", encoding="utf-8") as f:
		data = yaml.safe_load(f) or {}

	# Ensure required fields with defaults
	label = data.get("label", path.stem)
	tags = data.get("tags", [])
	if not isinstance(tags, list):
		tags = []
	limits = data.get("limits", {})
	upcoming = limits.get("upcoming", 5)
	queue_breakdown = limits.get("queue_breakdown", True)

	return {
		"label": label,
		"tags": set(tags),
		"limits": {
			"upcoming": upcoming,
			"queue_breakdown": queue_breakdown,
		},
		"_mtime": path.stat().st_mtime,
	}

def read_csv(path):
	"""Read and fold CSV into current state per task id.

	Skips // comments and header row. Last-write-wins by id.
	New columns: category (5), tags (6), importance (7) — backward compatible.
	"""
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
				if row[0] == "id":
					continue
				if len(row) < 5:
					continue
				try:
					task_id = int(row[0])
					status = row[1]
					title = row[2]
					due_ts = int(row[3]) if row[3] else None
					chg_ts = int(row[4])

					# New columns (backward compatible: missing = empty)
					category = row[5] if len(row) > 5 and row[5] else ""
					tags_str = row[6] if len(row) > 6 and row[6] else ""
					importance = row[7] if len(row) > 7 and row[7] else ""

					# Parse tags column: comma-separated, stripped, filtered empty
					tags = set()
					if tags_str:
						for tag in tags_str.split(","):
							t = tag.strip()
							if t:
								tags.add(t)

					state[task_id] = {
						"id": task_id,
						"status": status,
						"title": title,
						"due_ts": due_ts,
						"chg_ts": chg_ts,
						"category": category,
						"tags": tags,
						"importance": importance,
					}
				except (ValueError, IndexError):
					continue
	except OSError as e:
		sys.stderr.write(f"taskview: failed to read {path}: {e}\n")
	return state

def filter_tasks(state, filter_data):
	"""Apply filter evaluation logic to folded state, returning ALL tasks that pass.

	Order:
	1. never_show: task has 'cancelled' or 'archived' tag → exclude
	2. always_show: task has 'critical' or 'emergency' tag → include
	3. context filter: task tags overlap filter tags → include
	4. otherwise → exclude

	Returns dict of task_id -> task for ALL statuses that pass filter.
	"""
	filter_tags = filter_data["tags"]
	filtered = {}

	for task_id, task in state.items():
		task_tags = task["tags"]

		# 1. never_show (built-in)
		if task_tags & _NEVER_SHOW_TAGS:
			continue

		# 2. always_show (built-in)
		if task_tags & _ALWAYS_SHOW_TAGS:
			filtered[task_id] = task
			continue

		# 3. context filter (OR logic: any overlap → include)
		if filter_tags and not (task_tags & filter_tags):
			continue

		filtered[task_id] = task

	return filtered

def compute_metrics(state, filter_data, filtered):
	"""Compute pace and queue metrics from *filtered* tasks (all statuses).

	Args:
		state: full folded state (all tasks)
		filter_data: parsed filter config
		filtered: dict of task_id -> task for tasks that pass filter (all statuses)

	Returns dict with keys:
		done_day (int): tasks completed today (calendar day) from filtered
		done_week (int): tasks completed in last 7 days (rolling) from filtered
		done_month (int): tasks completed in last 30 days (rolling) from filtered
		active (int): open tasks in filtered set
		this_week (int): open filtered tasks due this week
		this_month (int): open filtered tasks due this month
		later (int): open filtered tasks due later or no due date
		open_tasks (list): open filtered tasks sorted by due_ts, then chg_ts desc
		shown (int): count of open filtered tasks
		filtered_total (int): total open tasks in state minus shown (i.e., filtered out)
	"""
	now = time.time()
	today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
	week_ago = now - 7 * 86400
	month_ago = now - 30 * 86400

	done_day = 0
	done_week = 0
	done_month = 0
	active_count = 0
	open_tasks = []

	for task in filtered.values():
		status = task["status"]
		if status == "done":
			ts = task["chg_ts"]
			if ts >= today_start:
				done_day += 1
			if ts >= week_ago:
				done_week += 1
			if ts >= month_ago:
				done_month += 1
		elif status == "open":
			active_count += 1
			open_tasks.append(task)
		elif status == "cancelled":
			pass

	# Sort by due date (soonest first), then by chg_ts (most recent first) as tiebreaker
	# Tasks with no due date go to the end
	def sort_key(t):
		due = t["due_ts"]
		if due is None:
			return (float("inf"), -t["chg_ts"])
		return (due, -t["chg_ts"])

	open_tasks.sort(key=sort_key)

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

	# Count open tasks excluded by context filter (not never_show, not always_show, no tag overlap)
	filter_tags = filter_data["tags"]
	filtered_out = 0
	for task in state.values():
		if task["status"] != "open":
			continue
		task_tags = task["tags"]
		# Skip never_show (globally excluded, not "filtered by context")
		if task_tags & _NEVER_SHOW_TAGS:
			continue
		# Skip always_show (bypasses context filter)
		if task_tags & _ALWAYS_SHOW_TAGS:
			continue
		# Count if doesn't match context filter
		if filter_tags and not (task_tags & filter_tags):
			filtered_out += 1

	shown = len(open_tasks)
	filtered_total = filtered_out

	return {
		"done_day": done_day,
		"done_week": done_week,
		"done_month": done_month,
		"active": active_count,
		"this_week": this_week,
		"this_month": this_month,
		"later": later,
		"open_tasks": open_tasks,
		"shown": shown,
		"filtered_total": filtered_total,
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
	# Use calendar day difference (date only) for "today"/"tomorrow"
	due_date = dt.date()
	now_date = now.date()
	day_diff = (due_date - now_date).days
	if day_diff < 0:
		return f"overdue {abs(day_diff)}d"
	if day_diff == 0:
		return "today"
	if day_diff == 1:
		return "tomorrow"
	if day_diff < 7:
		return f"{day_diff}d"
	return dt.strftime("%m-%d")

def truncate(text, width):
	if len(text) <= width:
		return text
	return text[: max(0, width - 1)] + "..."

def pick_current(open_tasks):
	"""Pick the task shown as "now": the most urgent open task — the one with
	the soonest due date, overdue first. open_tasks is already sorted by
	(due_ts, -chg_ts) with no-due last, so pick the first element.
	Returns None for an empty list.
	"""
	if not open_tasks:
		return None
	return open_tasks[0]

def build_view(filtered, metrics, filter_data, width=DEFAULT_WIDTH):
	lines = []
	label = filter_data["label"]
	lines.append(f"=== Tasks ({label}) ===")
	lines.append("")

	open_tasks = metrics["open_tasks"]

	# Current task: soonest due today-or-later; most overdue if all overdue
	current = pick_current(open_tasks)
	if current:
		lines.append(f"▸ {current['title']}")
		due_str = fmt_due(current["due_ts"])
		chg_str = fmt_time(current["chg_ts"])
		lines.append(f"  {chg_str}  ·  due: {due_str}")
		lines.append("")
	else:
		lines.append("▸ (no open tasks)")
		lines.append("")

	# Upcoming: next open tasks from filtered set, respect limits.upcoming
	limits = filter_data["limits"]
	upcoming_limit = limits["upcoming"]

	lines.append("UPCOMING")
	if len(open_tasks) > 1:
		# Exclude the current task (same pick as above)
		upcoming = [t for t in open_tasks if t["id"] != current["id"]]
		for task in upcoming[:upcoming_limit]:
			due_str = fmt_due(task["due_ts"])
			lines.append(f" · {truncate(task['title'], width - 4)}  ({due_str})")
	else:
		lines.append(" · (none)")
	lines.append("")

	lines.append("PACE")
	lines.append(f" Day:  {metrics['done_day']} done, {metrics['active']} active")
	lines.append(f" Week: {metrics['done_week']} done")
	lines.append(f" Month: {metrics['done_month']} done")
	lines.append("")

	# Queue breakdown
	total = metrics["this_week"] + metrics["this_month"] + metrics["later"]
	shown = metrics["shown"]
	filtered_count = metrics["filtered_total"]
	if limits["queue_breakdown"]:
		lines.append("QUEUE")
		lines.append(
			f" {total} tasks remaining "
			f"({metrics['this_week']} this week, {metrics['this_month']} this month, {metrics['later']} later) "
			f"({shown} shown, {filtered_count} filtered)"
		)
	else:
		lines.append("QUEUE")
		lines.append(f" {total} tasks remaining ({shown} shown, {filtered_count} filtered)")

	return "\n".join(lines)

def draw(view):
	sys.stdout.write(_CLEAR_SCREEN)
	sys.stdout.write(view)
	sys.stdout.flush()

def _watch_inotify(csv_path, filter_path, callback):
	"""Watch both CSV and filter file using inotify, call callback on change."""
	csv_parent = csv_path.parent
	csv_filename = csv_path.name
	filter_parent = filter_path.parent
	filter_filename = filter_path.name

	i = inotify.adapters.Inotify()
	i.add_watch(str(csv_parent))
	if filter_parent != csv_parent:
		i.add_watch(str(filter_parent))

	try:
		for event in i.event_gen(yield_nones=False):
			_, type_names, _, fname = event
			if fname == csv_filename and ("IN_MODIFY" in type_names or "IN_CLOSE_WRITE" in type_names):
				callback()
			elif fname == filter_filename and ("IN_MODIFY" in type_names or "IN_CLOSE_WRITE" in type_names):
				callback()
	finally:
		i.remove_watch(str(csv_parent))
		if filter_parent != csv_parent:
			i.remove_watch(str(filter_parent))
		i.close()

def _watch_poll(csv_path, filter_path, callback):
	"""Fallback: poll both file size/mtime."""
	last_csv_stat = (0, 0)
	last_filter_stat = (0, 0)
	while True:
		try:
			csv_st = csv_path.stat()
			cur_csv_stat = (csv_st.st_size, int(csv_st.st_mtime))
			if cur_csv_stat != last_csv_stat:
				last_csv_stat = cur_csv_stat
				callback()
		except OSError as e:
			sys.stderr.write(f"taskview: poll error on {csv_path}: {e}\n")

		try:
			filter_st = filter_path.stat()
			cur_filter_stat = (filter_st.st_size, int(filter_st.st_mtime))
			if cur_filter_stat != last_filter_stat:
				last_filter_stat = cur_filter_stat
				callback()
		except OSError as e:
			sys.stderr.write(f"taskview: poll error on {filter_path}: {e}\n")

		time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
	signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
	signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
	sys.exit(main())
