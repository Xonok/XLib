"""Tests for the instance report and the join it enables.

`tools/marduk/_/instance.py` reads what the opencode processes write about
themselves, and `tools/marduk/_/session_watcher.py` joins that to the registry.
The join is what makes a window that has done a `/new` appear once, under its
own name, on the session it is actually on — instead of twice, once on a
session it left behind.

Run with: python3 dev/xtest/xtest.py tools/marduk/test/test_instance.py
"""
import json,os,sys,tempfile,time
from pathlib import Path

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/"dev"/"xtest"))
sys.path.insert(0,str(REPO))

import xtest
from tools.marduk import marduk as marduk_mod
from tools.marduk._ import service
from tools.marduk._.instance import read_instances,window_key
from tools.marduk._.process import start_ticks
from tools.marduk._.session_watcher import SessionWatcher
from tools.marduk._.state import AgentStatus

def _marduk():
	"""A Marduk with the service connection stubbed out."""
	with _patched(service,"resolve_url",lambda *_a,**_k:"http://127.0.0.1:1"),_patched(service,"password",lambda *_a,**_k:"pw"):
		return marduk_mod.Marduk()

class _patched:
	"""Replace a module function for the length of a block."""

	def __init__(self,module,name,value):
		self.module=module
		self.name=name
		self.value=value
		self.original=None

	def __enter__(self):
		self.original=getattr(self.module,self.name)
		setattr(self.module,self.name,self.value)
		return self

	def __exit__(self,*_):
		setattr(self.module,self.name,self.original)
		return False

def _registry(folder,session_id="ses_launch",role="secretary-3",pid=None):
	"""Write a registry entry: the session the window was launched with."""
	pid=os.getpid() if pid is None else pid
	entry={"session_id":session_id,"role":role,"agent":role.split("-")[0],"workspace":"/w","slot":1,
		"pid":pid,"start_ticks":start_ticks(pid),"started_at":int(time.time()*1000)}
	(Path(folder)/f"{session_id}.json").write_text(json.dumps(entry))

def _instance(folder,pid,session_id,cwd="/w"):
	"""Write the report a process writes about itself."""
	(Path(folder)/f"{pid}.json").write_text(json.dumps({"pid":pid,"cwd":cwd,"sessionID":session_id,"at":1700000000000}))

def _watcher(registry,instances):
	"""A watcher over the two local directories, with the service stubbed."""
	added=[]
	removed=[]
	watcher=SessionWatcher("http://x","pw",on_new=added.append,on_removed=removed.append,poll_seconds=0.01,
		registry_dir=registry,instances_dir=instances)
	return watcher,added,removed

def _scan(watcher,active=(),sessions=()):
	"""One scan, with the service replaced by fixed answers."""
	with _patched(service,"active_session_ids",lambda *_a,**_k:set(active)),_patched(service,"all_sessions",lambda *_a,**_k:list(sessions)):
		return watcher.run_once()

def test_a_report_is_read_and_keyed_by_its_pid():
	with tempfile.TemporaryDirectory() as folder:
		_instance(folder,os.getpid(),"ses_now")
		reports=read_instances(Path(folder))
		xtest.equal(sorted(reports),[os.getpid()])
		xtest.equal(reports[os.getpid()]["sessionID"],"ses_now")

def test_a_report_whose_process_is_gone_is_reaped():
	"""A process killed outright never removes its own file."""
	with tempfile.TemporaryDirectory() as folder:
		path=Path(folder)/"999999.json"
		path.write_text(json.dumps({"pid":999999,"cwd":"/w","sessionID":"ses_dead","at":1}))
		xtest.equal(read_instances(Path(folder)),{})
		xtest.true(not path.exists(),"the stale file is deleted")

def test_a_report_without_a_pid_is_reaped():
	with tempfile.TemporaryDirectory() as folder:
		path=Path(folder)/"x.json"
		path.write_text(json.dumps({"cwd":"/w","sessionID":"ses_now"}))
		xtest.equal(read_instances(Path(folder)),{})
		xtest.true(not path.exists(),"a report with no pid names no process")

def test_a_malformed_report_is_skipped():
	with tempfile.TemporaryDirectory() as folder:
		(Path(folder)/"broken.json").write_text("{not json")
		_instance(folder,os.getpid(),"ses_ok")
		reports=read_instances(Path(folder))
		xtest.equal(sorted(reports),[os.getpid()],"the good report is still read")

