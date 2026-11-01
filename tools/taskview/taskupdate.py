#!/usr/bin/env python3
"""
taskupdate — Append-only task state updates for taskview.
Writes to tasks.csv resolved via R30: --csv > $TASKVIEW_CSV > <data-dir>/tasks.csv
"""

import argparse,csv,datetime,os,sys,time
from pathlib import Path

_here = Path(__file__).resolve().parent
_root = _here.parent.parent
for _p in (str(_root), str(_root / "tools")):
	if _p not in sys.path:
		sys.path.insert(0, _p)

try:
	from tools.taskview.taskview import resolve_data_dir,resolve_csv
	from tools.taskview.vocab import VocabError,check_category,check_tags,load_vocab,normalise_tags,normalise_value
except ImportError:
	from taskview import resolve_data_dir,resolve_csv
	from vocab import VocabError,check_category,check_tags,load_vocab,normalise_tags,normalise_value

# Kept for backwards compatibility with existing tests that mock it
DEFAULT_CSV = Path.home() / ".local" / "share" / "taskview" / "tasks.csv"
FIELDNAMES = ["id", "status", "title", "due_ts", "chg_ts", "category", "tags", "importance", "description", "queued_on"]

CANONICAL_HEADER = ",".join(FIELDNAMES)
CANONICAL_SCHEMA_COMMENT = "// Schema: " + ",".join(FIELDNAMES)

def _is_header_line(line):
	"""True if line is the field-name header row (not a comment)."""
	s = line.strip()
	if not s or s.startswith("//"):
		return False
	return s.split(",", 1)[0].strip().strip('"') == "id"

def ensure_csv(path):
	path.parent.mkdir(parents=True, exist_ok=True)
	if not path.exists():
		with path.open("w", encoding="utf-8", newline="") as f:
			f.write("// tasks.csv — append-only, last-write-wins by id\n")
			f.write(CANONICAL_SCHEMA_COMMENT + "\n")
			f.write(CANONICAL_HEADER + "\n")
		return
	# Self-heal: rewrite a stale header/schema-comment line in an existing file.
	# Metadata only — rows are never touched here (see migrate for full normalization).
	try:
		with path.open("r", encoding="utf-8", newline="") as f:
			lines = f.readlines()
	except OSError:
		return
	changed = False
	out = []
	for line in lines:
		if _is_header_line(line):
			if line.rstrip("\r\n") != CANONICAL_HEADER:
				eol = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
				out.append(CANONICAL_HEADER + eol)
				changed = True
				continue
		stripped = line.strip()
		if stripped.startswith("// Schema:"):
			if stripped != CANONICAL_SCHEMA_COMMENT:
				eol = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
				out.append(CANONICAL_SCHEMA_COMMENT + eol)
				changed = True
				continue
		out.append(line)
	if changed:
		with path.open("w", encoding="utf-8", newline="") as f:
			f.writelines(out)

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

def append_row(path, task_id, status, title, due_ts, chg_ts, category="", tags="", importance="", description="", queued_on=""):
	ensure_csv(path)
	with path.open("a", encoding="utf-8", newline="") as f:
		writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
		writer.writerow([task_id, status, title or "", due_ts or "", chg_ts, category or "", tags or "", importance or "", escape_description(description or ""), queued_on or ""])
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
					"queued_on": row[9] if len(row) > 9 else "",
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
					"queued_on": row[9] if len(row) > 9 else "",
				}
	return state

def fmt_due(ts: int | None, today: datetime.date | None = None) -> str:
	"""Human form of a due timestamp, in taskview's pane wording.

	`today` pins the reference day so the board can word dates around its own
	`now`, and so a test does not depend on the wall clock; omitted, it reads
	the wall clock. The far-date form is `%m-%d`, which is what the pane shows
	seven or more days out — the two tools word a date identically.
	"""
	if not ts:
		return "no due"
	try:
		due_date = datetime.datetime.fromtimestamp(int(ts)).date()
	except (ValueError, OSError, OverflowError):
		return f"unparseable due ({ts})"
	reference = today or datetime.date.today()
	day_diff = (due_date - reference).days
	if day_diff < 0:
		return f"overdue {abs(day_diff)}d"
	if day_diff == 0:
		return "today"
	if day_diff == 1:
		return "tomorrow"
	if day_diff < 7:
		return f"{day_diff}d"
	return due_date.strftime("%m-%d")

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

