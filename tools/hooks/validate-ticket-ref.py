#!/usr/bin/env python3
"""
Validate a ticket ref against the epiq board.

Usage: validate-ticket-ref.py <ref>
Exit code: 0 if valid, 1 if invalid, 2 on error.

Environment variables:
  EPIQ_ALLOW_FORMAT_FALLBACK=1  Allow format-only check when board cannot be loaded (default: fail closed)

AI AGENTS: DO NOT SET EPIQ_ALLOW_FORMAT_FALLBACK=1 WITHOUT EXPLICIT HUMAN PERMISSION.
This fallback exists only for genuine infrastructure failures (e.g., corrupted board state).
Using it to bypass validation defeats the purpose of the commit hook and will be treated as a policy violation.
"""

import json,sys,subprocess,os
from pathlib import Path

def find_epiq_project(repo_root: Path) -> Path | None:
	"""Find the epiq project.json for the given repo."""
	epiq_dir = repo_root / ".epiq"
	if not epiq_dir.exists():
		return None
	project_json = epiq_dir / "project.json"
	if not project_json.exists():
		return None
	return project_json

def get_epiq_state_worktree(project_json: Path) -> Path | None:
	"""Get the path to the epiq state worktree."""
	try:
		with open(project_json) as f:
			data = json.load(f)
		project_id = data.get("projectId")
		if not project_id:
			return None
		state_worktree = Path.home() / ".epiq-global" / "worktrees" / project_id
		if state_worktree.exists():
			return state_worktree
	except Exception:
		pass
	return None

def extract_valid_refs(state_worktree: Path, include_pending: bool = False) -> set[str]:
	"""Extract all valid ticket refs from the epiq state worktree.

	`include_pending` decides whether an actor's unsynced writes count. They are
	kept out of the committed set on purpose: a ref found only there is real on
	this machine and on no other one yet, and a commit naming it would name
	something nobody else can resolve.
	"""
	refs = set()
	events_dir = state_worktree / ".epiq" / "events"
	if not events_dir.exists():
		return refs

	for event_file in events_dir.glob("*.jsonl"):
		# The glob excludes the `.jsonl.backup` copies on its own, so only the
		# pending logs need a name check. They are the actor's unsynced writes,
		# and they are the reason a freshly filed ticket's ref is not found.
		if "~pending" in event_file.name and not include_pending:
			continue
		try:
			with open(event_file) as f:
				for line in f:
					line = line.strip()
					if not line:
						continue
					try:
						event = json.loads(line)
						if "add.issue" in event:
							issue_data = event["add.issue"]
							issue_id = issue_data.get("id")
							if issue_id and len(issue_id) >= 7:
								ref = issue_id[-7:]
								refs.add(ref)
					except json.JSONDecodeError:
						continue
		except Exception:
			continue

	return refs

def get_state_worktree(repo_root: Path) -> Path | None:
	"""The epiq state worktree for this repository, if it has one."""
	project_json = find_epiq_project(repo_root)
	if not project_json:
		return None
	return get_epiq_state_worktree(project_json)

def get_valid_refs_for_repo(repo_root: Path) -> set[str]:
	"""Get all valid ticket refs for the given repository."""
	state_worktree = get_state_worktree(repo_root)
	if not state_worktree:
		return set()

	return extract_valid_refs(state_worktree)

def get_pending_refs_for_repo(repo_root: Path) -> set[str]:
	"""The refs that exist only in an actor's unsynced writes.

	A freshly filed ticket lands in the actor's `~pending` log, so its ref is
	real and not yet committed. The commit that names it is refused, correctly —
	and the reason it is refused is a missing sync, not a missing ticket.
	"""
	state_worktree = get_state_worktree(repo_root)
	if not state_worktree:
		return set()

	return extract_valid_refs(state_worktree, include_pending=True) - get_valid_refs_for_repo(repo_root)

def main():
	if len(sys.argv) != 2:
		print("Usage: validate-ticket-ref.py <ref>", file=sys.stderr)
		sys.exit(2)

	ref = sys.argv[1].strip().upper()

	allow_fallback = os.environ.get("EPIQ_ALLOW_FORMAT_FALLBACK") == "1"

	try:
		repo_root = Path(subprocess.check_output(
			["git", "rev-parse", "--show-toplevel"],
			stderr=subprocess.DEVNULL, text=True
		).strip())
	except subprocess.CalledProcessError:
		print("ERROR: Not in a git repository", file=sys.stderr)
		sys.exit(2)

	valid_refs = get_valid_refs_for_repo(repo_root)

	if not valid_refs:
		if allow_fallback:
			print("WARNING: Could not load epiq board; falling back to format check only (EPIQ_ALLOW_FORMAT_FALLBACK=1)", file=sys.stderr)
			if len(ref) == 7 and ref.isalnum():
				sys.exit(0)
			else:
				sys.exit(1)
		else:
			print("ERROR: Could not load epiq board. Set EPIQ_ALLOW_FORMAT_FALLBACK=1 to allow format-only check (requires explicit human permission).", file=sys.stderr)
			sys.exit(1)

	if ref in valid_refs:
		sys.exit(0)
	else:
		pending_refs = get_pending_refs_for_repo(repo_root)
		if ref in pending_refs:
			print(f"ERROR: Ticket ref '{ref}' was filed but not yet synced", file=sys.stderr)
			print("It is in an actor's pending event log, which is not committed and not on any other machine.", file=sys.stderr)
			print("Run epiq_sync, and again if it reports skipped, then commit.", file=sys.stderr)
			sys.exit(1)
		print(f"ERROR: Invalid ticket ref '{ref}'", file=sys.stderr)
		print("Valid refs:", ", ".join(sorted(valid_refs)), file=sys.stderr)
		sys.exit(1)

if __name__ == "__main__":
	main()
