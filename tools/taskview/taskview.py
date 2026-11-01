#!/usr/bin/env python3
"""
taskview — Project-specific task display for tmux pane.
Reads append-only CSV and a per-project .taskview.yaml filter file.

Pipeline: main → parse_args → resolve_data_dir → resolve_csv → render loop
→ read_csv → resolve_filter → load_filter → select_tasks
→ compute_metrics → build_view → draw
Watch modes: inotify (primary) → poll (fallback)
Terminal contract: TERMINAL.md
"""

import argparse,contextlib,csv,ctypes,os,select,signal,struct,sys,termios,time,yaml
from datetime import datetime,timedelta
from pathlib import Path
import shutil

POLL_INTERVAL = 1.0
REFRESH_INTERVAL = 60.0
_CLEAR_SCREEN = "\033[2J\033[H"
_ENTER_WATCH = "\033[?25l\033[?1049h"
_LEAVE_WATCH = "\033[?25h\033[?1049l"
_EVENT_HEADER = struct.Struct("=iIII")
_IN_MODIFY = 0x00000002
_IN_CLOSE_WRITE = 0x00000008
_IN_MOVED_TO = 0x00000080
_IN_CREATE = 0x00000100
_IN_DELETE = 0x00000200
_IN_DELETE_SELF = 0x00000400
_IN_MOVE_SELF = 0x00000800
_WATCH_MASK = _IN_MODIFY | _IN_CLOSE_WRITE | _IN_MOVED_TO | _IN_CREATE | _IN_DELETE | _IN_DELETE_SELF | _IN_MOVE_SELF
try:
	_libc = ctypes.CDLL(None, use_errno=True)
	_libc.inotify_init.restype = ctypes.c_int
	_libc.inotify_init.argtypes = []
	_libc.inotify_add_watch.restype = ctypes.c_int
	_libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
	HAS_INOTIFY = True
except AttributeError:
	_libc = None
	HAS_INOTIFY = False
_resize_pending = False

def _handle_sigwinch(signum, frame):
	"""R50: redraw on terminal resize."""
	global _resize_pending
	_resize_pending = True

@contextlib.contextmanager
def _fullscreen():
	"""Watch mode owns the pane: no cursor, and no scrollback of old frames."""
	_stdin_fd = None
	_old_attrs = None
	if sys.stdin.isatty():
		try:
			_stdin_fd = sys.stdin.fileno()
			_old_attrs = termios.tcgetattr(_stdin_fd)
			_new_attrs = termios.tcgetattr(_stdin_fd)
			_new_attrs[3] &= ~(termios.ECHO | getattr(termios, "ECHOCTL", 0))
			termios.tcsetattr(_stdin_fd, termios.TCSANOW, _new_attrs)
		except (termios.error, OSError, AttributeError):
			_stdin_fd = None
			_old_attrs = None
	sys.stdout.write(_ENTER_WATCH)
	sys.stdout.flush()
	try:
		yield
	finally:
		if _old_attrs is not None and _stdin_fd is not None:
			try:
				termios.tcsetattr(_stdin_fd, termios.TCSANOW, _old_attrs)
			except (termios.error, OSError):
				pass
		sys.stdout.write(_LEAVE_WATCH)
		sys.stdout.flush()

class _Inotify:
	"""The file changes in the watched directories, read from inotify itself.

	No third-party package: the syscall is the interface, and a missing one
	is the only reason the caller falls back to polling.
	"""

	def __init__(self):
		if _libc is None:
			raise OSError("inotify is not available")
		self.fd = _libc.inotify_init()
		if self.fd == -1:
			raise OSError(ctypes.get_errno(), "inotify_init failed")
		self.dirs = {}

	def add(self, path):
		"""Watch one directory; a failure is the caller's cue to poll."""
		wd = _libc.inotify_add_watch(self.fd, os.fsencode(path), _WATCH_MASK)
		if wd == -1:
			raise OSError(ctypes.get_errno(), "inotify_add_watch failed")
		self.dirs[wd] = Path(path)

	def read(self, timeout):
		"""The (mask, path) changes in the next `timeout` seconds, if any."""
		ready, _, _ = select.select([self.fd], [], [], timeout)
		if not ready:
			return []
		raw = os.read(self.fd, 65536)
		events = []
		offset = 0
		while offset < len(raw):
			wd, mask, _, namelen = _EVENT_HEADER.unpack_from(raw, offset)
			offset += _EVENT_HEADER.size
			name = raw[offset:offset + namelen].split(b"\0", 1)[0]
			offset += (namelen + 3) & ~3
			base = self.dirs.get(wd)
			if base is not None:
				events.append((mask, base / os.fsdecode(name) if name else base))
		return events

	def close(self):
		"""Release the descriptor and every watch on it."""
		if self.fd != -1:
			os.close(self.fd)
			self.fd = -1

