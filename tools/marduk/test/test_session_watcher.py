#!/usr/bin/env python3
"""
Tests for session reconciliation — tools/marduk/_/session_watcher.py.

Run with: python3 -m unittest tools.marduk.test.test_session_watcher -v

The service functions are patched, so nothing here opens a socket. What is
under test is the reconciliation itself: which sessions produce `on_new`, which
produce `on_removed`, and — the subtle one — that a session the service
reports as active *before* it appears in the session list is still picked up on
a later scan instead of being marked known and forgotten.
"""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools.marduk._ import service
from tools.marduk._.session_watcher import SessionWatcher,read_registry,_start_ticks

_EMPTY_REGISTRY=Path(tempfile.gettempdir())/"marduk-test-empty-registry"

def _watcher(active_by_scan,meta_by_scan=None):
	"""A watcher whose service calls are scripted scan by scan.

	`active_by_scan` is a list of id-sets, one per scan. `meta_by_scan` is the
	session list per scan; it defaults to metadata for whatever is active. The
	registry is pointed at an empty directory so these tests exercise the
	service path only — see TestRegistry for the other source.
	"""
	added: list = []
	removed: list = []
	state={"i":-1}

	def _next_active(*_a,**_k):
		state["i"]+=1
		i=min(state["i"],len(active_by_scan)-1)
		return set(active_by_scan[i])

	def _next_all(*_a,**_k):
		if meta_by_scan is None:
			i=min(state["i"],len(active_by_scan)-1)
			return [{"id":sid,"agent":"secretary"} for sid in active_by_scan[i]]
		i=min(state["i"],len(meta_by_scan)-1)
		return meta_by_scan[i]

	watcher=SessionWatcher("http://x","pw",on_new=added.append,on_removed=removed.append,poll_seconds=0.01,registry_dir=_EMPTY_REGISTRY)
	return watcher,added,removed,_next_active,_next_all

def _scan(watcher,active_fn,all_fn):
	"""Run one scan with the service patched."""
	with patch.object(service,"active_session_ids",active_fn),patch.object(service,"all_sessions",all_fn):
		return watcher.run_once()

class TestDiscovery(unittest.TestCase):
	def test_new_session_is_announced_once(self):
		watcher,added,removed,active,all_= _watcher([{"ses_1"}])
		_scan(watcher,active,all_)
		self.assertEqual(len(added),1)
		self.assertEqual(added[0]["id"],"ses_1")
		self.assertEqual(removed,[])

	def test_rescan_does_not_reannounce(self):
		"""A repeated announcement would reset the agent's age every tick.

		`_on_new_session` is idempotent for a session it already holds, so the
		repeated call is harmless — but the count is asserted to document that
		the watcher does hand it over every scan.
		"""
		watcher,added,removed,active,all_=_watcher([{"ses_1"},{"ses_1"}])
		_scan(watcher,active,all_)
		_scan(watcher,active,all_)
		self.assertEqual(len(added),2)
		self.assertEqual([s["id"] for s in added],["ses_1","ses_1"])

	def test_second_session_is_announced(self):
		watcher,added,removed,active,all_=_watcher([{"ses_1"},{"ses_1","ses_2"}])
		_scan(watcher,active,all_)
		_scan(watcher,active,all_)
		self.assertEqual(sorted({s["id"] for s in added}),["ses_1","ses_2"])

class TestRemoval(unittest.TestCase):
	def test_vanished_session_is_retired(self):
		watcher,added,removed,active,all_=_watcher([{"ses_1"},set()],[
			[{"id":"ses_1","agent":"secretary"}],
			[],
		])
		_scan(watcher,active,all_)
		_scan(watcher,active,all_)
		self.assertEqual(removed,["ses_1"])

	def test_survivor_is_not_retired(self):
		watcher,added,removed,active,all_=_watcher([{"ses_1","ses_2"},{"ses_2"}],[
			[{"id":"ses_1","agent":"a"},{"id":"ses_2","agent":"b"}],
			[{"id":"ses_2","agent":"b"}],
		])
		_scan(watcher,active,all_)
		_scan(watcher,active,all_)
		self.assertEqual(removed,["ses_1"])

