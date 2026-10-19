"""Track which sessions belong to a launched agent window.

Two sources, because neither alone answers the question:

- the **registry** (`~/.opencode/agents/<sessionID>.json`), written by
  `tools/oc-agent` once the opencode process is up. This is the only record of an
  agent that is open but idle: the service's `/api/session/active` means
  *executing*, not *open*, so an idle agent is absent from it entirely. Each entry
  names the opencode process by pid **and** start time, so its lifetime is that
  process's — not the kitty window's, which outlives it.
- the **service**, for sessions running outside any oc-agent window.

A session is shown when it is in either. Registry entries outrank the service
for role and workspace, since the service knows neither reliably.
"""

import json,os,time
from pathlib import Path
from . import service

REGISTRY_DIR=Path.home()/".opencode"/"agents"

def read_registry(registry_dir:Path=REGISTRY_DIR) -> dict:
	"""Live registry entries keyed by session id, skipping stale or broken files.

	A file whose process is gone is stale: oc-agent removes it on exit, so this
	covers the case where it could not (a kill, a crash, a closed window).
	"""
	entries={}
	try:
		paths=sorted(registry_dir.glob("*.json"))
	except OSError:
		return entries
	for path in paths:
		try:
			entry=json.loads(path.read_text())
			if not _running(entry):
				path.unlink(missing_ok=True)
				continue
			session_id=entry.get("session_id")
			if session_id:
				entries[session_id]=entry
		except (OSError,json.JSONDecodeError,AttributeError):
			continue
	return entries

def _running(entry:dict) -> bool:
	"""Whether the process an entry was written for is still that same process.

	`pid` on its own is not an identity. The number is handed out again as
	processes die, and a reused one would hold a finished session on the panel for
	as long as the unrelated process it now names goes on living. `start_ticks`
	is what closes that: the pair names one process for as long as the machine is
	up, which is what makes an entry's lifetime the opencode process's rather
	than whatever inherits its pid.

	An entry carrying no usable handle counts as not running. "Cannot be checked"
	and "still running" are different claims and only one of them can be acted on;
	a session nobody can vouch for is not one to keep on the panel.
	"""
	pid=entry.get("pid")
	ticks=entry.get("start_ticks")
	if not isinstance(pid,int) or not isinstance(ticks,int):
		return False
	if not _alive(pid):
		return False
	return _start_ticks(pid)==ticks

def _start_ticks(pid:int):
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

def _alive(pid:int) -> bool:
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

def _registry_session(entry:dict) -> dict:
	"""A registry entry shaped like a service session, so both sources merge."""
	return {"id":entry.get("session_id"),"agent":entry.get("agent") or entry.get("role") or "unknown","title":entry.get("role"),"location":{"directory":entry.get("workspace","")},"started_at":entry.get("started_at")}

class SessionWatcher:
	"""Poll the registry and the service, reporting sessions as they come and go."""

	def __init__(self,base_url:str,pw:str,on_new,on_removed,poll_seconds:float=3.0,registry_dir:Path=REGISTRY_DIR):
		self.base_url=base_url
		self.pw=pw
		self.on_new=on_new
		self.on_removed=on_removed
		self.poll_seconds=poll_seconds
		self.registry_dir=registry_dir
		self._known:set=set()
		self._running=False

	def _collect(self) -> dict:
		"""Every session worth showing, keyed by id, registry first."""
		found={}
		registry=read_registry(self.registry_dir)
		for session_id,entry in registry.items():
			found[session_id]=_registry_session(entry)
		active=service.active_session_ids(self.base_url,self.pw)
		if active is None:
			return found
		added=active-set(found)
		if added:
			sessions=service.all_sessions(self.base_url,self.pw)
			if sessions is None:
				return found
			by_id={s.get("id"):s for s in sessions}
			for session_id in added:
				if by_id.get(session_id):
					found[session_id]=by_id[session_id]
		return found

	def _scan(self) -> set:
		"""Sessions to show now, reconciled against the last scan."""
		found=self._collect()
		for session_id in self._known-set(found):
			self.on_removed(session_id)
			self._known.discard(session_id)
		for session_id,session in found.items():
			self.on_new(session)
			self._known.add(session_id)
		return set(self._known)

	def run_once(self) -> set:
		"""One scan, for `--once` mode."""
		return self._scan()

	def run_watch(self) -> None:
		"""Poll until stopped."""
		self._running=True
		while self._running:
			try:
				self._scan()
			except Exception:
				# A failed poll must not kill the panel; the next tick retries.
				pass
			deadline=time.time()+self.poll_seconds
			while self._running and time.time()<deadline:
				time.sleep(0.1)

	def stop(self) -> None:
		"""Stop the polling loop."""
		self._running=False