def test_a_window_is_filed_under_the_session_its_process_is_on():
	"""The whole point: the window's session is the one it is on now."""
	with tempfile.TemporaryDirectory() as folder:
		registry=Path(folder)/"registry"
		instances=Path(folder)/"instances"
		registry.mkdir()
		instances.mkdir()
		_registry(registry,"ses_launch")
		_instance(instances,os.getpid(),"ses_now")
		watcher,added,_removed=_watcher(registry,instances)
		xtest.equal(_scan(watcher),{"ses_now"})
		xtest.equal(added[0]["title"],"secretary-3","the window keeps its own name")
		xtest.equal(added[0]["location"]["directory"],"/w","and its own workspace")

def test_the_session_the_window_left_behind_is_not_shown():
	with tempfile.TemporaryDirectory() as folder:
		registry=Path(folder)/"registry"
		instances=Path(folder)/"instances"
		registry.mkdir()
		instances.mkdir()
		_registry(registry,"ses_launch")
		_instance(instances,os.getpid(),"ses_now")
		watcher,_added,_removed=_watcher(registry,instances)
		xtest.not_equal(_scan(watcher),{"ses_launch"},"the launch session is not on the panel")

def test_a_window_with_no_session_is_filed_under_its_own_key():
	"""Between a `/new` and the first message of the new one, the window is on
	no session at all — and it still belongs on the panel, once."""
	with tempfile.TemporaryDirectory() as folder:
		registry=Path(folder)/"registry"
		instances=Path(folder)/"instances"
		registry.mkdir()
		instances.mkdir()
		_registry(registry,"ses_launch")
		_instance(instances,os.getpid(),None)
		watcher,added,_removed=_watcher(registry,instances)
		xtest.equal(_scan(watcher),{window_key(os.getpid())})
		xtest.equal(added[0]["title"],"secretary-3","the window is still named")

def test_a_window_that_never_reported_keeps_its_launch_session():
	"""A TUI started before the plugin existed has no report, so the launch
	session is the best that is known."""
	with tempfile.TemporaryDirectory() as folder:
		registry=Path(folder)/"registry"
		instances=Path(folder)/"instances"
		registry.mkdir()
		instances.mkdir()
		_registry(registry,"ses_launch")
		watcher,_added,_removed=_watcher(registry,instances)
		xtest.equal(_scan(watcher),{"ses_launch"})

def test_a_service_only_session_is_still_shown():
	with tempfile.TemporaryDirectory() as folder:
		registry=Path(folder)/"registry"
		instances=Path(folder)/"instances"
		registry.mkdir()
		instances.mkdir()
		watcher,_added,_removed=_watcher(registry,instances)
		sessions=[{"id":"ses_raw","agent":"programmer","title":"programmer","location":{"directory":"/p"}}]
		xtest.equal(_scan(watcher,active={"ses_raw"},sessions=sessions),{"ses_raw"})

def test_a_window_with_no_session_is_shown_as_idle_and_does_not_warn():
	"""There is no event stream behind a window that is on no session, so its
	silence says nothing — and its age is the window's own age."""
	with tempfile.TemporaryDirectory() as folder:
		registry=Path(folder)/"registry"
		instances=Path(folder)/"instances"
		registry.mkdir()
		instances.mkdir()
		_registry(registry,"ses_launch")
		_instance(instances,os.getpid(),None)
		watcher,added,_removed=_watcher(registry,instances)
		_scan(watcher)
		m=_marduk()
		for session in added:
			m._on_new_session(session)
		agent=next(iter(m._agents.values()))
		xtest.equal(agent.status,AgentStatus.IDLE)
		xtest.true(agent.no_session,"the window is marked as having no session")
		m._check_warnings()
		xtest.true(not agent.warn_sse_silence,"a window with no session does not warn about silence")
		xtest.equal(agent.last_event_ts,agent.started_at,"the age shown is the window's own age")

def test_the_panel_shows_one_line_for_a_window_that_did_a_new():
	"""The complaint, at the level the complaint was made: one window, one line."""
	with tempfile.TemporaryDirectory() as folder:
		registry=Path(folder)/"registry"
		instances=Path(folder)/"instances"
		registry.mkdir()
		instances.mkdir()
		_registry(registry,"ses_launch")
		_instance(instances,os.getpid(),"ses_now")
		watcher,added,_removed=_watcher(registry,instances)
		_scan(watcher)
		m=_marduk()
		for session in added:
			m._on_new_session(session)
		xtest.equal(len(m._agents),1,"one window, one agent")
		xtest.equal(next(iter(m._agents.values())).role,"secretary-3")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