class TestMetadataLag(unittest.TestCase):
	def test_active_session_without_metadata_is_retried(self):
		"""The regression: marking it known before it could be emitted drops
		the session from the panel for the rest of its life."""
		meta=[[],[{"id":"ses_1","agent":"secretary"}],[{"id":"ses_1","agent":"secretary"}]]
		watcher,added,removed,active,all_=_watcher([{"ses_1"}]*3,meta)
		self.assertEqual(_scan(watcher,active,all_),set())
		self.assertEqual(added,[])
		self.assertEqual(_scan(watcher,active,all_),{"ses_1"})
		self.assertEqual(len(added),1)

	def test_reappearing_session_is_announced_again(self):
		watcher,added,removed,active,all_=_watcher([{"ses_1"},set(),{"ses_1"}])
		_scan(watcher,active,all_)
		_scan(watcher,active,all_)
		_scan(watcher,active,all_)
		self.assertEqual(len(added),2)
		self.assertEqual(len(removed),1)

class TestRegistry(unittest.TestCase):
	"""The registry is the only record of a window that is open but idle."""

	def _watcher(self,reg):
		added: list = []
		removed: list = []
		watcher=SessionWatcher("http://x","pw",on_new=added.append,on_removed=removed.append,poll_seconds=0.01,registry_dir=reg)
		return watcher,added,removed

	def _write(self,reg,session_id,role="secretary-1",pid=None,ticks=None,drop=()):
		"""Write a registry entry.

		`pid` and `ticks` default to this process and its own start time, which is
		a live entry; `drop` removes fields, to write the entries a real oc-agent
		no longer produces.
		"""
		entry={"session_id":session_id,"role":role,"agent":role.split("-")[0],"workspace":"/w","slot":1,
			"pid":os.getpid() if pid is None else pid,
			"start_ticks":_start_ticks(os.getpid()) if ticks is None else ticks,
			"started_at":1}
		for field in drop:
			entry.pop(field,None)
		(reg/f"{session_id}.json").write_text(json.dumps(entry))

	def test_idle_registry_session_is_shown(self):
		"""The regression this whole file exists for: not in /active, still shown."""
		with tempfile.TemporaryDirectory() as tmp:
			reg=Path(tmp)
			self._write(reg,"ses_idle")
			watcher,added,removed=self._watcher(reg)
			with patch.object(service,"active_session_ids",return_value=set()),patch.object(service,"all_sessions",return_value=[]):
				self.assertEqual(watcher.run_once(),{"ses_idle"})
			# `_registry_session` normalises to the service's shape: `title`
			# carries the role (with slot), `agent` the bare agent name.
			self.assertEqual(added[0]["title"],"secretary-1")
			self.assertEqual(added[0]["agent"],"secretary")

	def test_registry_workspace_is_carried(self):
		with tempfile.TemporaryDirectory() as tmp:
			reg=Path(tmp)
			self._write(reg,"ses_ws")
			watcher,added,removed=self._watcher(reg)
			with patch.object(service,"active_session_ids",return_value=set()),patch.object(service,"all_sessions",return_value=[]):
				watcher.run_once()
			self.assertEqual(added[0]["location"]["directory"],"/w")

	def test_stale_pid_file_is_reaped(self):
		"""A killed opencode leaves its file behind; it must not linger."""
		with tempfile.TemporaryDirectory() as tmp:
			reg=Path(tmp)
			self._write(reg,"ses_dead",pid=999999)
			watcher,added,removed=self._watcher(reg)
			with patch.object(service,"active_session_ids",return_value=set()),patch.object(service,"all_sessions",return_value=[]):
				self.assertEqual(watcher.run_once(),set())
			self.assertFalse((reg/"ses_dead.json").exists())

	def test_recycled_pid_is_reaped(self):
		"""The regression behind `start_ticks`: a live pid is not a live session.

		The number belongs to whatever process holds it now. An unrelated long-lived
		process reusing a dead agent's pid would otherwise keep that agent on the
		panel until it exits itself, which is the window-bound lifetime all over
		again with a different cause.
		"""
		with tempfile.TemporaryDirectory() as tmp:
			reg=Path(tmp)
			self._write(reg,"ses_recycled",ticks=_start_ticks(os.getpid())+1)
			watcher,added,removed=self._watcher(reg)
			with patch.object(service,"active_session_ids",return_value=set()),patch.object(service,"all_sessions",return_value=[]):
				self.assertEqual(watcher.run_once(),set())
			self.assertFalse((reg/"ses_recycled.json").exists())

	def test_entry_without_a_usable_pid_is_reaped(self):
		"""`isinstance(pid,int) and not _alive(pid)` used to skip the check entirely.

		An entry whose pid is missing or the wrong type fell through to "keep", so it
		was never reaped at all — the one leak no kill could clear.
		"""
		for field in ("pid","start_ticks"):
			with self.subTest(missing=field),tempfile.TemporaryDirectory() as tmp:
				reg=Path(tmp)
				self._write(reg,f"ses_no_{field}",drop=(field,))
				with patch.object(service,"active_session_ids",return_value=set()),patch.object(service,"all_sessions",return_value=[]):
					self.assertEqual(self._watcher(reg)[0].run_once(),set())
				self.assertFalse((reg/f"ses_no_{field}.json").exists())

	def test_entry_from_the_pre_fix_launcher_is_reaped(self):
		"""An entry oc-agent wrote before this fix names the kitty window's shell.

		Nothing in it is a usable handle any more, so it goes rather than sitting on
		the panel under a pid that now means a live bash.
		"""
		with tempfile.TemporaryDirectory() as tmp:
			reg=Path(tmp)
			self._write(reg,"ses_legacy",drop=("start_ticks",))
			watcher,added,removed=self._watcher(reg)
			with patch.object(service,"active_session_ids",return_value=set()),patch.object(service,"all_sessions",return_value=[]):
				watcher.run_once()
			self.assertFalse((reg/"ses_legacy.json").exists())

	def test_malformed_entry_is_skipped(self):
		with tempfile.TemporaryDirectory() as tmp:
			reg=Path(tmp)
			(reg/"broken.json").write_text("{not json")
			self._write(reg,"ses_ok")
			watcher,added,removed=self._watcher(reg)
			with patch.object(service,"active_session_ids",return_value=set()),patch.object(service,"all_sessions",return_value=[]):
				self.assertEqual(watcher.run_once(),{"ses_ok"})

	def test_registry_role_outranks_service_title(self):
		"""A service title is just the agent name; the slot suffix is ours."""
		with tempfile.TemporaryDirectory() as tmp:
			reg=Path(tmp)
			self._write(reg,"ses_both",role="secretary-3")
			watcher,added,removed=self._watcher(reg)
			meta=[{"id":"ses_both","agent":"secretary","title":"secretary","location":{"directory":"/other"}}]
			with patch.object(service,"active_session_ids",return_value={"ses_both"}),patch.object(service,"all_sessions",return_value=meta):
				watcher.run_once()
			self.assertEqual(added[0]["title"],"secretary-3")
			self.assertEqual(added[0]["location"]["directory"],"/w")

	def test_service_only_session_is_still_shown(self):
		"""Sessions outside any oc-agent window must not disappear."""
		with tempfile.TemporaryDirectory() as tmp:
			reg=Path(tmp)
			watcher,added,removed=self._watcher(reg)
			meta=[{"id":"ses_raw","agent":"programmer","title":"programmer","location":{"directory":"/p"}}]
			with patch.object(service,"active_session_ids",return_value={"ses_raw"}),patch.object(service,"all_sessions",return_value=meta):
				self.assertEqual(watcher.run_once(),{"ses_raw"})

	def test_removing_the_file_drops_the_session(self):
		with tempfile.TemporaryDirectory() as tmp:
			reg=Path(tmp)
			self._write(reg,"ses_gone")
			watcher,added,removed=self._watcher(reg)
			with patch.object(service,"active_session_ids",return_value=set()),patch.object(service,"all_sessions",return_value=[]):
				watcher.run_once()
			(reg/"ses_gone.json").unlink()
			with patch.object(service,"active_session_ids",return_value=set()),patch.object(service,"all_sessions",return_value=[]):
				self.assertEqual(watcher.run_once(),set())
			self.assertEqual(removed,["ses_gone"])

	def test_missing_registry_directory_is_not_fatal(self):
		watcher,added,removed=self._watcher(Path("/nonexistent/marduk/registry"))
		with patch.object(service,"active_session_ids",return_value=set()),patch.object(service,"all_sessions",return_value=[]):
			self.assertEqual(watcher.run_once(),set())

