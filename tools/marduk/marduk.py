#!/usr/bin/env python3
"""Marduk - Real-Time Agent Status Monitor.

Terminal contract: TERMINAL.md.
"""

import argparse,contextlib,shutil,signal,sys,termios,threading,time
from pathlib import Path
from ._ import service
from ._.sse_client import create_sse_client
from ._.session_watcher import REGISTRY_DIR,SessionWatcher
from ._.state import AgentState,AgentStatus,parse_event,format_age

_ENTER_WATCH="\033[?25l\033[?1049h"
_LEAVE_WATCH="\033[?25h\033[?1049l"

@contextlib.contextmanager
def _fullscreen():
	"""Watch mode owns the pane: no cursor, and no scrollback of old frames."""
	_stdin_fd = None
	_old_attrs = None
	if sys.stdin.isatty():
		try:
			_stdin_fd = sys.stdin.fileno()
			_old_attrs = termios.tcgetattr(_stdin_fd)
			_new_attrs = termios.tcgetattr(_stdin_fd)
			_new_attrs[3] &= ~(termios.ECHO | getattr(termios, "ECHOCTL", 0))
			termios.tcsetattr(_stdin_fd, termios.TCSANOW, _new_attrs)
		except (termios.error, OSError, AttributeError):
			_stdin_fd = None
			_old_attrs = None
	sys.stdout.write(_ENTER_WATCH)
	sys.stdout.flush()
	try:
		yield
	finally:
		if _old_attrs is not None and _stdin_fd is not None:
			try:
				termios.tcsetattr(_stdin_fd, termios.TCSANOW, _old_attrs)
			except (termios.error, OSError):
				pass
		sys.stdout.write(_LEAVE_WATCH)
		sys.stdout.flush()

