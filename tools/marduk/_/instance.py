"""The instance reports: which opencode process is on which session.

A window is an opencode **process**, not a session. A `/new` in the TUI
replaces the session while the process lives on, so the registry — written once
at launch, naming the session the window was launched with — goes stale, and
the panel shows the window twice: the dead session the registry still names,
and the live one it cannot place.

The service cannot answer "which process owns this session". `/api/session/active`
is the sessions owned by the *service* process, the session table carries no
pid, and `session.viewed` carries no client either. The one party that knows
is the opencode process itself, so it reports: the TUI plugin in
`tools/marduk/plugin/instance-report/` writes one file per process, named for
its pid.

The file is the whole contract:

	{"pid": 10116, "cwd": "/srv/agents",
	 "sessionID": "ses_ea53c242…", "at": 1792560442000}

`sessionID` is null while the window is on no session — the honest answer
between a `/new` and the first message of the new one.
"""

import json
from pathlib import Path
from .process import alive

INSTANCES_DIR=Path.home()/".opencode"/"instances"

WINDOW_PREFIX="window:"

def window_key(pid:int) -> str:
	"""The key a window with no session is filed under.

	Not a session id: the window is on none, and the key has to be something
	that cannot be mistaken for one.
	"""
	return f"{WINDOW_PREFIX}{pid}"

def is_window(session_id:str) -> bool:
	"""Whether a key names a window rather than a session."""
	return isinstance(session_id,str) and session_id.startswith(WINDOW_PREFIX)

def read_instances(instances_dir:Path=INSTANCES_DIR) -> dict:
	"""Live instance reports keyed by pid; a file whose process is gone is reaped.

	A process killed outright leaves its file behind — the plugin removes it on
	a clean exit, but nothing runs that cleanup on a SIGKILL. The pid is checked
	against the process table, so such a file is deleted rather than read: a
	recycled pid would otherwise make the panel believe a window is on a
	session that belongs to somebody else.
	"""
	entries={}
	try:
		paths=sorted(instances_dir.glob("*.json"))
	except OSError:
		return entries
	for path in paths:
		try:
			entry=json.loads(path.read_text())
			pid=entry.get("pid")
			if not isinstance(pid,int) or not alive(pid):
				path.unlink(missing_ok=True)
				continue
			entries[pid]=entry
		except (OSError,json.JSONDecodeError,AttributeError):
			continue
	return entries

def window_session(entry:dict,report) -> str:
	"""The session a window is on now, or the window's own key when it is on none.

	The registry names the session the window was *launched* with; the report
	names the session that process is on *now*. The report wins, because a
	`/new` replaces the session and the window lives on.

	Three cases, and the third is the one that is easy to get wrong:

	- a report naming a session: that is the window's session;
	- a report saying no session: the window is between sessions, and it still
	  belongs on the panel — under a key of its own, so it is not confused
	  with the session it left behind;
	- no report at all: the window has never reported itself (it was started
	  before the plugin existed), so the launch session is the best that is
	  known, and the panel reads as it did before.
	"""
	launch=entry.get("session_id")
	if not isinstance(report,dict) or "sessionID" not in report:
		return launch
	current=report.get("sessionID")
	if isinstance(current,str) and current:
		return current
	return window_key(entry.get("pid"))
