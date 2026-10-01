#!/usr/bin/env python3
"""
taskview — Project-specific task display for tmux pane.
Reads append-only CSV and a per-project .taskview.yaml filter file.

Pipeline: main → parse_args → resolve_data_dir → resolve_csv → render loop
→ read_csv → resolve_filter → load_filter → select_tasks
→ compute_metrics → build_view → draw
Watch modes: inotify (primary) → poll (fallback)
"""

import argparse,csv,os,signal,sys,time,yaml
from datetime import datetime,timedelta
from pathlib import Path

try:
	import inotify.adapters
	HAS_INOTIFY = True
except ImportError:
	HAS_INOTIFY = False

POLL_INTERVAL = 1.0

_CLEAR_SCREEN = "\033[2J\033[H"

# Built-in never-show tags (Rule 1)
_NEVER_SHOW_TAGS = {"cancelled", "archived"}
# Built-in always-show tags (Rule 3) — bypass tag rule only, not category
_ALWAYS_SHOW_TAGS = {"critical", "emergency"}

class FilterError(Exception):
	"""Raised by load_filter on unreadable or malformed YAML."""
	pass

def resolve_data_dir(explicit: Path | None, environ: dict) -> Path:
	"""R17: --data-dir, else $TASKVIEW_DATA_DIR, else $XDG_DATA_HOME/taskview, else ~/.local/share/taskview."""
	if explicit is not None:
		return explicit
	if "TASKVIEW_DATA_DIR" in environ:
		return Path(environ["TASKVIEW_DATA_DIR"])
	# Check passed environ first, then fall back to os.environ for test isolation
	xdg = environ.get("XDG_DATA_HOME") or os.environ.get("XDG_DATA_HOME")
	if xdg:
		return Path(xdg) / "taskview"
	return Path.home() / ".local" / "share" / "taskview"

def resolve_csv(data_dir: Path, explicit: Path | None) -> Path:
	"""R18: --csv wins, else <data-dir>/tasks.csv."""
	if explicit is not None:
		return explicit
	return data_dir / "tasks.csv"

def load_filter(path: Path | str) -> dict:
	"""
	Load and parse a filter YAML file.
	R6: Recognised keys with defaults.
	R7: Unknown keys warn on stderr.
	R8: Malformed YAML raises FilterError.
	Returns dict with keys: label, categories (set), tags (set), include_bucket (bool),
	limits{upcoming, queue_breakdown}, _path.
	"""
	path = Path(path)
	try:
		with path.open("r", encoding="utf-8") as f:
			data = yaml.safe_load(f) or {}
	except yaml.YAMLError as e:
		raise FilterError(f"malformed YAML in {path}: {e}") from e
	except OSError as e:
		raise FilterError(f"cannot read {path}: {e}") from e

	# R7: warn on unknown keys
	recognised = {"label", "categories", "tags", "include_bucket", "limits"}
	for key in data:
		if key not in recognised:
			sys.stderr.write(f"taskview: unknown key '{key}' in {path}\n")

	label = data.get("label", path.stem)

	categories = data.get("categories", [])
	if not isinstance(categories, list):
		categories = []
	categories = set(categories)

	tags = data.get("tags", [])
	if not isinstance(tags, list):
		tags = []
	tags = set(tags)

	include_bucket = bool(data.get("include_bucket", False))

	limits = data.get("limits", {})
	upcoming = limits.get("upcoming", 5)
	if not isinstance(upcoming, int):
		upcoming = 5
	queue_breakdown = bool(limits.get("queue_breakdown", True))

	return {
		"label": label,
		"categories": categories,
		"tags": tags,
		"include_bucket": include_bucket,
		"limits": {
			"upcoming": upcoming,
			"queue_breakdown": queue_breakdown,
		},
		"_path": path,
	}

def discover_filter(start: Path) -> Path | None:
	"""
	R9 rule 2, R10, R11: Walk up from resolved cwd to filesystem root.
	First .taskview.yaml wins. Returns None if none found.
	No git, no $HOME stop.
	"""
	current = start.resolve()
	while True:
		candidate = current / ".taskview.yaml"
		if candidate.is_file():
			return candidate
		parent = current.parent
		if parent == current:  # reached filesystem root
			return None
		current = parent

