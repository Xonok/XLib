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

import json,time
from pathlib import Path
from . import service
from .inotify import Inotify,available as inotify_available
from .instance import INSTANCES_DIR,is_window,read_instances,window_session
from .process import alive as _alive,start_ticks as _start_ticks

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

def _registry_session(entry:dict,session_id:str=None) -> dict:
	"""A registry entry shaped like a service session, so both sources merge.

	`session_id` is the session the window is on now, which is not always the one
	the entry was written with — a `/new` replaces it — so it is passed in rather
	than read from the entry.
	"""
	sid=session_id if session_id else entry.get("session_id")
	return {"id":sid,"agent":entry.get("agent") or entry.get("role") or "unknown","title":entry.get("role"),"location":{"directory":entry.get("workspace","")},"started_at":entry.get("started_at"),"window":is_window(sid)}

class SessionWatcher:
	"""Poll the registry and the service, reporting sessions as they come and go."""

	def __init__(self,base_url:str,pw:str,on_new,on_removed,poll_seconds:float=3.0,registry_dir:Path=REGISTRY_DIR,instances_dir:Path=INSTANCES_DIR):
		self.base_url=base_url
		self.pw=pw
		self.on_new=on_new
		self.on_removed=on_removed
		self.poll_seconds=poll_seconds
		self.registry_dir=registry_dir
		self.instances_dir=instances_dir
		self._known:set=set()
		self._running=False

	def _collect(self) -> dict:
		"""Every session worth showing, keyed by id, registry first.

		A registry entry is a window, and the window's session is not the one the
		entry was written with: a `/new` replaces it while the process lives on.
		The instance report says which session the process is on now, and it is
		what the entry is keyed by — so the session the window left behind stops
		being shown at all, and the window is shown once, under its own name.
		"""
		found={}
		registry=read_registry(self.registry_dir)
		instances=read_instances(self.instances_dir)
		for session_id,entry in registry.items():
			current=window_session(entry,instances.get(entry.get("pid")))
			found[current]=_registry_session(entry,current)
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
		"""Scan until stopped, waking early when the registry changes.

		The registry and the instance reports are files, so inotify is what
		notices them; a missing inotify is the only case that falls back to
		the plain poll interval. The service is still asked on each pass,
		because a session running outside a window has no file to watch.
		"""
		self._running=True
		watcher=None
		if inotify_available():
			try:
				watcher=Inotify()
				for path in (self.registry_dir,self.instances_dir):
					if path.exists():
						watcher.add(path)
			except OSError:
				if watcher is not None:
					watcher.close()
				watcher=None
		try:
			while self._running:
				try:
					self._scan()
				except Exception:
					# A failed poll must not kill the panel; the next tick retries.
					pass
				if watcher is not None:
					watcher.read(self.poll_seconds)
					continue
				deadline=time.time()+self.poll_seconds
				while self._running and time.time()<deadline:
					time.sleep(0.1)
		finally:
			if watcher is not None:
				watcher.close()

	def stop(self) -> None:
		"""Stop the polling loop."""
		self._running=False
