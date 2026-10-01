import json,os,shutil,subprocess,sys,tempfile,time
sys.path.insert(0, "dev/xtest")
import xtest
TOOL = "tools/epiq-pending.py"

def _event(event_id: str, parent: str, **fields) -> str:
	return json.dumps({"v": 1, "id": [event_id, parent], **fields})

def _events_dir(root: str, project: str) -> str:
	"""Create the state-worktree layout epiq-pending reads, and return its events dir."""
	events = os.path.join(root, "worktrees", project, ".epiq", "events")
	os.makedirs(events)
	return events

def _age_file(path: str, seconds: int = 7200) -> None:
	"""Backdate a file, so a fixture pending file reads as stranded rather than in flight."""
	stamp = time.time() - seconds
	os.utime(path, (stamp, stamp))

def _write(path: str, lines: list) -> None:
	with open(path, "w") as f:
		f.write("\n".join(lines) + "\n")

def _clean_project(root: str) -> str:
	"""A project whose committed log is self-consistent and has no pending file."""
	events = _events_dir(root, "01CLEAN")
	_write(os.path.join(events, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jsonl"), [
		_event("e1", "e0", **{"add.issue": {"id": "ISSUE1", "name": "first", "parent": "L"}}),
		_event("e2", "e1", **{"move.node": {"id": "ISSUE1", "parent": "L"}}),
		_event("e3", "e2", **{"add.issue.comment": {"id": "COMMENT1", "issue": "ISSUE1", "md": "hi"}}),
	])
	return events

def _run(root: str, *args: str) -> tuple:
	"""Run the tool with EPIQ_HOME pointed at a fixture root; return (exit code, output)."""
	env = dict(os.environ, EPIQ_HOME_OVERRIDE=root)
	proc = subprocess.run([sys.executable, TOOL, *args], capture_output=True, text=True, env=env)
	return proc.returncode, proc.stdout + proc.stderr

def test_reports_clean_when_nothing_stranded():
	root = tempfile.mkdtemp()
	try:
		_clean_project(root)
		code, out = _run(root)
		xtest.equal(code, 0)
		xtest.contains("clean", out)
	finally:
		shutil.rmtree(root)

