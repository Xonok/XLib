import argparse,glob,json,os,time,sys

EPIQ_HOME = os.environ.get("EPIQ_HOME_OVERRIDE") or os.path.expanduser("~/.epiq-global")

DEFAULT_STALE_SECONDS = 300
CREATING_KINDS = frozenset({"add.issue", "add.board", "add.swimlane"})
REFERENCING_KINDS = frozenset({"move.node", "close.issue", "add.issue.tag",
	"add.issue.comment", "edit.description", "edit.title"})

def sys_stderr(msg: str) -> None:
	sys.stderr.write("%s\n" % msg)

def _event_dirs():
	"""Return {project_id: events_dir} for every epiq project state worktree."""
	dirs = {}
	for path in sorted(glob.glob(os.path.join(EPIQ_HOME, "worktrees", "*", ".epiq", "events"))):
		dirs[os.path.basename(os.path.dirname(os.path.dirname(path)))] = path
	return dirs

def _read_events(path):
	"""Yield parsed events from a jsonl file, skipping unparseable lines."""
	try:
		with open(path) as f:
			for line in f:
				line = line.strip()
				if not line:
					continue
				try:
					yield json.loads(line)
				except ValueError:
					continue
	except OSError:
		return

def _kind(event):
	"""The event's operation name, e.g. 'add.issue'. Events carry it as a key."""
	others = [k for k in event if k not in ("v", "id")]
	return others[0] if others else ""

def _event_id(event):
	"""The event's own id, the first element of its [self, parent] pair."""
	ids = event.get("id") or []
	return tuple(ids) if isinstance(ids, list) else (ids,)

def _target(event):
	"""The issue or node an event acts on.

	`add.issue.comment` carries both its own comment `id` and the `issue` it
	belongs to, so `issue` wins — otherwise every comment looks like a reference
	to a never-created object.
	"""
	body = event.get(_kind(event)) or {}
	for field in ("issue", "id", "node"):
		if field in body:
			return body[field]
	return None

def _issue_titles(events_dir: str) -> dict:
	"""Map issue id to title, reading pending files too — a stranded creation still names its ticket."""
	titles = {}
	for path in sorted(glob.glob(os.path.join(events_dir, "*.jsonl"))):
		for event in _read_events(path):
			if _kind(event) != "add.issue":
				continue
			body = event.get("add.issue") or {}
			if body.get("id") and body.get("name"):
				titles[body["id"]] = body["name"]
	return titles

def _scan_project(events_dir):
	"""Return (committed_ids, created_nodes, referenced_nodes, pending_files).

	`nodes` is everything addressable on the board — issues, boards and
	swimlanes — because `move.node` addresses all three and a reference to any of
	them is only an orphan if its creation is missing.
	"""
	committed = set()
	created = set()
	referenced = set()
	pending = []
	for path in sorted(glob.glob(os.path.join(events_dir, "*.jsonl"))):
		name = os.path.basename(path)
		if name.startswith("."):
			continue
		if "~pending" in name:
			pending.append(path)
			continue
		for event in _read_events(path):
			committed.add(_event_id(event))
			kind = _kind(event)
			if kind in CREATING_KINDS:
				created.add(_target(event))
			elif kind in REFERENCING_KINDS:
				referenced.add(_target(event))
	return committed, created, referenced, pending

def _age_seconds(path: str) -> int:
	return max(0, int(time.time() - os.path.getmtime(path)))