def resolve_filter(cwd: Path, explicit: Path | None, no_filter: bool) -> tuple[Path | None, dict | None, str]:
	"""
	R9, R9a, R13: Resolve filter path and load it.
	Returns (path, filter_data, source) where source is one of:
	"explicit", "discovered", "none", "flag".
	filter_data is None unless source is "explicit" or "discovered".
	"""
	if no_filter:
		return (None, None, "flag")

	if explicit is not None:
		try:
			filter_data = load_filter(explicit)
			return (explicit, filter_data, "explicit")
		except FilterError:
			raise

	discovered = discover_filter(cwd)
	if discovered is not None:
		try:
			filter_data = load_filter(discovered)
			return (discovered, filter_data, "discovered")
		except FilterError:
			raise

	return (None, None, "none")

def select_tasks(state: dict, filter_data: dict | None) -> dict:
	"""
	R14-R16: Select tasks by the five rules, in order.
	Returns dict of task_id -> task for tasks of ANY status that pass.
	A None filter passes everything except R16 rule 1 (never-show).
	"""
	if filter_data is None:
		# No filter: only never-show excludes
		result = {}
		for task_id, task in state.items():
			if task["tags"] & _NEVER_SHOW_TAGS:
				continue
			result[task_id] = task
		return result

	filter_categories = filter_data["categories"]
	filter_tags = filter_data["tags"]
	include_bucket = filter_data["include_bucket"]

	result = {}
	for task_id, task in state.items():
		task_tags = task["tags"]
		task_category = task["category"]

		# Rule 1: never-show tags exclude unconditionally
		if task_tags & _NEVER_SHOW_TAGS:
			continue

		# Rule 2: category not accepted by filter → exclude
		if filter_categories:
			if task_category == "":
				if not include_bucket:
					continue
			elif task_category not in filter_categories:
				continue

		# Rule 3: always-show tags (critical/emergency) include, bypassing tag rule only
		if task_tags & _ALWAYS_SHOW_TAGS:
			result[task_id] = task
			continue

		# Rule 4: filter tags non-empty and no overlap → exclude
		if filter_tags and not (task_tags & filter_tags):
			continue

		# Rule 5: otherwise include
		result[task_id] = task

	return result

