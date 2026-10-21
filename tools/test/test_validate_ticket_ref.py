import json,os,shutil,subprocess,sys,tempfile
from pathlib import Path

# xtest, found relative to this file rather than to the working directory: a
# path relative to the cwd only works from the repository root, and a test
# that runs from one directory and fails from another is worse than one that
# never runs.
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
import xtest

# The tool under test, relative to this file rather than to the working
# directory, for the same reason.
VALIDATOR = REPO / "tools" / "hooks" / "validate-ticket-ref.py"
# The project id is read from the repository rather than written down, so a
# re-created board does not leave this test pointing at nothing.
PROJECT = json.loads((REPO / ".epiq" / "project.json").read_text())["projectId"]

def _issue_event(issue_id: str, name: str) -> str:
	return json.dumps({"v": 1, "id": ["e" + issue_id, "parent"],
		"add.issue": {"id": issue_id, "name": name, "parent": "LANE"}})

def _fixture(logs: dict) -> str:
	"""A home directory holding a state worktree with the given event logs.

	The validator finds the board through the repository's `.epiq/project.json`
	and then looks for the state worktree under the home directory, so pointing
	HOME at a fixture is enough to give it a board of our own.
	"""
	home = tempfile.mkdtemp()
	events = Path(home) / ".epiq-global" / "worktrees" / PROJECT / ".epiq" / "events"
	events.mkdir(parents=True)
	for name, lines in logs.items():
		(events / name).write_text("\n".join(lines) + "\n")
	return home

def _run(home: str, ref: str) -> tuple:
	"""Run the validator against a fixture board; return (exit code, output)."""
	env = dict(os.environ, HOME=home)
	proc = subprocess.run([sys.executable, str(VALIDATOR), ref],
		capture_output=True, text=True, env=env, cwd=str(REPO))
	return proc.returncode, proc.stdout + proc.stderr

def test_a_ref_in_the_committed_log_is_valid():
	home = _fixture({"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jsonl": [
		_issue_event("01M4DPM5YTB9AQ8TBRJAAAAAAA", "committed"),
	]})
	try:
		code, out = _run(home, "AAAAAAA")
		xtest.equal(code, 0, "a committed ref passes")
	finally:
		shutil.rmtree(home)

def test_a_ref_only_in_a_pending_log_is_refused():
	"""The guarantee stands: a ref nobody else can resolve does not pass."""
	home = _fixture({
		"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jsonl": [_issue_event("01M4DPM5YTB9AQ8TBRJAAAAAAA", "committed")],
		"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb~pending.jsonl": [_issue_event("01M4DPM5YTB9AQ8TBRJPEND999", "pending")],
	})
	try:
		code, out = _run(home, "PEND999")
		xtest.equal(code, 1, "an unsynced ref is refused")
	finally:
		shutil.rmtree(home)

def test_the_refusal_of_an_unsynced_ref_says_to_sync():
	"""The failure mode is a missing sync, not a missing ticket, and it says so.

	The plain message names an invalid ref and lists the valid ones, which is
	true and useless: the ticket exists, it just has not been synced. An agent
	reading that has nothing to act on but re-reading the ticket's own title.
	"""
	home = _fixture({
		"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jsonl": [_issue_event("01M4DPM5YTB9AQ8TBRJAAAAAAA", "committed")],
		"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb~pending.jsonl": [_issue_event("01M4DPM5YTB9AQ8TBRJPEND999", "pending")],
	})
	try:
		code, out = _run(home, "PEND999")
		xtest.equal(code, 1)
		xtest.contains("not yet synced", out)
		xtest.contains("epiq_sync", out)
		xtest.contains("PEND999", out)
	finally:
		shutil.rmtree(home)

def test_an_unknown_ref_says_nothing_about_syncing():
	"""A ref that exists nowhere is a different mistake, and says so."""
	home = _fixture({"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jsonl": [
		_issue_event("01M4DPM5YTB9AQ8TBRJAAAAAAA", "committed"),
	]})
	try:
		code, out = _run(home, "NOSUCHX")
		xtest.equal(code, 1)
		xtest.contains("Invalid ticket ref", out)
		xtest.not_equal("not yet synced" in out, True)
	finally:
		shutil.rmtree(home)

def test_a_ref_committed_and_still_pending_is_valid():
	"""One actor's pending copy of a ref another actor already committed."""
	home = _fixture({
		"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jsonl": [_issue_event("01M4DPM5YTB9AQ8TBRJAAAAAAA", "committed")],
		"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb~pending.jsonl": [_issue_event("01M4DPM5YTB9AQ8TBRJAAAAAAA", "committed")],
	})
	try:
		code, out = _run(home, "AAAAAAA")
		xtest.equal(code, 0, "a committed ref is valid even if it is also pending")
	finally:
		shutil.rmtree(home)

def test_a_backup_log_is_not_read():
	"""The `.jsonl.backup` copies are copies, and a ref in one is not a ref.

	The glob over `*.jsonl` excludes them, so this pins the outcome rather than
	a line of code — which is the right thing to pin, because the outcome is
	what a ref means.
	"""
	home = _fixture({
		"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jsonl": [_issue_event("01M4DPM5YTB9AQ8TBRJAAAAAAA", "committed")],
		"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jsonl.backup": [_issue_event("01M4DPM5YTB9AQ8TBRJBACKUP", "backup")],
	})
	try:
		code, out = _run(home, "BACKUP")
		xtest.equal(code, 1, "a ref in a backup is not a ref")
		xtest.not_equal("not yet synced" in out, True)
	finally:
		shutil.rmtree(home)

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