# Built-in never-show tags (Rule 1)
_NEVER_SHOW_TAGS = {"cancelled", "archived"}

def _is_queued(task: dict, state: dict) -> bool:
	"""A task is queued (hidden) when it waits on a task that is not done or cancelled."""
	dep = task.get("queued_on")
	if not dep:
		return False
	dep_task = state.get(dep)
	if dep_task is None:
		return False
	return dep_task.get("status") not in ("done", "cancelled")
# Built-in always-show tags (Rule 3) — bypass tag rule only, not category
_ALWAYS_SHOW_TAGS = {"critical", "emergency"}

# R28: height thresholds that select how many detail tasks are shown.
# Full height (>= _FULL_HEIGHT lines): 2 most urgent tasks in full detail.
# Medium height (>= _MEDIUM_HEIGHT): 1 most urgent task in full detail.
# Below _MEDIUM_HEIGHT: 0 detail tasks; every open task goes to UPCOMING.
_FULL_HEIGHT = 22
_MEDIUM_HEIGHT = 14
# R28: fixed lines the layout spends regardless of detail content —
# header(2) + blank after detail(1) + UPCOMING header(1) + blank after
# UPCOMING(1) + PACE(5) + QUEUE(2) = 12. The detail body minimum (2 lines
# per task: title + due, plus 1 between tasks) and the UPCOMING rows are the
# variable parts that shrink or grow with the terminal height.
_FIXED_OVERHEAD = 12
# R50: below this, even the header + PACE + QUEUE do not fit together, so the
# renderer falls back to the header and the queue total alone.
_MINIMUM_HEIGHT = 9

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
		if parent == current: # reached filesystem root
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

def select_tasks(state: dict, filter_data: dict | None, show_queued: bool = False) -> dict:
	"""
	R14-R16: Select tasks by the five rules, in order.
	Returns dict of task_id -> task for tasks of ANY status that pass.
	A None filter passes everything except R16 rule 1 (never-show).
	"""
	if filter_data is None:
		# No filter: only never-show and queued (unresolved) excludes
		result = {}
		for task_id, task in state.items():
			if task["tags"] & _NEVER_SHOW_TAGS:
				continue
			if not show_queued and _is_queued(task, state):
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

		# Queued (unresolved dependency) tasks are hidden unless --show-queued
		if not show_queued and _is_queued(task, state):
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
			# Skip queued (unresolved) — not counted as "filtered by this view"
			if _is_queued(task, state):
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

def get_terminal_size(width_override: int | None = None) -> tuple[int, int]:
	"""
	R20: Terminal width is read at render time, and --width N overrides it.
	Height is also read at render time for the condensed list sizing.
	Returns (width, height). Falls back to 80x24 if unavailable.
	"""
	if width_override is not None:
		width = width_override
	else:
		width = 80
	height = 24
	try:
		size = shutil.get_terminal_size()
		if width_override is None:
			width = size.columns
		height = size.lines
	except OSError:
		pass
	return (width, height)

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

def pick_detail_tasks(open_tasks: list, height: int) -> list:
	"""Pick the most urgent open tasks for the detail view, adapting to height.

	R28: returns the 2 most urgent tasks at full height (height >= _FULL_HEIGHT),
	1 at medium height (height >= _MEDIUM_HEIGHT), and 0 at very limited
	height (all open tasks go to the condensed UPCOMING list instead).
	Returns an empty list when there are no open tasks, or when the pane is
	too short for any detail block.
	"""
	if not open_tasks:
		return []
	if height >= _FULL_HEIGHT:
		return open_tasks[:2]
	if height >= _MEDIUM_HEIGHT:
		return open_tasks[:1]
	# Very limited: no room for a detail block — every task appears in UPCOMING.
	return []