def _age(seconds: int) -> str:
	for size, unit in ((86400, "d"), (3600, "h"), (60, "m")):
		if seconds >= size:
			return "%d%s" % (seconds // size, unit)
	return "%ds" % seconds

def _pending_report(events_dir: str, committed: set, stale_seconds: int) -> tuple:
	"""List pending files with undrained events, split by whether they still look live.

	A pending file younger than `stale_seconds` belongs to a process that may be
	about to sync it, so it is reported as in-flight and does not fail the check.
	An older one is stranded: nothing will drain it except a new session running
	as that actor. Counting the live case would mean the check failed on every
	session that had done any board work, and a check that always fails is
	ignored — which is the failure it exists to prevent.
	"""
	stranded, inflight = [], []
	for path in sorted(glob.glob(os.path.join(events_dir, "*~pending*.jsonl"))):
		events = list(_read_events(path))
		undrained = [e for e in events if _event_id(e) not in committed]
		if not undrained:
			continue
		age = _age_seconds(path)
		row = {"actor": os.path.basename(path).split("~")[0], "path": path,
			"age": _age(age), "age_seconds": age, "total": len(events),
			"stranded": len(undrained), "kinds": sorted({_kind(e) for e in undrained}),
			"created": sorted({_target(e) for e in undrained if _kind(e) == "add.issue"
				and _target(e)})}
		(inflight if age < stale_seconds else stranded).append(row)
	return stranded, inflight

def _print_rows(rows: list, heading: str, note: str, titles: dict) -> None:
	if not rows:
		return
	print("  %s" % heading)
	for row in rows:
		print("    %d/%d events  actor %s  last written %s ago"
			% (row["stranded"], row["total"], row["actor"], row["age"]))
		print("      %s" % ", ".join(row["kinds"]))
		for issue_id in row["created"]:
			title = titles.get(issue_id)
			print("      created only here: %s%s"
				% (issue_id, "  %s" % title if title else "  (title unknown)"))
		print("      %s" % row["path"])
	print("    %s" % note)

def cmd_epiq_pending(args: argparse.Namespace) -> None:
	dirs = _event_dirs()
	if not dirs:
		sys_stderr("no epiq state worktrees under %s" % EPIQ_HOME)
		raise SystemExit(2)
	if args.repo:
		dirs = {pid: d for pid, d in dirs.items()
			if pid == args.repo or args.repo in d}
	problems = 0
	for pid, events_dir in dirs.items():
		committed, created, referenced, pending = _scan_project(events_dir)
		stranded, inflight = _pending_report(events_dir, committed, args.stale_seconds)
		orphans = sorted(referenced - created)
		if not stranded and not orphans:
			if inflight:
				print("epiq project %s: no stranded events (%d events in flight, not yet synced)"
					% (pid, sum(r["stranded"] for r in inflight)))
			elif args.verbose:
				print("%s: clean" % pid)
			continue
		problems += 1
		print("epiq project %s  (%s)" % (pid, events_dir))
		titles = _issue_titles(events_dir)
		_print_rows(stranded, "STRANDED — no running process will drain these:",
			"draining needs a session running as the actor, which the board refuses",
			titles)
		_print_rows(inflight, "in flight (under %ds old, counted clean):" % args.stale_seconds,
			"a live process owns these; a sync from that actor commits them", titles)
		for orphan in orphans:
			print("  ORPHAN reference: %s is referenced by committed events but never created in one" % orphan)
			print("    a clone of this state branch cannot resolve it")
		print("")
	if not problems:
		print("clean")
		return
	print("%d epiq project(s) with stranded events" % problems)
	print("epiq_sync drains only the calling actor's own log, so these persist until a")
	print("session runs as each actor above — and epiq_actor_assume refuses a name the")
	print("server was not launched with. See AGENTS.md, 'epiq writes are per-actor'.")
	raise SystemExit(1)

def main() -> None:
	parser = argparse.ArgumentParser(prog="epiq-pending",
		description="report epiq events stranded in pending files, and board nodes that committed events reference but never committed a creation for")
	parser.add_argument("--repo", default=None, help="only this epiq project id or worktree path")
	parser.add_argument("--stale-seconds", type=int, default=DEFAULT_STALE_SECONDS,
		help="a pending file younger than this is treated as in flight, not stranded (default: %d)" % DEFAULT_STALE_SECONDS)
	parser.add_argument("--verbose", action="store_true", help="print a line per clean project too")
	cmd_epiq_pending(parser.parse_args())

if __name__ == "__main__":
	main()
