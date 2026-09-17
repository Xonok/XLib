"""Port file watcher with inotify and poll fallback."""

import json,os,socket,time
from pathlib import Path
from typing import Callable,Optional

try:
	from inotify_simple import INotify,flags
	HAS_INOTIFY=True
except ImportError:
	HAS_INOTIFY=False

class PortFile:
	"""Represents a parsed port file."""

	__slots__=("port","role","session_id","pid","started_at","path")

	def __init__(self,port:int,role:str,session_id:str,pid:int,started_at:float,path:Path):
		self.port=port
		self.role=role
		self.session_id=session_id
		self.pid=pid
		self.started_at=started_at
		self.path=path

	@classmethod
	def from_json(cls,path:Path,data:dict):
		"""Create PortFile from parsed JSON data."""
		required=("port","role","session_id","pid","started_at")
		for key in required:
			if key not in data:
				raise ValueError(f"Missing required field: {key}")
		return cls(port=int(data["port"]),role=str(data["role"]),session_id=str(data["session_id"]),pid=int(data["pid"]),started_at=float(data["started_at"]),path=path)

	def is_stale_pid(self):
		"""Check if the process is dead."""
		try:
			os.kill(self.pid,0)
			return False
		except ProcessLookupError:
			return True
		except PermissionError:
			return False

	def is_tcp_dead(self,timeout:float=0.5):
		"""Check if TCP connection to the port fails."""
		try:
			with socket.create_connection(("127.0.0.1",self.port),timeout=timeout):
				return False
		except (ConnectionRefusedError,socket.timeout,OSError):
			return True

def parse_port_file(path:Path):
	"""Parse a port file, returning None if invalid."""
	try:
		text=path.read_text()
		data=json.loads(text)
		return PortFile.from_json(path,data)
	except (json.JSONDecodeError,ValueError,OSError,KeyError,TypeError):
		return None

class PortWatcher:
	"""Watches a directory for port files."""

	def __init__(self,ports_dir:Path,on_new:Callable[[PortFile],None],on_removed:Callable[[int],None],poll_seconds:float=1.0):
		self.ports_dir=ports_dir
		self.on_new=on_new
		self.on_removed=on_removed
		self.poll_seconds=poll_seconds
		self._known_ports:dict[int,PortFile]={}
		self._running=False

	def scan_existing(self):
		"""Scan for existing port files on startup."""
		if not self.ports_dir.exists():
			return
		for path in self.ports_dir.glob("*.json"):
			port_file=parse_port_file(path)
			if port_file:
				self._known_ports[port_file.port]=port_file
				self.on_new(port_file)

	def _check_port_file(self,path:Path):
		"""Check a single port file for changes."""
		port_file=parse_port_file(path)
		if not port_file:
			return
		existing=self._known_ports.get(port_file.port)
		if existing is None:
			self._known_ports[port_file.port]=port_file
			self.on_new(port_file)
		elif existing.path.stat().st_mtime!=port_file.path.stat().st_mtime:
			self._known_ports[port_file.port]=port_file
			self.on_new(port_file)

	def _cleanup_stale(self):
		"""Remove stale port files (PID dead or TCP connect fails)."""
		to_remove=[]
		for port,port_file in self._known_ports.items():
			if port_file.is_stale_pid() or port_file.is_tcp_dead():
				to_remove.append(port)
		for port in to_remove:
			port_file=self._known_ports.pop(port)
			try:
				port_file.path.unlink(missing_ok=True)
			except OSError:
				pass
			self.on_removed(port)

	def run_once(self):
		"""Run one iteration of watching (for --once mode)."""
		self.scan_existing()
		self._cleanup_stale()

	def run_watch(self):
		"""Run continuous watching loop."""
		self._running=True
		self.scan_existing()
		if HAS_INOTIFY:
			self._run_inotify()
		else:
			self._run_poll()

	def _run_inotify(self):
		"""Run using inotify."""
		inotify=INotify()
		watch_flags=flags.CREATE|flags.MODIFY|flags.DELETE|flags.MOVED_TO
		inotify.add_watch(str(self.ports_dir),watch_flags)
		try:
			while self._running:
				for event in inotify.read(timeout=int(self.poll_seconds*1000)):
					if not self._running:
						break
					if event.mask&(flags.CREATE|flags.MODIFY|flags.MOVED_TO):
						path=self.ports_dir/event.name
						if path.suffix==".json":
							self._check_port_file(path)
					elif event.mask&flags.DELETE:
						try:
							port=int(event.name.replace(".json",""))
							if port in self._known_ports:
								self._known_ports.pop(port)
								self.on_removed(port)
						except ValueError:
							pass
				self._cleanup_stale()
		finally:
			inotify.close()

	def _run_poll(self):
		"""Run using polling fallback."""
		while self._running:
			time.sleep(self.poll_seconds)
			if not self._running:
				break
			self.scan_existing()
			self._cleanup_stale()

	def stop(self):
		"""Stop the watcher."""
		self._running=False
