"""Banned git commands in tracked files.

The working-tree rules forbid `git checkout`, `git reset --hard` and
`git reset --merge`: each overwrites or moves state with no warning and
nothing to undo. The rule cannot stop a one-off command (that needs the
opencode plugin guard), but it can stop the durable half — a banned command
written into a tracked file, where it would be copy-pasted again.

The check runs on tracked files only, the way the personal-identifier check
does: an untracked draft is allowed to carry the string while it is being
written.
"""

import re

_PATTERNS = [
	(re.compile(r"\bgit\s+checkout\b"), "git checkout"),
	(re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard"),
	(re.compile(r"\bgit\s+reset\s+--merge\b"), "git reset --merge"),
]

def check(lines):
	"""The banned git commands in `lines`, as `(line number, message)` pairs."""
	report = []
	for index, line in enumerate(lines, start=1):
		for pattern, name in _PATTERNS:
			if pattern.search(line):
				report.append((index, f"banned git command ({name}) in tracked file — use git switch / git restore instead"))
				break
	return report