def compute_metrics(state: dict, selected: dict, filter_data: dict | None) -> dict:
	"""
	R25, R26: Compute pace and queue metrics from selected tasks (all statuses).
	Keys: done_day, done_week, done_month, active, this_week, this_month, later,
	open_tasks, shown, filtered_total.
	`selected` is every status that passed the filter; `shown` and `filtered_total`
	count OPEN tasks only.
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

	for task in selected.values():
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

	# R25: S + F = open tasks not excluded by rule 1
	# shown = open tasks in selected
	# filtered_total = open tasks in state not in selected and not excluded by rule 1
	shown = len(open_tasks)

	# Count open tasks excluded by filter (rules 2-4), but not rule 1
	if filter_data is None:
		filtered_total = 0
	else:
		filter_categories = filter_data["categories"]
		filter_tags = filter_data["tags"]
		include_bucket = filter_data["include_bucket"]

		filtered_total = 0
		for task in state.values():
			if task["status"] != "open":
				continue
			task_tags = task["tags"]
			# Skip never-show (rule 1) — not counted as "filtered by this view"
			if task_tags & _NEVER_SHOW_TAGS:
				continue
			# Check if this task is in selected
			if task["id"] in selected:
				continue
			# It's an open task, not never-show, not selected → filtered by this view
			filtered_total += 1

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

def fmt_time(ts: int | None) -> str:
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

def fmt_due(ts: int | None) -> str:
	if ts is None:
		return "no due"
	dt = datetime.fromtimestamp(ts)
	now = datetime.now()
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

def truncate(text: str, width: int) -> str:
	"""
	Shorten text to fit width, marking the cut with an ellipsis. Never returns
	more than width characters, so a caller can subtract a prefix (an id, say)
	from its budget and rely on the line still fitting.
	"""
	if width <= 0:
		return ""
	if len(text) <= width:
		return text
	if width <= 3:
		return text[:width]
	return text[:width - 3] + "..."

def task_label(task: dict, budget: int) -> str:
	"""
	R42: the id, then as much of the title as `budget` allows. The id is the
	handle a task is referred by — `taskupdate.py show <id>` resolves it — so it
	is shown rather than left implicit, and the title's budget is reduced by the
	prefix width so the title is not shortened by adding the id.

	A budget too small for the id itself drops the title rather than overflowing
	the line: a pane wraps badly long before a task becomes unnameable, and an
	id with no title is still a usable reference.
	"""
	prefix = f"#{task['id']} "
	if len(prefix) > budget:
		return truncate(prefix.rstrip(), budget)
	return prefix + truncate(task["title"], budget - len(prefix))

def pick_current(open_tasks: list) -> dict | None:
	"""Pick the task shown as 'now': the most urgent open task."""
	if not open_tasks:
		return None
	return open_tasks[0]

def build_view(selected: dict, metrics: dict, filter_data: dict | None, width: int, source: str) -> str:
	"""
	R24, R26, R26a, R27: Pure render function.
	Header chosen by source: explicit/discovered → label, none → "no filter found", flag → "no filter".
	"""
	lines = []

	# R24: three distinguishable header states
	if source in ("explicit", "discovered") and filter_data is not None:
		label = filter_data["label"]
		lines.append(f"=== Tasks ({label}) ===")
	elif source == "none":
		lines.append("=== Tasks (no filter found — showing all) ===")
	elif source == "flag":
		lines.append("=== Tasks (no filter) ===")
	else:
		# Should not happen, but fallback
		lines.append("=== Tasks ===")
	lines.append("")

	open_tasks = metrics["open_tasks"]

	# Current task
	current = pick_current(open_tasks)
	if current:
		lines.append(f"▸ {task_label(current, width - 2)}")
		due_str = fmt_due(current["due_ts"])
		chg_str = fmt_time(current["chg_ts"])
		lines.append(f"  {chg_str}  ·  due: {due_str}")
		lines.append("")
	else:
		lines.append("▸ (no open tasks)")
		lines.append("")

	# Upcoming
	limits = filter_data["limits"] if filter_data else {"upcoming": 5, "queue_breakdown": True}
	upcoming_limit = limits["upcoming"]

	lines.append("UPCOMING")
	if len(open_tasks) > 1:
		upcoming = [t for t in open_tasks if t["id"] != current["id"]]
		for task in upcoming[:upcoming_limit]:
			due_str = fmt_due(task["due_ts"])
			# R42: the " · " lead (3) and the "  (due)" tail (len + 4, the two
			# spaces and two parentheses) come off the width, and the id comes off
			# the title's share rather than the line's. When what is left cannot
			# hold a label and a due together, the due is dropped rather than the
			# line overflowing — a wrapped line in a narrow pane breaks the
			# alignment of every line under it.
			tail = len(due_str) + 4
			with_due = width - 3 - tail
			label = task_label(task, with_due)
			if label.strip() and with_due >= len(f"#{task['id']}"):
				lines.append(f" · {label}  ({due_str})")
			else:
				lines.append(f" · {task_label(task, width - 3)}")
	else:
		lines.append(" · (none)")
	lines.append("")

	# PACE
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

def watch_targets(csv_path: Path, filter_path: Path | None) -> list[Path]:
	"""R22: The CSV plus the resolved filter file if there is one, de-duplicated."""
	targets = [csv_path]
	if filter_path is not None:
		if filter_path not in targets:
			targets.append(filter_path)
	return targets

def read_csv(path: Path) -> dict:
	"""
	R33, R34: Read and fold CSV into current state per task id.
	Skips // comments and header row. Last-write-wins by id.
	Missing trailing columns read as empty. Bad id/chg_ts skips row.
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
				except (ValueError, IndexError):
					continue

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
	except OSError as e:
		sys.stderr.write(f"taskview: failed to read {path}: {e}\n")
	return state