def test_reports_orphan_when_creation_never_committed():
	root = tempfile.mkdtemp()
	try:
		events = _clean_project(root)
		with open(os.path.join(events, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jsonl"), "a") as f:
			f.write(_event("e4", "e3", **{"move.node": {"id": "ISSUE2", "parent": "L"}}) + "\n")
		code, out = _run(root)
		xtest.equal(code, 1)
		xtest.contains("ISSUE2", out)
		xtest.contains("ORPHAN", out)
	finally:
		shutil.rmtree(root)

def test_reports_orphan_when_creation_only_pending():
	"""The real failure: the add.issue never committed, but a move.node did."""
	root = tempfile.mkdtemp()
	try:
		events = _clean_project(root)
		with open(os.path.join(events, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jsonl"), "a") as f:
			f.write(_event("e4", "e3", **{"move.node": {"id": "ISSUE3", "parent": "L"}}) + "\n")
		path = os.path.join(events, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb~pending.jsonl")
		_write(path, [_event("p1", "p0", **{"add.issue": {"id": "ISSUE3", "name": "lost", "parent": "L"}})])
		_age_file(path)
		code, out = _run(root)
		xtest.equal(code, 1)
		xtest.contains("ISSUE3", out)
		xtest.contains("1/1 events", out)
		xtest.contains("STRANDED", out)
	finally:
		shutil.rmtree(root)

def test_drained_pending_file_is_not_stranded():
	"""A pending file whose events are all committed is leftover, not loss."""
	root = tempfile.mkdtemp()
	try:
		events = _clean_project(root)
		path = os.path.join(events, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb~pending.jsonl")
		_write(path, [_event("e1", "e0", **{"add.issue": {"id": "ISSUE1", "name": "first", "parent": "L"}})])
		_age_file(path)
		code, out = _run(root)
		xtest.equal(code, 0)
		xtest.not_equal("STRANDED" in out, True)
	finally:
		shutil.rmtree(root)

def test_comment_id_is_not_mistaken_for_an_issue():
	"""add.issue.comment carries its own id; that must not read as an orphan reference."""
	root = tempfile.mkdtemp()
	try:
		events = _clean_project(root)
		with open(os.path.join(events, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jsonl"), "a") as f:
			f.write(_event("e4", "e3", **{"add.issue.comment": {"id": "COMMENT2", "issue": "ISSUE1", "md": "x"}}) + "\n")
		code, out = _run(root)
		xtest.equal(code, 0)
		xtest.not_equal("COMMENT2" in out, True)
	finally:
		shutil.rmtree(root)

def test_board_and_swimlane_ids_are_not_orphans():
	"""move.node addresses boards and lanes too; their creations count."""
	root = tempfile.mkdtemp()
	try:
		events = _clean_project(root)
		with open(os.path.join(events, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jsonl"), "a") as f:
			f.write(_event("e4", "e3", **{"add.board": {"id": "BOARD1", "name": "b", "parent": "P"}}) + "\n")
			f.write(_event("e5", "e4", **{"move.node": {"id": "BOARD1", "parent": "P"}}) + "\n")
			f.write(_event("e6", "e5", **{"add.swimlane": {"id": "LANE1", "name": "l", "parent": "BOARD1"}}) + "\n")
			f.write(_event("e7", "e6", **{"move.node": {"id": "LANE1", "parent": "BOARD1"}}) + "\n")
		code, out = _run(root)
		xtest.equal(code, 0)
		xtest.not_equal("ORPHAN" in out, True)
	finally:
		shutil.rmtree(root)

def test_unparseable_line_is_skipped_not_fatal():
	root = tempfile.mkdtemp()
	try:
		events = _clean_project(root)
		with open(os.path.join(events, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jsonl"), "a") as f:
			f.write("{not json\n")
		code, out = _run(root)
		xtest.equal(code, 0)
	finally:
		shutil.rmtree(root)

def test_recent_pending_counts_as_in_flight_not_stranded():
	"""A live process's own unsynced writes must not fail the check."""
	root = tempfile.mkdtemp()
	try:
		events = _clean_project(root)
		_write(os.path.join(events, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb~pending.jsonl"), [
			_event("p1", "p0", **{"add.issue": {"id": "ISSUE4", "name": "mine", "parent": "L"}}),
		])
		code, out = _run(root)
		xtest.equal(code, 0)
		xtest.contains("in flight", out)
		xtest.not_equal("STRANDED" in out, True)
	finally:
		shutil.rmtree(root)

def test_old_pending_is_stranded_and_fails():
	"""Same file, aged past the threshold: now it is loss, and the check fails."""
	root = tempfile.mkdtemp()
	try:
		events = _clean_project(root)
		path = os.path.join(events, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb~pending.jsonl")
		_write(path, [_event("p1", "p0", **{"add.issue": {"id": "ISSUE4", "name": "mine", "parent": "L"}})])
		old = time.time() - 7200
		os.utime(path, (old, old))
		code, out = _run(root)
		xtest.equal(code, 1)
		xtest.contains("STRANDED", out)
		xtest.contains("ISSUE4", out)
	finally:
		shutil.rmtree(root)

def test_stale_seconds_is_configurable():
	root = tempfile.mkdtemp()
	try:
		events = _clean_project(root)
		path = os.path.join(events, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb~pending.jsonl")
		_write(path, [_event("p1", "p0", **{"add.issue": {"id": "ISSUE4", "name": "x", "parent": "L"}})])
		old = time.time() - 60
		os.utime(path, (old, old))
		code, out = _run(root, "--stale-seconds", "5")
		xtest.equal(code, 1)
		xtest.contains("STRANDED", out)
	finally:
		shutil.rmtree(root)

def test_repo_filter_restricts_to_one_project():
	root = tempfile.mkdtemp()
	try:
		_clean_project(root)
		other = _events_dir(root, "01DIRTY")
		dirty = os.path.join(other, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jsonl")
		_write(dirty, [_event("d1", "d0", **{"move.node": {"id": "ISSUE9", "parent": "L"}})])
		old = time.time() - 7200
		os.utime(dirty, (old, old))
		code, out = _run(root, "--repo", "01CLEAN")
		xtest.equal(code, 0)
		xtest.not_equal("ISSUE9" in out, True)
		code, out = _run(root, "--repo", "01DIRTY")
		xtest.equal(code, 1)
		xtest.contains("ISSUE9", out)
	finally:
		shutil.rmtree(root)