def describe_lines(text: str, width: int, max_lines: int) -> list[str]:
	"""Wrap *text* to *width* and return at most *max_lines* lines.

	When the wrapped text exceeds *max_lines*, the last visible line is cut to
	make room for an ellipsis (``...``), signalling that content follows which
	did not fit. R30a.
	"""
	if max_lines <= 0:
		return []
	all_lines = wrap_text(text, width)
	if len(all_lines) <= max_lines:
		return all_lines
	# Keep the first max_lines-1 lines unchanged; the last gets a marker.
	kept = list(all_lines[:max_lines - 1])
	last = all_lines[max_lines - 1]
	if width <= 3:
		kept.append("..."[:max(0, width)])
	else:
		kept.append(last[:width - 3] + "...")
	return kept

def _fit(lines: list[str], height: int) -> list[str]:
	"""R50: trim the view to the pane height. Last sections go first."""
	return lines[:max(0, height)]

def _header_lines(source: str, filter_data: dict | None) -> list[str]:
	"""R24: the header line chosen by source."""
	if source in ("explicit", "discovered") and filter_data is not None:
		return [f"=== Tasks ({filter_data['label']}) ==="]
	if source == "none":
		return ["=== Tasks (no filter found — showing all) ==="]
	if source == "flag":
		return ["=== Tasks (no filter) ==="]
	return ["=== Tasks ==="]

def _pace_lines(metrics: dict) -> list[str]:
	"""R27: the PACE block."""
	return [
		"PACE",
		f" Day: {metrics['done_day']} done, {metrics['active']} active",
		f" Week: {metrics['done_week']} done",
		f" Month: {metrics['done_month']} done",
	]

def _queue_lines(metrics: dict, limits: dict) -> list[str]:
	"""R27: the queue total, broken down by when it is due when the filter allows."""
	total = metrics["this_week"] + metrics["this_month"] + metrics["later"]
	shown = metrics["shown"]
	filtered = metrics["filtered_total"]
	if limits["queue_breakdown"]:
		breakdown = (
			f"({metrics['this_week']} this week, {metrics['this_month']} this month, "
			f"{metrics['later']} later) "
		)
	else:
		breakdown = ""
	return ["QUEUE", f" {total} tasks remaining {breakdown}({shown} shown, {filtered} filtered)"]

def _upcoming_line(task: dict, width: int) -> str:
	"""R42: one condensed UPCOMING row, never wider than *width*."""
	due_str = fmt_due(task["due_ts"])
	# R42: the " · " lead (3) and the "  (due)" tail (len + 4, the two spaces
	# and two parentheses) come off the width, and the id comes off the title's
	# share rather than the line's. When what is left cannot hold a label and a
	# due together, the due is dropped rather than the line overflowing — a
	# wrapped line in a narrow pane breaks the alignment of every line under it.
	tail = len(due_str) + 4
	with_due = width - 3 - tail
	label = task_label(task, with_due)
	if label.strip() and with_due >= len(f"#{task['id']}"):
		return f" · {label}  ({due_str})"
	return f" · {task_label(task, width - 3)}"