class TestReadRegistry(unittest.TestCase):
	def test_empty_directory_yields_nothing(self):
		with tempfile.TemporaryDirectory() as tmp:
			self.assertEqual(read_registry(Path(tmp)),{})

	def test_missing_directory_yields_nothing(self):
		self.assertEqual(read_registry(Path("/nonexistent/marduk/registry")),{})

	def test_entry_without_session_id_is_dropped(self):
		with tempfile.TemporaryDirectory() as tmp:
			reg=Path(tmp)
			(reg/"x.json").write_text(json.dumps({"role":"nope","pid":os.getpid(),"start_ticks":_start_ticks(os.getpid())}))
			self.assertEqual(read_registry(reg),{})

class TestStartTicks(unittest.TestCase):
	"""Field 22 is behind a parenthesised `comm`, which is the whole difficulty."""

	def test_reads_this_process(self):
		self.assertIsInstance(_start_ticks(os.getpid()),int)

	def test_is_stable_across_calls(self):
		self.assertEqual(_start_ticks(os.getpid()),_start_ticks(os.getpid()))

	def test_distinguishes_a_different_process(self):
		"""The value the check rests on: two live processes, two answers."""
		child=subprocess.Popen(["sleep","5"])
		try:
			self.assertNotEqual(_start_ticks(child.pid),_start_ticks(os.getpid()))
		finally:
			child.kill()
			child.wait()

	def test_missing_process_is_none(self):
		self.assertIsNone(_start_ticks(999999))

