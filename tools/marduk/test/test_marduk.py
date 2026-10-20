#!/usr/bin/env python3
"""
Tests for event routing and rendering — tools/marduk/marduk.py.

Run with: python3 -m unittest tools.marduk.test.test_marduk -v

The constructor resolves the service URL by shelling out to the opencode CLI,
so both that and the password are patched. No test here starts a thread or
opens a socket: `_start_events` is never called, and routing is exercised
directly through `_on_event`, which is where the real risk lives.

The thing worth guarding is session routing. v2 replaced one SSE stream per
agent with a single shared stream carrying every session, so every event is now
dispatched by its `sessionID`. Getting that wrong does not crash — it silently
updates the wrong agent's status, which is the failure a panel cannot show you.
"""
import io,unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from tools.marduk import marduk as marduk_mod
from tools.marduk._.state import AgentStatus

def _marduk(**kw) -> marduk_mod.Marduk:
	"""A Marduk with the service connection stubbed out."""
	with patch.object(marduk_mod.service,"resolve_url",return_value="http://127.0.0.1:1"),patch.object(marduk_mod.service,"password",return_value="pw"):
		return marduk_mod.Marduk(**kw)

def _session(session_id="ses_1",agent="secretary",directory="/w") -> dict:
	return {"id":session_id,"agent":agent,"location":{"directory":directory},"time":{"created":1000000}}

def _event(session_id="ses_1",event_type="session.step.started",**data) -> dict:
	return {"id":"evt_1","type":event_type,"data":{"sessionID":session_id,**data}}

class TestRegistration(unittest.TestCase):
	def test_session_is_registered_with_its_agent(self):
		m=_marduk()
		m._on_new_session(_session(agent="reviewer"))
		self.assertEqual(len(m._agents),1)
		self.assertEqual(next(iter(m._agents.values())).role,"reviewer")

	def test_workspace_is_carried_through(self):
		m=_marduk()
		m._on_new_session(_session(directory="/srv/agents"))
		self.assertEqual(next(iter(m._agents.values())).workspace,"/srv/agents")

	def test_repeat_registration_keeps_the_same_object(self):
		"""A fresh AgentState would reset the event age every poll."""
		m=_marduk()
		m._on_new_session(_session())
		first=next(iter(m._agents.values()))
		m._on_new_session(_session())
		self.assertEqual(len(m._agents),1)
		self.assertIs(next(iter(m._agents.values())),first)

	def test_repeat_registration_refreshes_the_role(self):
		"""The registry knows the slot suffix; the service title does not."""
		m=_marduk()
		m._on_new_session(_session())
		m._on_new_session({"id":"ses_1","title":"secretary-4","location":{"directory":"/other"}})
		agent=m._agents["ses_1"]
		self.assertEqual(agent.role,"secretary-4")
		self.assertEqual(agent.workspace,"/other")

	def test_repeat_registration_keeps_status_and_age(self):
		"""The registry says nothing about what the agent is doing."""
		m=_marduk()
		m._on_new_session(_session())
		m._on_event("session.step.started",_event("ses_1"))
		agent=m._agents["ses_1"]
		age=agent.last_event_ts
		m._on_new_session({"id":"ses_1","title":"secretary-4"})
		self.assertEqual(agent.status,AgentStatus.WORKING)
		self.assertEqual(agent.last_event_ts,age)

	def test_registry_started_at_is_used_when_there_is_no_time_block(self):
		m=_marduk()
		m._on_new_session({"id":"ses_1","title":"secretary-1","started_at":1700000000000})
		self.assertAlmostEqual(m._agents["ses_1"].started_at,1700000000.0,places=0)

	def test_missing_agent_name_falls_back(self):
		m=_marduk()
		m._on_new_session({"id":"ses_1"})
		self.assertEqual(next(iter(m._agents.values())).role,"unknown")

	def test_session_without_id_is_ignored(self):
		m=_marduk()
		m._on_new_session({"agent":"secretary"})
		self.assertEqual(m._agents,{})

	def test_removal_forgets_the_session(self):
		m=_marduk()
		m._on_new_session(_session())
		m._on_removed_session("ses_1")
		self.assertEqual(m._agents,{})

	def test_removing_an_unknown_session_is_harmless(self):
		m=_marduk()
		m._on_removed_session("ses_nope")