def clean_category(category: str, vocab: dict | None) -> str:
	"""The category in house spelling; exits 1 when the vocabulary refuses it."""
	category = normalise_value(category)
	refusal = check_category(category, vocab)
	if refusal:
		print(refusal, file=sys.stderr)
		sys.exit(1)
	return category

def clean_tags(tags: str, vocab: dict | None) -> str:
	"""The tag list in house spelling, de-duplicated; exits 1 when refused."""
	tags = normalise_tags(tags)
	refusal = check_tags(tags, vocab)
	if refusal:
		print(refusal, file=sys.stderr)
		sys.exit(1)
	return tags

def clean_queued_on(value: str) -> str:
	"""Normalise a --queued-on argument to a stored task id (or '' to clear)."""
	if value is None:
		return ""
	if value.strip().lower() in ("", "none"):
		return ""
	try:
		return str(int(value))
	except ValueError:
		print(f"Invalid queued-on value: {value}", file=sys.stderr)
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

def normalize_row(row):
	"""Pad/truncate a data row to the canonical field count."""
	row = list(row)
	if len(row) < len(FIELDNAMES):
		row = row + [""] * (len(FIELDNAMES) - len(row))
	elif len(row) > len(FIELDNAMES):
		row = row[:len(FIELDNAMES)]
	return row