class Marduk:
	"""Main Marduk monitor."""

	def __init__(self,poll_seconds:float=1.0,warn_sse_secs:int=60,warn_age_hours:int=24,compact:bool=False,registry_dir:Path=REGISTRY_DIR):
		self.poll_seconds=poll_seconds
		self.warn_sse_secs=warn_sse_secs
		self.warn_age_hours=warn_age_hours
		self.compact=compact
		self.registry_dir=registry_dir
		self.base_url=service.resolve_url()
		self.pw=service.password()
		self.error="" if self.base_url and self.pw else "opencode service not reachable"
		self._agents:dict[str,AgentState]={}
		self._client=None
		self._running=False

	def _start_events(self):
		"""Open the shared event stream; it carries every session at once."""
		if self._client or not self.base_url:
			return
		headers=service.auth_headers(self.pw)
		self._client=create_sse_client(f"{self.base_url}/api/event",on_event=self._on_event,on_disconnect=self._on_stream_down,headers=headers)
		threading.Thread(target=self._client.run,daemon=True).start()

	def _on_stream_down(self):
		"""The shared stream dropped; mark every agent disconnected."""
		now=time.time()
		for agent in self._agents.values():
			agent.status=AgentStatus.DISCONNECTED
			agent.disconnected_at=now

	def _on_new_session(self,session:dict):
		"""Register a session to show, from the registry or the service."""
		session_id=session.get("id")
		if not session_id:
			return
		created=(session.get("time") or {}).get("created")
		if not isinstance(created,(int,float)):
			created=session.get("started_at")
		started=created/1000 if isinstance(created,(int,float)) else time.time()
		if session_id not in self._agents:
			state=AgentState(session_id=session_id,role=session.get("title") or session.get("agent") or "unknown",port=0,pid=0,started_at=started,workspace=service.session_workspace(session))
			if session.get("window"):
				# A window with no session: there is no event stream to be silent
				# about, so its age is the window's own age.
				state.no_session=True
				state.last_event_ts=started
			self._agents[session_id]=state
			return
		# Already known: refresh what the registry can correct, but keep the
		# status and age, which only the event stream knows.
		agent=self._agents[session_id]
		role=session.get("title") or session.get("agent")
		if role:
			agent.role=role
		workspace=service.session_workspace(session)
		if workspace:
			agent.workspace=workspace

	def _on_removed_session(self,session_id:str):
		"""Forget a session that is no longer running."""
		self._agents.pop(session_id,None)

	def _on_event(self,event_type:str,data:dict):
		"""Route one event to whichever session it belongs to."""
		session_id=None
		if isinstance(data,dict):
			session_id=data.get("sessionID")
			if not session_id and isinstance(data.get("data"),dict):
				session_id=data["data"].get("sessionID")
		agent=self._agents.get(session_id)
		if agent:
			parse_event(event_type,data,agent)

	def _check_warnings(self):
		"""Update warning markers for agents."""
		now=time.time()
		for agent in self._agents.values():
			sse_silent=now-agent.last_event_ts if agent.last_event_ts else float("inf")
			file_age_hours=(now-agent.started_at)/3600
			warn=False
			if not agent.no_session:
				# A window with no session has no event stream, so its silence
				# says nothing; only its age can warn.
				if sse_silent>self.warn_sse_secs:
					warn=True
			if file_age_hours>self.warn_age_hours:
				warn=True
			agent.warn_sse_silence=warn

	def _visible_len(self, s: str) -> int:
		"""Return visible length of string (strip ANSI escape codes)."""
		import re
		return len(re.sub(r"\033\[[0-9;]*m", "", s))

	def _pad_status(self, status: str, width: int = 10) -> str:
		"""Pad status to width based on visible characters, preserving ANSI codes."""
		vis = self._visible_len(status)
		if vis < width:
			return status + " " * (width - vis)
		return status

	def _fit_visible(self, text: str, width: int) -> str:
		"""Cut a line to the pane width, counting visible characters only."""
		if self._visible_len(text) <= width:
			return text
		import re
		out=[]
		visible=0
		index=0
		while index<len(text) and visible<max(width-1,0):
			match=re.match(r"\033\[[0-9;]*m",text[index:])
			if match:
				out.append(match.group(0))
				index+=len(match.group(0))
				continue
			out.append(text[index])
			visible+=1
			index+=1
		return "".join(out)+"…\033[0m"

	def _status_color(self, status_text: str) -> str:
		"""Return ANSI-colored status string."""
		code = {
			"idle": "\033[36m", # cyan
			"working": "\033[33m", # yellow
			"delegating": "\033[35m",# magenta
			"question": "\033[34m", # blue
			"retry": "\033[31m", # red
			"disconnected": "\033[2m",# dim
		}.get(status_text.split("⚠")[0], "")
		reset = "\033[0m"
		return f"{code}{status_text}{reset}"

	def _format_detail(self, agent):
		"""Format detail column per SPEC."""
		if agent.status==AgentStatus.QUESTION:
			return "?"
		if agent.status==AgentStatus.WORKING and agent.current_tool:
			if agent.current_tool in ("step","text","reasoning"):
				return f"{agent.current_tool}:read"
			return agent.current_tool
		if agent.status==AgentStatus.DELEGATING:
			return "task"
		return ""

	def _cleanup_disconnected(self):
		"""Clear agents disconnected for more than 10 seconds."""
		now=time.time()
		to_remove=[]
		for session_id,agent in list(self._agents.items()):
			if agent.status==AgentStatus.DISCONNECTED and agent.disconnected_at is not None:
				if now-agent.disconnected_at>10:
					to_remove.append(session_id)
		for session_id in to_remove:
			self._agents.pop(session_id,None)

	def _render(self, height=None, width=None):
		"""Render current state, using the rows the pane actually has.

		The body is capped at the pane height: a list of agents that runs past
		the bottom would push the header out of sight, so what is left over
		becomes one `… +N more` line instead. The width does the same job for
		the long fields: a narrow pane goes compact, and a line that still
		does not fit is cut rather than wrapped.
		"""
		self._cleanup_disconnected()
		self._check_warnings()
		if height is None or width is None:
			size=shutil.get_terminal_size((80,24))
			if height is None:
				height=size.lines
			if width is None:
				width=size.columns
		compact=self.compact or width<46
		workspaces:dict[str,list[AgentState]]={}
		for agent in self._agents.values():
			ws=getattr(agent,"workspace",None) or "XLib"
			if ws not in workspaces:
				workspaces[ws]=[]
			workspaces[ws].append(agent)
		for ws_agents in workspaces.values():
			ws_agents.sort(key=lambda a:a.role)
		header=["=== Marduk (Live) ===",""]
		body=[]
		for ws_name,ws_agents in sorted(workspaces.items()):
			body.append(("workspace",self._fit_visible(ws_name,width)))
			for agent in ws_agents:
				status=agent.status.value
				if agent.warn_sse_silence:
					status+="⚠"
				status=self._status_color(status)
				detail=self._format_detail(agent)
				age=format_age(time.time()-agent.last_event_ts) if agent.last_event_ts else "?"
				if compact:
					status=self._pad_status(status, 7)
					line=f" {agent.role[:8]:8} {status} {detail[:10]:10} {age:>5}"
				else:
					status=self._pad_status(status, 10)
					line=f"  {agent.role[:12]:12} {status} {detail[:12]:12} {age:>6}"
				body.append(("agent",self._fit_visible(line,width)))
		if not self._agents:
			body.append(("message",self.error or "no agents connected"))
		if height <= len(header):
			lines=header[:max(height,0)]
		else:
			room=height-len(header)
			shown=body[:room]
			if room>0 and any(kind=="agent" for kind,_ in body[room:]):
				shown=body[:room-1]
				hidden_agents=sum(1 for kind,_ in body[room-1:] if kind=="agent")
				shown.append(("message",f"… +{hidden_agents} more"))
			lines=header+[line for _,line in shown]
		# A newline after a full frame would scroll the first line away; only
		# a frame with room to spare gets one, so a shell prompt starts clean.
		text="\n".join(lines)
		if len(lines)<height:
			text+="\n"
		sys.stdout.write("\033[H\033[2J")
		sys.stdout.write(text)
		sys.stdout.flush()

	def run_once(self):
		"""Run one scan and exit (--once mode)."""
		watcher=self._watcher()
		watcher.run_once()
		self._start_events()
		time.sleep(3.0)
		self._render()
		if self._client:
			self._client.stop()

	def _watcher(self) -> SessionWatcher:
		"""A session watcher wired to this monitor's callbacks."""
		return SessionWatcher(self.base_url,self.pw,on_new=self._on_new_session,on_removed=self._on_removed_session,poll_seconds=max(self.poll_seconds,2.0),registry_dir=self.registry_dir)

	def run_watch(self):
		"""Run continuous watch loop."""
		self._running=True
		def signal_handler(signum,frame):
			self._running=False
		signal.signal(signal.SIGTERM,signal_handler)
		signal.signal(signal.SIGINT,signal_handler)
		watcher=self._watcher()
		watcher_thread=threading.Thread(target=watcher.run_watch,daemon=True)
		watcher_thread.start()
		self._start_events()
		with _fullscreen():
			try:
				while self._running:
					self._render()
					time.sleep(1.0)
			finally:
				watcher.stop()
				if self._client:
					self._client.stop()

def main():
	parser=argparse.ArgumentParser(description="Marduk - Real-Time Agent Status Monitor")
	parser.add_argument("--watch",action="store_true",default=True,help="Watch mode (default)")
	parser.add_argument("--once",action="store_true",help="One-shot mode")
	parser.add_argument("--registry-dir",type=Path,default=REGISTRY_DIR,help="oc-agent registry directory")
	parser.add_argument("--poll-seconds",type=float,default=2.0,help="Session poll interval")
	parser.add_argument("--warn-sse-secs",type=int,default=60,help="SSE silence warning threshold")
	parser.add_argument("--warn-age-hours",type=int,default=24,help="File age warning threshold")
	parser.add_argument("--compact",action="store_true",help="Compact mode for narrow panes")
	args=parser.parse_args()
	marduk=Marduk(poll_seconds=args.poll_seconds,warn_sse_secs=args.warn_sse_secs,warn_age_hours=args.warn_age_hours,compact=args.compact,registry_dir=args.registry_dir)
	if args.once:
		marduk.run_once()
	else:
		marduk.run_watch()
	return 0

if __name__=="__main__":
	sys.exit(main())
