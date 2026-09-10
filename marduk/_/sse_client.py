"""SSE client with reconnection logic."""

import json,time
from abc import ABC,abstractmethod
from typing import Callable

try:
	import httpx
	HAS_HTTPX=True
except ImportError:
	HAS_HTTPX=False
	import urllib.request,urllib.error

class SSEClient(ABC):
	"""Abstract SSE client."""

	def __init__(self,url:str,on_event:Callable[[str,dict],None],on_disconnect:Callable[[],None]):
		self.url=url
		self.on_event=on_event
		self.on_disconnect=on_disconnect
		self._running=False
		self._backoff=1.0
		self._max_backoff=30.0

	@abstractmethod
	def _connect(self):
		"""Connect and process events."""
		pass

	def run(self):
		"""Run the client with reconnection logic."""
		self._running=True
		while self._running:
			try:
				self._connect()
			except Exception:
				if not self._running:
					break
				self.on_disconnect()
				time.sleep(self._backoff)
				self._backoff=min(self._backoff*2,self._max_backoff)
			else:
				if self._running:
					self.on_disconnect()
				self._backoff=1.0

	def stop(self):
		"""Stop the client."""
		self._running=False

class HttpxSSEClient(SSEClient):
	"""SSE client using httpx."""

	def _connect(self):
		with httpx.stream("GET",self.url,timeout=None) as response:
			response.raise_for_status()
			self._process_stream(response.iter_lines())

	def _process_stream(self,lines):
		"""Process SSE stream lines."""
		event_type=None
		event_data=""
		for line in lines:
			if not self._running:
				break
			line=line.rstrip("\n")
			if not line:
				if event_data:
					try:
						data=json.loads(event_data)
						if not event_type and isinstance(data,dict) and isinstance(data.get("type"),str):
							event_type=data["type"]
						with open("/tmp/marduk_pipe/events.log","a") as f:
							f.write(f"{event_type}:{json.dumps(data)}\n")
						self.on_event(event_type or "",data)
					except json.JSONDecodeError:
						pass
				event_type=None
				event_data=""
				continue
			if line.startswith("event:"):
				event_type=line[6:].strip()
			elif line.startswith("data:"):
				event_data+=line[5:].lstrip()+"\n"

class UrllibSSEClient(SSEClient):
	"""SSE client using urllib (stdlib fallback)."""

	def _connect(self):
		req=urllib.request.Request(self.url,headers={"Accept":"text/event-stream"})
		with urllib.request.urlopen(req,timeout=None) as response:
			self._process_stream(response)

	def _process_stream(self,response):
		"""Process SSE stream from urllib response."""
		event_type=None
		event_data=""
		for raw_line in response:
			if not self._running:
				break
			line=raw_line.decode("utf-8").rstrip("\n")
			if not line:
				if event_data:
					try:
						data=json.loads(event_data)
						if not event_type and isinstance(data,dict) and isinstance(data.get("type"),str):
							event_type=data["type"]
						with open("/tmp/marduk_pipe/events.log","a") as f:
							f.write(f"{event_type}:{json.dumps(data)}\n")
						self.on_event(event_type or "",data)
					except json.JSONDecodeError:
						pass
				event_type=None
				event_data=""
				continue
			if line.startswith("event:"):
				event_type=line[6:].strip()
			elif line.startswith("data:"):
				event_data+=line[5:].lstrip()+"\n"

def create_sse_client(url:str,on_event:Callable[[str,dict],None],on_disconnect:Callable[[],None]):
	"""Create the best available SSE client."""
	if HAS_HTTPX:
		return HttpxSSEClient(url,on_event,on_disconnect)
	return UrllibSSEClient(url,on_event,on_disconnect)