def build_view(selected: dict, metrics: dict, filter_data: dict | None, width: int, height: int, source: str) -> str:
	"""
	R24, R26, R26a, R27, R28, R29, R30, R30a, R50: Pure render function.
	Header chosen by source: explicit/discovered → label, none → "no filter found",
	flag → "no filter".  The result never has more lines than *height*.

	The view is built full, then sections are dropped while it overflows, in the
	order the human asked for: PACE first, QUEUE second, UPCOMING third, the
	header last.  UPCOMING gives up its rows from the bottom before its header
	goes, so a short pane keeps as many tasks on screen as it has room for.
	"""
	if height <= 0:
		return ""
	open_tasks = metrics["open_tasks"]
	limits = filter_data["limits"] if filter_data else {"upcoming": 5, "queue_breakdown": True}

	# R28: detail tasks adapt to terminal height — 2 at full height, 1 at
	# medium height, 0 at very limited (all open tasks go to UPCOMING).
	detail_tasks = pick_detail_tasks(open_tasks, height)
	detail_count = len(detail_tasks)

	# R28, R30a: description line budgets.  _FIXED_OVERHEAD covers the lines the
	# layout spends whatever the detail content is; the detail body minimum is
	# 2 lines per task (title + due) plus 1 between tasks.
	detail_body_min = detail_count * 2 + max(0, detail_count - 1)
	budget = height - _FIXED_OVERHEAD - detail_body_min
	desc_counts = [
		len(wrap_text(task["description"], width - 4)) if task.get("description") else 0
		for task in detail_tasks
	]
	if budget >= sum(desc_counts):
		desc_budgets = desc_counts
	else:
		# Not enough room: truncate descriptions first (greedy, first task gets
		# priority).  R30a.
		desc_budgets = []
		remaining = max(0, budget)
		for count in desc_counts:
			alloc = min(count, remaining)
			desc_budgets.append(alloc)
			remaining -= alloc

	detail_section = []
	for i, task in enumerate(detail_tasks):
		if i > 0:
			detail_section.append("") # blank line between detail blocks
		detail_section.append(f"▸ {task_label(task, width - 2)}")
		due_str = fmt_due(task["due_ts"])
		chg_str = fmt_time(task["chg_ts"])
		detail_section.append(f"  {chg_str}  ·  due: {due_str}")
		if desc_budgets[i] > 0:
			for dl in describe_lines(task["description"], width - 4, desc_budgets[i]):
				detail_section.append(f"  {dl}")
	if not open_tasks:
		detail_section.append("▸ (no open tasks)")

	# R29: UPCOMING rows.  `limits.upcoming` is the number reserved for; spare
	# lines at the end of the layout go to more rows (see the fill step below).
	remaining_tasks = [t for t in open_tasks if t not in detail_tasks]
	upcoming_rows = [_upcoming_line(task, width) for task in remaining_tasks[:limits["upcoming"]]]
	if open_tasks and not upcoming_rows:
		none_text = " · (none)"
		if len(none_text) > width:
			none_text = truncate(none_text, width)
		upcoming_rows.append(none_text)

	# R50: the drop chain.  Each block knows its own lines; a block is dropped
	# whole, and UPCOMING additionally loses rows from the bottom first.
	keep_pace = True
	keep_queue = True
	keep_upcoming = bool(upcoming_rows)
	keep_header = True
	compact = False
	header_lines = _header_lines(source, filter_data)
	pace_lines = _pace_lines(metrics)
	queue_lines = _queue_lines(metrics, limits)

	def render() -> list[str]:
		blocks = []
		if keep_header:
			blocks.append(header_lines)
		if detail_section:
			blocks.append(detail_section)
		if keep_upcoming and upcoming_rows:
			blocks.append(["UPCOMING"] + upcoming_rows)
		if keep_pace:
			blocks.append(pace_lines)
		if keep_queue:
			blocks.append(queue_lines)
		lines = []
		for block in blocks:
			if lines and not compact:
				lines.append("")
			lines.extend(block)
		return lines

	view = render()
	if len(view) > height:
		keep_pace = False
		view = render()
	if len(view) > height:
		keep_queue = False
		view = render()
	if len(view) > height:
		# Blank separators are the cheapest thing to give up.
		compact = True
		view = render()
	while len(view) > height and upcoming_rows:
		upcoming_rows.pop()
		view = render()
	# R29: a section header with no rows under it says nothing.
	if not upcoming_rows or len(view) > height:
		keep_upcoming = False
		view = render()
	if len(view) > height:
		keep_header = False
		view = render()

	# R50: use the lines that are left.  Whatever the drop chain freed goes back
	# to UPCOMING rows — the filter's `upcoming` count is the number the layout
	# reserves, not a ceiling that leaves the pane half empty.
	spare = height - len(view)
	if spare > 0 and keep_upcoming and remaining_tasks:
		shown = len(upcoming_rows)
		for task in remaining_tasks[shown:shown + spare]:
			upcoming_rows.append(_upcoming_line(task, width))
		view = render()
	return "\n".join(truncate(line, width) for line in _fit(view, height))

