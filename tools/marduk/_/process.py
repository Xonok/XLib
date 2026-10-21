"""Identity of a process on this machine.

A pid is not an identity: the number is handed out again as processes die, and
a reused one would hold a finished session on the panel for as long as the
unrelated process it now names goes on living. The pair — pid and the clock
ticks at which the process started — names one process for as long as the
machine is up, which is what makes a handle's lifetime the process's rather
than whatever inherits the number.

Both the registry and the instance reports are checked this way, so the check
lives here and has one copy.
"""

import os
from pathlib import Path

def alive(pid:int) -> bool:
	"""Whether a process id is still running."""
	try:
		os.kill(pid,0)
	except ProcessLookupError:
		return False
	except PermissionError:
		return True
	except OSError:
		return True
	return True

def start_ticks(pid:int):
	"""Clock ticks since boot at which a process started, or None if unreadable.

	Field 22 of `/proc/<pid>/stat`. The `comm` field (2) is parenthesised and may
	contain spaces, so the line is cut after its *last* `)` before it is split —
	cutting at the first would miscount every field behind a parenthesis in the
	process name.
	"""
	try:
		after=Path(f"/proc/{pid}/stat").read_text().rpartition(")")[2].split()
		return int(after[19])
	except (OSError,ValueError,IndexError):
		return None