def migrate_csv(path, apply=False):
	"""Report (and optionally repair) mixed-format tasks.csv files.

	AQQNPAN: the file may carry several row widths (legacy 5-column rows
	alongside the current 10-column schema) and a stale header line. This
	command reports the field-count distribution and, with --apply, rewrites
	the file so the header is canonical and every data row is padded to the
	canonical width. Comments are preserved as the two leading lines.
	"""
	if not path.exists():
		print(f"taskupdate migrate: no file at {path}")
		return 0
	with path.open("r", encoding="utf-8", newline="") as f:
		reader = csv.reader(f)
		rows = list(reader)
	# Separate leading comments/header from data rows
	leading = []
	data = []
	for r in rows:
		if not r:
			continue
		if r[0].startswith("//"):
			leading.append(r)
			continue
		if r and r[0].strip().strip('"') == "id" and len(r) <= len(FIELDNAMES):
			# header row
			leading.append(r)
			continue
		data.append(r)

	from collections import Counter
	widths = Counter(len(r) for r in data)
	header_stale = True
	# detect header among leading
	header_lines = [r for r in leading if r and r[0].strip().strip('"') == "id"]
	header_stale = (not header_lines) or (header_lines[-1] != FIELDNAMES)

	print(f"taskupdate migrate: {path}")
	print(f"  data rows: {len(data)}")
	print(f"  field widths: " + ", ".join(f"{w}={n}" for w, n in sorted(widths.items())))
	print(f"  header stale: {header_stale}")

	if not apply:
		print("  dry run — pass --apply to rewrite")
		return 0

	# Rewrite
	backup = path.with_suffix(path.suffix + ".bak")
	try:
		if not backup.exists():
			import shutil
			shutil.copy2(path, backup)
	except OSError:
		pass

	with path.open("w", encoding="utf-8", newline="") as f:
		f.write("// tasks.csv — append-only, last-write-wins by id\n")
		f.write(CANONICAL_SCHEMA_COMMENT + "\n")
		f.write(CANONICAL_HEADER + "\n")
		writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
		for r in data:
			writer.writerow(normalize_row(r))
	print("  applied: file normalized")
	return 0

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
	p_add.add_argument("--queued-on", default=None, help="Task id this task is queued behind (or 'none' to clear)")
	p_upd = sub.add_parser("update", help="Update existing task (by id)")
	p_upd.add_argument("id", type=int)
	p_upd.add_argument("--status", choices=["open", "done", "cancelled"])
	p_upd.add_argument("--title")
	p_upd.add_argument("--due", help="Due date (timestamp or YYYY-MM-DD)")
	p_upd.add_argument("--category", default=None)
	p_upd.add_argument("--tags", default=None)
	p_upd.add_argument("--importance", default=None, choices=["low", "medium", "high", ""])
	p_upd.add_argument("--description", default=None)
	p_upd.add_argument("--keep-chg-ts", action="store_true", help="Keep the task's current change time (a correction, not a change)")
	p_upd.add_argument("--queued-on", default=None, help="Task id this task is queued behind (or 'none' to clear)")

	p_done = sub.add_parser("done", help="Mark task done")
	p_done.add_argument("id", type=int)

	p_cancel = sub.add_parser("cancel", help="Mark task cancelled")
	p_cancel.add_argument("id", type=int)

	p_show = sub.add_parser("show", help="Show one task by id")
	p_show.add_argument("id", type=int)
	p_show.add_argument("--field", help="Print just this field (id, status, title, due_ts, chg_ts, category, tags, importance, description, queued_on)")

	p_list = sub.add_parser("list", help="List tasks, id first")
	p_list.add_argument("--status", help="Only tasks with this status (default: all)")
	p_list.add_argument("--category", help="Only tasks in this category")

	p_mig = sub.add_parser("migrate", help="Report/repair mixed-format tasks.csv (AQQNPAN)")
	p_mig.add_argument("--apply", action="store_true", help="Rewrite the file normalized (default: dry run)")

	args = parser.parse_args()
	now = int(time.time())

	# Resolve CSV path per R30
	csv_path = resolve_csv_path(args)

	vocab = None
	if args.cmd in ("add", "update"):
		try:
			vocab = load_vocab()
		except VocabError as e:
			print(f"taskupdate: {e}", file=sys.stderr)
			sys.exit(1)
	if args.cmd == "add":
		task_id = read_last_id(csv_path) + 1
		due_ts = parse_due(args.due) if args.due else ""
		category = clean_category(args.category, vocab) if args.category else ""
		tags = clean_tags(args.tags, vocab) if args.tags else ""
		queued_on = clean_queued_on(args.queued_on) if args.queued_on is not None else ""
		append_row(csv_path, task_id, args.status, args.title, due_ts, now, category, tags, args.importance, args.description, queued_on)

	elif args.cmd == "update":
		if (args.status is None and args.title is None and args.due is None
			and args.category is None and args.tags is None and args.importance is None and args.description is None and args.queued_on is None):
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
		queued_on = current["queued_on"] if "queued_on" in current else ""
		if args.queued_on is not None:
			queued_on = clean_queued_on(args.queued_on)
		if args.category is not None:
			category = clean_category(args.category, vocab)
		if args.tags is not None:
			tags = clean_tags(args.tags, vocab)
		chg_ts = current["chg_ts"] if args.keep_chg_ts else now
		append_row(csv_path, args.id, status, title, due_ts, chg_ts, category, tags, importance, description, queued_on)

	elif args.cmd == "done":
		current = read_task(csv_path, args.id)
		if not current:
			print(f"Task {args.id} not found", file=sys.stderr)
			sys.exit(1)
		append_row(csv_path, args.id, "done", current["title"], current["due_ts"], now, current["category"], current["tags"], current["importance"], current["description"], current.get("queued_on", ""))

	elif args.cmd == "cancel":
		current = read_task(csv_path, args.id)
		if not current:
			print(f"Task {args.id} not found", file=sys.stderr)
			sys.exit(1)
		append_row(csv_path, args.id, "cancelled", current["title"], current["due_ts"], now, current["category"], current["tags"], current["importance"], current["description"], current.get("queued_on", ""))

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
			print(f"  queued_on:   {current.get('queued_on') or '(none)'}")

	elif args.cmd == "list":
		state = read_all(csv_path) if csv_path.exists() else {}
		rows_out = []
		for task_id in sorted(state):
			t = state[task_id]
			if args.status and t["status"] != args.status:
				continue
			if args.category and t["category"] != normalise_value(args.category):
				continue
			rows_out.append(t)
		if not rows_out:
			print("No matching tasks", file=sys.stderr)
			sys.exit(1)
		for t in rows_out:
			due = fmt_due(t["due_ts"]) if t["due_ts"] else "no due"
			print(f"#{t['id']}  {t['status']:<9}  {due:<12}  {t['title']}")

	elif args.cmd == "migrate":
		migrate_csv(csv_path, apply=args.apply)

if __name__ == "__main__":
	main()