class TestRouting(unittest.TestCase):
	def test_event_reaches_its_own_session(self):
		m=_marduk()
		m._on_new_session(_session("ses_1","a"))
		m._on_new_session(_session("ses_2","b"))
		m._on_event("session.execution.started",_event("ses_1"))
		self.assertEqual(m._agents["ses_1"].status,AgentStatus.WORKING)
		self.assertEqual(m._agents["ses_2"].status,AgentStatus.IDLE)

	def test_tool_event_reaches_only_its_session(self):
		m=_marduk()
		m._on_new_session(_session("ses_1","a"))
		m._on_new_session(_session("ses_2","b"))
		m._on_event("session.tool.input.started",_event("ses_1",id="call_1",name="shell"))
		self.assertEqual(m._agents["ses_1"].current_tool,"shell")
		self.assertIsNone(m._agents["ses_2"].current_tool)

	def test_unknown_session_is_ignored(self):
		m=_marduk()
		m._on_new_session(_session("ses_1"))
		m._on_event("session.step.started",_event("ses_gone"))

	def test_event_without_a_session_is_ignored(self):
		m=_marduk()
		m._on_new_session(_session("ses_1"))
		m._on_event("server.connected",{"type":"server.connected","data":{}})

	def test_malformed_event_does_not_crash(self):
		m=_marduk()
		m._on_new_session(_session("ses_1"))
		m._on_event("session.step.started",{"type":"session.step.started"})
		m._on_event("session.step.started",{"type":"session.step.started","data":None})

class TestStreamLoss(unittest.TestCase):
	def test_dropped_stream_disconnects_everyone(self):
		m=_marduk()
		m._on_new_session(_session("ses_1","a"))
		m._on_new_session(_session("ses_2","b"))
		m._on_stream_down()
		self.assertTrue(all(a.status==AgentStatus.DISCONNECTED for a in m._agents.values()))

	def test_disconnect_is_timestamped_for_cleanup(self):
		m=_marduk()
		m._on_new_session(_session("ses_1"))
		m._on_stream_down()
		self.assertIsNotNone(m._agents["ses_1"].disconnected_at)

class TestErrorReporting(unittest.TestCase):
	def test_unreachable_service_is_reported(self):
		"""An empty panel must say why, not just show nothing."""
		with patch.object(marduk_mod.service,"resolve_url",return_value=""),patch.object(marduk_mod.service,"password",return_value="pw"):
			m=marduk_mod.Marduk()
		self.assertTrue(m.error)
		out=io.StringIO()
		with redirect_stdout(out):
			m._render()
		self.assertIn(m.error,out.getvalue())

	def test_empty_but_reachable_says_no_agents(self):
		m=_marduk()
		self.assertEqual(m.error,"")
		out=io.StringIO()
		with redirect_stdout(out):
			m._render()
		self.assertIn("no agents connected",out.getvalue())

class TestRendering(unittest.TestCase):
	def test_render_groups_by_workspace(self):
		m=_marduk()
		m._on_new_session(_session("ses_1","secretary","/w/a"))
		m._on_new_session(_session("ses_2","reviewer","/w/b"))
		out=io.StringIO()
		with redirect_stdout(out):
			m._render()
		self.assertIn("/w/a",out.getvalue())
		self.assertIn("/w/b",out.getvalue())

	def test_compact_render_still_lists_agents(self):
		m=_marduk(compact=True)
		m._on_new_session(_session("ses_1","secretary","/w"))
		out=io.StringIO()
		with redirect_stdout(out):
			m._render()
		self.assertIn("secretar",out.getvalue())

if __name__=="__main__":
	unittest.main()
