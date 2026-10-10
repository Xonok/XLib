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

def extract_valid_refs(state_worktree: Path) -> set[str]:
	"""Extract all valid ticket refs from the epiq state worktree."""
	refs = set()
	events_dir = state_worktree / ".epiq" / "events"
	if not events_dir.exists():
		return refs

	for event_file in events_dir.glob("*.jsonl"):
		if event_file.name.endswith(".backup") or "~pending" in event_file.name:
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

def get_valid_refs_for_repo(repo_root: Path) -> set[str]:
	"""Get all valid ticket refs for the given repository."""
	project_json = find_epiq_project(repo_root)
	if not project_json:
		return set()

	state_worktree = get_epiq_state_worktree(project_json)
	if not state_worktree:
		return set()

	return extract_valid_refs(state_worktree)

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
		print(f"ERROR: Invalid ticket ref '{ref}'", file=sys.stderr)
		print("Valid refs:", ", ".join(sorted(valid_refs)), file=sys.stderr)
		sys.exit(1)

if __name__ == "__main__":
	main()
