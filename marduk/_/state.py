"""Event parser and status inference."""

import time
from enum import Enum
from typing import Optional

class AgentStatus(Enum):
	"""Agent display status."""

	IDLE="idle"
	WORKING="working"
	DELEGATING="delegating"
	QUESTION="question"
	RETRY="retry"
	DISCONNECTED="disconnected"

class AgentState:
	"""In-memory state for a single agent."""

	__slots__=("session_id","role","status","current_tool","last_event_ts","port","pid","started_at","warn_sse_silence","_sse_client","disconnected_at")

	def __init__(self,session_id:str,role:str,port:int,pid:int,started_at:float=0.0):
		self.session_id=session_id
		self.role=role
		self.status=AgentStatus.IDLE
		self.current_tool:Optional[str]=None
		self.last_event_ts=time.time()
		self.port=port
		self.pid=pid
		self.started_at=started_at
		self.warn_sse_silence=False
		self.disconnected_at=None
		self._sse_client=None

def _payload(data:dict,event_type:str)->dict:
	"""Extract payload from full SSE event object."""
	if not isinstance(data,dict):
		return {}
	# If top-level already matches expected payload keys for this event, use directly.
	if event_type=="session.status":
		if "type" in data and data.get("type")!=event_type:
			return data
	# Nested under common wrapper keys.
	for k in ("data","properties","payload"):
		if k in data and isinstance(data[k],dict):
			nested=data[k]
			if event_type=="session.status" and "type" in nested:
				return nested
			if event_type=="session.next.tool.called" and ("tool" in nested or "name" in nested):
				return nested
			# For other events, prefer nested if it looks like payload (has event-specific keys or isn't just meta)
			if nested and ("type" in nested or "status" in nested or "tool" in nested or "step" in nested):
				return nested
	# Fallback: try direct but skip if top-level is purely meta (no payload keys)
	if "type" in data and data["type"]==event_type:
		payload_keys=set(data)-{"type","data","properties","payload"}
		if payload_keys:
			return data
		return {}
	return data

def parse_event(event_type:str,data:dict,state:AgentState):
	"""Parse an SSE event and update agent state."""
	now=time.time()
	payload=_payload(data,event_type)
	if event_type=="session.status":
		status_raw=payload.get("status") or payload.get("type","")
		if isinstance(status_raw,dict):
			status_type=status_raw.get("type","")
		else:
			status_type=str(status_raw)
		if status_type==event_type:  # meta wrapper: type is event name, not status
			status_type=payload.get("status","")
			if isinstance(status_type,dict):
				status_type=status_type.get("type","")
			else:
				status_type=str(status_type)
		if status_type=="idle":
			state.status=AgentStatus.IDLE
			state.current_tool=None
		elif status_type=="busy":
			state.status=AgentStatus.WORKING
		elif status_type=="retry":
			state.status=AgentStatus.RETRY
	elif event_type=="session.next.step.started":
		state.status=AgentStatus.WORKING
		state.current_tool="step"
	elif event_type=="session.next.text.started":
		state.status=AgentStatus.WORKING
		state.current_tool="text"
	elif event_type=="session.next.reasoning.started":
		state.status=AgentStatus.WORKING
		state.current_tool="reasoning"
	elif event_type=="session.next.tool.called":
		if isinstance(payload.get("tool"),dict):
			tool_name=payload["tool"].get("name","unknown")
		elif isinstance(payload.get("name"),str):
			tool_name=payload["name"]
		elif isinstance(payload,dict) and payload.get("type")==event_type:
			# payload was empty because top-level was event meta; try full data for tool name
			tool_name=data.get("tool",{}).get("name","unknown") if isinstance(data.get("tool"),dict) else (data.get("name") or "unknown")
		else:
			tool_name="unknown"
		state.current_tool=tool_name
		if tool_name=="task":
			state.status=AgentStatus.DELEGATING
		else:
			state.status=AgentStatus.WORKING
	elif event_type=="question.asked":
		state.status=AgentStatus.QUESTION
		state.current_tool="?"
	elif event_type=="permission.asked":
		state.status=AgentStatus.QUESTION
		state.current_tool="?"
	elif event_type=="session.next.agent.switched":
		state.status=AgentStatus.DELEGATING
		state.current_tool="subagent"
	if event_type not in ("ping","heartbeat","server.heartbeat"):
		state.last_event_ts=now
	# Note: question/permission status persists until cleared by session.status or step.event

def format_age(seconds:float):
	"""Format age as human-readable string."""
	if seconds<60:
		return f"{int(seconds)}s"
	elif seconds<3600:
		return f"{int(seconds/60)}m"
	else:
		hours=int(seconds/3600)
		minutes=int((seconds%3600)/60)
		if minutes:
			return f"{hours}h{minutes}m"
		return f"{hours}h"