class TestEmptyAndFailedScans(unittest.TestCase):
	def test_nothing_running_announces_nothing(self):
		watcher,added,removed,active,all_=_watcher([set()])
		self.assertEqual(_scan(watcher,active,all_),set())
		self.assertEqual(added,[])

	def test_failed_active_query_retires_service_only_sessions(self):
		"""A service-only session has no local record, so a failed query loses it.

		That is the honest consequence of the service being the only source for
		those: there is nothing to fall back on. Registry sessions survive the
		same failure (tested above) because they are local.
		"""
		watcher,added,removed,active,all_=_watcher([{"ses_1"}])
		_scan(watcher,active,all_)
		with patch.object(service,"active_session_ids",return_value=None),patch.object(service,"all_sessions",return_value=None):
			self.assertEqual(watcher.run_once(),set())
		self.assertEqual(removed,["ses_1"])

	def test_failed_active_query_keeps_registry_sessions(self):
		"""The registry is local, so a dead service must not empty the panel."""
		with tempfile.TemporaryDirectory() as tmp:
			reg=Path(tmp)
			(reg/"ses_r1.json").write_text(json.dumps({"session_id":"ses_r1","role":"reviewer-1","agent":"reviewer","workspace":"/w","slot":1,"pid":os.getpid(),"start_ticks":_start_ticks(os.getpid())}))
			watcher=SessionWatcher("http://x","pw",on_new=lambda s:None,on_removed=lambda s:None,registry_dir=reg)
			with patch.object(service,"active_session_ids",return_value=None),patch.object(service,"all_sessions",return_value=None):
				self.assertEqual(watcher.run_once(),{"ses_r1"})

	def test_failed_metadata_query_keeps_previous_state(self):
		watcher,added,removed,active,all_=_watcher([set()])
		with patch.object(service,"active_session_ids",return_value={"ses_9"}),patch.object(service,"all_sessions",return_value=None):
			self.assertEqual(watcher.run_once(),set())
		self.assertEqual(added,[])

class TestStop(unittest.TestCase):
	def test_stop_is_idempotent(self):
		watcher,added,removed,active,all_=_watcher([set()])
		watcher.stop()
		watcher.stop()

if __name__=="__main__":
	unittest.main()