def wrap_text(text: str, width: int) -> list[str]:
	"""Wrap text to fit within width, returning list of lines.
	Preserves explicit newlines as paragraph breaks; wraps long lines.
	"""
	if width <= 0:
		return [text]
	# Split on actual newlines first to preserve paragraph structure
	paragraphs = text.split('\n')
	lines = []
	for para in paragraphs:
		if not para:
			# Empty paragraph → blank line
			lines.append("")
			continue
		words = para.split()
		if not words:
			lines.append("")
			continue
		current = ""
		for word in words:
			if len(current) + len(word) + (1 if current else 0) <= width:
				current = (current + " " + word) if current else word
			else:
				lines.append(current)
				current = word
		if current:
			lines.append(current)
	return lines

def watch_targets(csv_path: Path, filter_path: Path | None) -> list[Path]:
	"""R22: The CSV plus the resolved filter file if there is one, de-duplicated."""
	targets = [csv_path]
	if filter_path is not None:
		if filter_path not in targets:
			targets.append(filter_path)
	return targets

def unescape_description(text: str) -> str:
	"""Unescape newlines in description from CSV storage."""
	return text.replace("\\n", "\n")

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
				description = unescape_description(row[8] if len(row) > 8 and row[8] else "")
				queued_raw = row[9] if len(row) > 9 and row[9] else ""
				try:
					queued_on = int(queued_raw) if queued_raw else None
				except (ValueError, TypeError):
					queued_on = None

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
					"description": description,
					"queued_on": queued_on,
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
		"--show-queued",
		action="store_true",
		help="Show tasks queued behind an unresolved dependency (hidden by default)",
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

	signal.signal(signal.SIGWINCH, _handle_sigwinch)

	def render():
		global _resize_pending
		nonlocal current_filter_data, current_filter_path, current_source
		_resize_pending = False
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

		selected = select_tasks(state, current_filter_data, show_queued=args.show_queued)
		metrics = compute_metrics(state, selected, current_filter_data)
		width, height = get_terminal_size(args.width)
		view = build_view(selected, metrics, current_filter_data, width, height, current_source)
		draw(view)

	if not args.watch:
		render()
		return 0

	with _fullscreen():
		render()
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
	targets = [csv_path]
	filter_parent = None
	if filter_path is not None:
		targets.append(filter_path)
		if filter_path.parent != csv_parent:
			filter_parent = filter_path.parent

	watcher = _Inotify()
	try:
		watcher.add(csv_parent)
		if filter_parent is not None:
			watcher.add(filter_parent)
	except OSError:
		watcher.close()
		raise

	last_refresh = time.monotonic()
	try:
		while True:
			now = time.monotonic()
			changed = False
			for mask, path in watcher.read(POLL_INTERVAL):
				if path in targets and mask & (_IN_MODIFY | _IN_CLOSE_WRITE | _IN_MOVED_TO | _IN_CREATE):
					changed = True
			if changed:
				callback()
				last_refresh = now
				continue
			if _resize_pending:
				callback()
				last_refresh = time.monotonic()
				continue
			if now - last_refresh >= REFRESH_INTERVAL:
				callback()
				last_refresh = now
	finally:
		watcher.close()

def _watch_poll(csv_path: Path, filter_path: Path | None, callback):
	"""Fallback: poll both file size/mtime."""
	last_csv_stat = (0, 0)
	last_filter_stat = (0, 0)
	last_refresh = time.monotonic()
	while True:
		now = time.monotonic()
		changed = False
		try:
			csv_st = csv_path.stat()
			cur_csv_stat = (csv_st.st_size, int(csv_st.st_mtime))
			if cur_csv_stat != last_csv_stat:
				last_csv_stat = cur_csv_stat
				changed = True
		except OSError as e:
			sys.stderr.write(f"taskview: poll error on {csv_path}: {e}\n")

		if not changed and filter_path is not None:
			try:
				filter_st = filter_path.stat()
				cur_filter_stat = (filter_st.st_size, int(filter_st.st_mtime))
				if cur_filter_stat != last_filter_stat:
					last_filter_stat = cur_filter_stat
					changed = True
			except OSError as e:
				sys.stderr.write(f"taskview: poll error on {filter_path}: {e}\n")

		if changed or _resize_pending or now - last_refresh >= REFRESH_INTERVAL:
			callback()
			last_refresh = time.monotonic()
		time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
	signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
	signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
	sys.exit(main())
