#!/usr/bin/env python3
"""
Tests for the v2 event mapping — tools/marduk/_/state.py.

Run with: python3 -m unittest tools.marduk.test.test_state -v

The v1 event names were all removed in OpenCode v2, so `parse_event_v2` is the
piece most likely to be wrong: every mapping here was read off a real captured
event stream, and a silent miss means marduk shows every agent as idle. The
shapes below are the payloads as the service actually sends them — `sessionID`
under `data`, tool names only on `session.tool.input.started`.
"""
import unittest
from tools.marduk._.state import AgentState,AgentStatus,parse_event,parse_event_v2

def _state() -> AgentState:
	"""A fresh agent to feed events into."""
	return AgentState(session_id="ses_1",role="secretary",port=0,pid=0)

def _event(event_type:str,**data) -> dict:
	"""A v2 event envelope, as the service sends it."""
	return {"id":"evt_1","type":event_type,"data":{"sessionID":"ses_1",**data}}

class TestExecutionStatus(unittest.TestCase):
	def test_execution_started_is_working(self):
		state=_state()
		parse_event("session.execution.started",_event("session.execution.started"),state)
		self.assertEqual(state.status,AgentStatus.WORKING)

	def test_execution_succeeded_is_idle(self):
		state=_state()
		state.status=AgentStatus.WORKING
		state.current_tool="shell"
		parse_event("session.execution.succeeded",_event("session.execution.succeeded"),state)
		self.assertEqual(state.status,AgentStatus.IDLE)

	def test_execution_succeeded_clears_stale_tool(self):
		"""Idle with a leftover tool name would render as `idle shell`."""
		state=_state()
		state.current_tool="shell"
		parse_event("session.execution.succeeded",_event("session.execution.succeeded"),state)
		self.assertIsNone(state.current_tool)

	def test_execution_failed_is_retry(self):
		state=_state()
		parse_event("session.execution.failed",_event("session.execution.failed"),state)
		self.assertEqual(state.status,AgentStatus.RETRY)

class TestStepAndText(unittest.TestCase):
	def test_step_started_is_working_step(self):
		state=_state()
		parse_event("session.step.started",_event("session.step.started",assistantMessageID="msg_1"),state)
		self.assertEqual(state.status,AgentStatus.WORKING)
		self.assertEqual(state.current_tool,"step")

	def test_text_started_is_working_text(self):
		state=_state()
		parse_event("session.text.started",_event("session.text.started",ordinal=0),state)
		self.assertEqual(state.status,AgentStatus.WORKING)
		self.assertEqual(state.current_tool,"text")

class TestToolNaming(unittest.TestCase):
	def test_tool_name_comes_from_input_started(self):
		"""The name is only here; `session.tool.called` carries just an id."""
		state=_state()
		parse_event("session.tool.input.started",_event("session.tool.input.started",id="call_1",name="shell"),state)
		self.assertEqual(state.current_tool,"shell")
		self.assertEqual(state.status,AgentStatus.WORKING)

	def test_tool_called_resolves_name_by_id(self):
		"""The call itself carries no name, so the lookup must do the work.

		The name is seeded directly rather than by replaying the input event:
		if the correlation were removed, replaying it first would leave
		current_tool already correct and the test would pass vacuously.
		"""
		state=_state()
		state._tool_names["call_1"]="read"
		state.current_tool="step"
		parse_event("session.tool.called",_event("session.tool.called",id="call_1",input={}),state)
		self.assertEqual(state.current_tool,"read")
		self.assertEqual(state.status,AgentStatus.WORKING)

	def test_tool_called_uses_a_stale_name_when_the_id_is_unknown(self):
		"""A different id must not borrow another call's tool name."""
		state=_state()
		state._tool_names["call_1"]="read"
		parse_event("session.tool.called",_event("session.tool.called",id="call_2",input={}),state)
		self.assertNotEqual(state.current_tool,"read")

	def test_tool_called_with_unknown_id_is_harmless(self):
		"""A call whose naming event was never seen must not crash the panel."""
		state=_state()
		state.current_tool="shell"
		parse_event("session.tool.called",_event("session.tool.called",id="call_missing",input={}),state)
		self.assertEqual(state.current_tool,"shell")

	def test_task_tool_is_delegating(self):
		state=_state()
		parse_event("session.tool.input.started",_event("session.tool.input.started",id="call_2",name="task"),state)
		self.assertEqual(state.status,AgentStatus.DELEGATING)

	def test_subagent_tool_is_delegating(self):
		state=_state()
		parse_event("session.tool.input.started",_event("session.tool.input.started",id="call_3",name="subagent"),state)
		self.assertEqual(state.status,AgentStatus.DELEGATING)

	def test_tool_failed_is_retry(self):
		state=_state()
		parse_event("session.tool.failed",_event("session.tool.failed",id="call_1"),state)
		self.assertEqual(state.status,AgentStatus.RETRY)

	def test_agent_selected_is_delegating(self):
		state=_state()
		parse_event("session.agent.selected",_event("session.agent.selected",agent="reviewer",previous="build"),state)
		self.assertEqual(state.status,AgentStatus.DELEGATING)
		self.assertEqual(state.current_tool,"subagent")

class TestRecognitionAndLiveness(unittest.TestCase):
	def test_unrelated_event_is_not_claimed(self):
		"""Returning False is what lets v1 handling stay reachable."""
		self.assertFalse(parse_event_v2("server.connected",{"type":"server.connected","data":{}},_state()))

	def test_streaming_delta_counts_as_liveness(self):
		"""Otherwise a long reply trips the SSE-silence warning while healthy."""
		state=_state()
		state.last_event_ts=0.0
		parse_event("session.text.delta",_event("session.text.delta",ordinal=1),state)
		self.assertGreater(state.last_event_ts,0.0)

	def test_event_without_payload_does_not_crash(self):
		state=_state()
		parse_event("session.step.started",{"type":"session.step.started"},state)
		self.assertEqual(state.status,AgentStatus.WORKING)

class TestV1StillRecognised(unittest.TestCase):
	def test_v1_execution_style_status_still_maps(self):
		"""The v1 branches are retained deliberately; keep them working."""
		state=_state()
		parse_event("session.status",{"type":"session.status","status":"idle"},state)
		self.assertEqual(state.status,AgentStatus.IDLE)

	def test_v1_tool_call_still_maps(self):
		state=_state()
		parse_event("session.next.tool.called",{"type":"session.next.tool.called","tool":{"name":"write"}},state)
		self.assertEqual(state.current_tool,"write")
		self.assertEqual(state.status,AgentStatus.WORKING)

class TestAgentState(unittest.TestCase):
	def test_workspace_defaults_to_empty(self):
		self.assertEqual(_state().workspace,"")

	def test_workspace_is_carried_when_given(self):
		state=AgentState(session_id="ses_1",role="secretary",port=0,pid=0,workspace="/tmp/x")
		self.assertEqual(state.workspace,"/tmp/x")

if __name__=="__main__":
	unittest.main()
