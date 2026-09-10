#!/usr/bin/env python3
"""Marduk - Real-Time Agent Status Monitor."""

import argparse,signal,sys,time
from pathlib import Path
from ._.port_watcher import PortWatcher
from ._.sse_client import create_sse_client
from ._.state import AgentState,AgentStatus,parse_event,format_age

class Marduk:
	"""Main Marduk monitor."""

	def __init__(self,ports_dir:Path,poll_seconds:float=1.0,warn_sse_secs:int=60,warn_age_hours:int=24,compact:bool=False):
		self.ports_dir=ports_dir
		self.poll_seconds=poll_seconds
		self.warn_sse_secs=warn_sse_secs
		self.warn_age_hours=warn_age_hours
		self.compact=compact
		self._agents:dict[str,AgentState]={}
		self._port_to_session:dict[int,str]={}
		self._running=False

	def _on_new_port(self,port_file):
		"""Handle new port file."""
		if port_file.session_id in self._agents:
			agent=self._agents[port_file.session_id]
			old_port=agent.port
			agent.port=port_file.port
			agent.pid=port_file.pid
			if old_port!=port_file.port and old_port in self._port_to_session:
				del self._port_to_session[old_port]
			self._port_to_session[port_file.port]=port_file.session_id
			return
		agent=AgentState(session_id=port_file.session_id,role=port_file.role,port=port_file.port,pid=port_file.pid,started_at=port_file.started_at)
		self._agents[port_file.session_id]=agent
		self._port_to_session[port_file.port]=port_file.session_id
		url=f"http://127.0.0.1:{port_file.port}/event"
		client=create_sse_client(url,on_event=lambda et,data:self._on_event(port_file.session_id,et,data),on_disconnect=lambda:self._on_disconnect(port_file.session_id))
		agent._sse_client=client
		import threading
		threading.Thread(target=client.run,daemon=True).start()

	def _on_removed_port(self,port:int):
		"""Handle port file removal."""
		session_id=self._port_to_session.pop(port,None)
		if session_id and session_id in self._agents:
			agent=self._agents[session_id]
			if agent.port==port:
				agent=self._agents.pop(session_id)
				if hasattr(agent,"_sse_client"):
					agent._sse_client.stop()

	def _on_event(self,session_id:str,event_type:str,data:dict):
		"""Handle SSE event."""
		agent=self._agents.get(session_id)
		if agent:
			parse_event(event_type,data,agent)

	def _on_disconnect(self,session_id:str):
		"""Handle SSE disconnect."""
		agent=self._agents.get(session_id)
		if agent:
			agent.status=AgentStatus.DISCONNECTED
			agent.disconnected_at=time.time()

	def _check_warnings(self):
		"""Update warning markers for agents."""
		now=time.time()
		for agent in self._agents.values():
			sse_silent=now-agent.last_event_ts if agent.last_event_ts else float("inf")
			file_age_hours=(now-agent.started_at)/3600
			warn=False
			if sse_silent>self.warn_sse_secs:
				warn=True
			if file_age_hours>self.warn_age_hours:
				warn=True
			agent.warn_sse_silence=warn

	def _format_detail(self,agent):
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
			agent_to_remove=self._agents.pop(session_id,None)
			if agent_to_remove:
				port=agent_to_remove.port
				if port in self._port_to_session:
					del self._port_to_session[port]
				if agent_to_remove._sse_client is not None:
					agent_to_remove._sse_client.stop()

	def _render(self):
		"""Render current state."""
		self._cleanup_disconnected()
		self._check_warnings()
		workspaces:dict[str,list[AgentState]]={}
		for agent in self._agents.values():
			ws=getattr(agent,"workspace",None) or "XLib"
			if ws not in workspaces:
				workspaces[ws]=[]
			workspaces[ws].append(agent)
		for ws_agents in workspaces.values():
			ws_agents.sort(key=lambda a:a.role)
		lines=["=== Marduk (Live) ===",""]
		for ws_name,ws_agents in sorted(workspaces.items()):
			lines.append(ws_name)
			for agent in ws_agents:
				status=agent.status.value
				if agent.warn_sse_silence:
					status+="⚠"
				detail=self._format_detail(agent)
				age=format_age(time.time()-agent.last_event_ts) if agent.last_event_ts else "?"
				if self.compact:
					lines.append(f" {agent.role[:8]:8} {status[:7]:7} {detail[:10]:10} {age:>5}")
				else:
					lines.append(f"  {agent.role:<12} {status:<10} {detail:<12} {age:>6}")
		if not self._agents:
			lines.append("no agents connected")
		sys.stdout.write("\033[H\033[2J")
		sys.stdout.write("\n".join(lines)+"\n")
		sys.stdout.flush()

	def run_once(self):
		"""Run one scan and exit (--once mode)."""
		watcher=PortWatcher(self.ports_dir,on_new=self._on_new_port,on_removed=self._on_removed_port,poll_seconds=self.poll_seconds)
		watcher.run_once()
		time.sleep(3.0)
		self._render()

	def run_watch(self):
		"""Run continuous watch loop."""
		self._running=True
		def signal_handler(signum,frame):
			self._running=False
		signal.signal(signal.SIGTERM,signal_handler)
		signal.signal(signal.SIGINT,signal_handler)
		watcher=PortWatcher(self.ports_dir,on_new=self._on_new_port,on_removed=self._on_removed_port,poll_seconds=self.poll_seconds)
		import threading
		watcher_thread=threading.Thread(target=watcher.run_watch,daemon=True)
		watcher_thread.start()
		try:
			while self._running:
				self._render()
				time.sleep(1.0)
		finally:
			watcher.stop()
			for agent in self._agents.values():
				if hasattr(agent,"_sse_client"):
					agent._sse_client.stop()

def main():
	parser=argparse.ArgumentParser(description="Marduk - Real-Time Agent Status Monitor")
	parser.add_argument("--watch",action="store_true",default=True,help="Watch mode (default)")
	parser.add_argument("--once",action="store_true",help="One-shot mode")
	parser.add_argument("--ports-dir",type=Path,default=Path.home()/".opencode"/"ports",help="Port files directory")
	parser.add_argument("--poll-seconds",type=float,default=1.0,help="Poll interval (fallback)")
	parser.add_argument("--warn-sse-secs",type=int,default=60,help="SSE silence warning threshold")
	parser.add_argument("--warn-age-hours",type=int,default=24,help="File age warning threshold")
	parser.add_argument("--compact",action="store_true",help="Compact mode for narrow panes")
	args=parser.parse_args()
	marduk=Marduk(ports_dir=args.ports_dir,poll_seconds=args.poll_seconds,warn_sse_secs=args.warn_sse_secs,warn_age_hours=args.warn_age_hours,compact=args.compact)
	if args.once:
		marduk.run_once()
	else:
		marduk.run_watch()
	return 0

if __name__=="__main__":
	sys.exit(main())
