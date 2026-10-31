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

# Only a command that is actually written as a command is flagged: it must
# appear at the start of the line, optionally after a shell prompt or leading
# whitespace. A mention in prose, documentation or an inline code span is not
# a copy-pasteable command and is not reported. This keeps the rule from
# firing on every discussion of the ban while still catching the durable half.
_PATTERNS = [
	(re.compile(r"^\s*(?:[$#>]\s*)?git\s+checkout\b"), "git checkout"),
	(re.compile(r"^\s*(?:[$#>]\s*)?git\s+reset\s+--hard\b"), "git reset --hard"),
	(re.compile(r"^\s*(?:[$#>]\s*)?git\s+reset\s+--merge\b"), "git reset --merge"),
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