def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Display condensed task view")
	parser.add_argument(
		"--csv",
		type=Path,
		default=None,
		help="Path to tasks.csv (default: <data-dir>/tasks.csv)",
	)
	parser.add_argument(
		"--data-dir",
		type=Path,
		default=None,
		help="Data directory (default: $TASKVIEW_DATA_DIR or $XDG_DATA_HOME/taskview or ~/.local/share/taskview)",
	)
	parser.add_argument(
		"--filter",
		type=Path,
		default=None,
		help="Explicit filter file path",
	)
	parser.add_argument(
		"--no-filter",
		action="store_true",
		help="Skip filter discovery and apply no filter",
	)
	parser.add_argument(
		"--watch",
		action="store_true",
		help="Watch for changes and redraw",
	)
	parser.add_argument(
		"--width",
		type=int,
		default=None,
		help="Terminal width override",
	)
	return parser.parse_args()

def main() -> int:
	args = parse_args()

	# Resolve data directory and CSV path
	data_dir = resolve_data_dir(args.data_dir, os.environ)
	csv_path = resolve_csv(data_dir, args.csv)

	# Resolve filter
	filter_path, filter_data, source = resolve_filter(Path.cwd(), args.filter, args.no_filter)

	# Mutable state for watch mode
	current_filter_data = filter_data
	current_filter_path = filter_path
	current_source = source

	def render():
		nonlocal current_filter_data, current_filter_path, current_source
		state = read_csv(csv_path)

		# Reload filter if mtime changed (for watch mode)
		if current_filter_path is not None:
			try:
				current_mtime = current_filter_path.stat().st_mtime
				if current_mtime != current_filter_data.get("_mtime", 0):
					current_filter_data = load_filter(current_filter_path)
					current_filter_data["_mtime"] = current_mtime
			except OSError:
				# Filter file deleted or unreadable — re-run discovery (R23)
				current_filter_path, current_filter_data, current_source = resolve_filter(
					Path.cwd(), args.filter, args.no_filter
				)
				if current_filter_path is not None:
					sys.stderr.write(f"taskview: filter reloaded from {current_filter_path}\n")
				else:
					sys.stderr.write("taskview: filter file lost, showing all\n")

		selected = select_tasks(state, current_filter_data)
		metrics = compute_metrics(state, selected, current_filter_data)
		view = build_view(selected, metrics, current_filter_data, args.width or 80, current_source)
		draw(view)

	render()

	if not args.watch:
		return 0

	if HAS_INOTIFY:
		try:
			_watch_inotify(csv_path, current_filter_path, render)
		except Exception:
			_watch_poll(csv_path, current_filter_path, render)
	else:
		_watch_poll(csv_path, current_filter_path, render)

	return 0

def draw(view: str):
	sys.stdout.write(_CLEAR_SCREEN)
	sys.stdout.write(view)
	sys.stdout.flush()

def _watch_inotify(csv_path: Path, filter_path: Path | None, callback):
	"""Watch both CSV and filter file using inotify, call callback on change."""
	csv_parent = csv_path.parent
	csv_filename = csv_path.name

	i = inotify.adapters.Inotify()
	i.add_watch(str(csv_parent))

	filter_watched = False
	filter_filename = None
	if filter_path is not None:
		filter_parent = filter_path.parent
		filter_filename = filter_path.name
		if filter_parent != csv_parent:
			i.add_watch(str(filter_parent))
			filter_watched = True

	try:
		for event in i.event_gen(yield_nones=False):
			_, type_names, _, fname = event
			if fname == csv_filename and ("IN_MODIFY" in type_names or "IN_CLOSE_WRITE" in type_names):
				callback()
			elif filter_filename is not None and fname == filter_filename and ("IN_MODIFY" in type_names or "IN_CLOSE_WRITE" in type_names):
				callback()
	finally:
		i.remove_watch(str(csv_parent))
		if filter_watched:
			i.remove_watch(str(filter_path.parent))
		i.close()

def _watch_poll(csv_path: Path, filter_path: Path | None, callback):
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

		if filter_path is not None:
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

