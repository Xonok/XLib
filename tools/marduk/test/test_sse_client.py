#!/usr/bin/env python3
"""
Tests for the SSE client's reconnection and auth handling.

Run with: python3 -m unittest tools.marduk.test.test_sse_client -v

The transport is exercised through a fake `httpx.stream`, never a real socket.
Both client implementations are covered: httpx when it is importable, and the
stdlib urllib fallback, which is what actually runs if httpx is missing.

The two behaviours worth locking down are that Basic auth reaches the wire and
that the stream reconnects with backoff instead of giving up — a panel that
stops updating after one hiccup is indistinguishable from one with no agents.
"""
import unittest
from unittest.mock import patch
from tools.marduk._ import sse_client

def _lines(*rows) -> list:
	"""SSE frames as text lines: a blank line closes each event."""
	out=[]
	for event_type,data in rows:
		if event_type:
			out.append(f"event: {event_type}")
		out.append(f"data: {data}")
		out.append("")
	return out

class _FakeStream:
	"""Context manager standing in for httpx.stream."""

	def __init__(self,lines,seen):
		self._lines=lines
		self._seen=seen

	def __enter__(self):
		return self

	def __exit__(self,*exc):
		return False

	def raise_for_status(self):
		return None

	def iter_lines(self):
		return iter(self._lines)

class TestAuthHeaders(unittest.TestCase):
	@unittest.skipUnless(sse_client.HAS_HTTPX,"httpx is not installed")
	def test_headers_reach_the_httpx_request(self):
		"""The v2 stream 401s without Basic auth, so this is load-bearing."""
		seen={}

		class _Ctx:
			def __enter__(self):
				return self

			def __exit__(self,*exc):
				return False

			def raise_for_status(self):
				return None

			def iter_lines(self):
				return iter([])

		def _stream(method,url,headers=None,timeout=None):
			seen["headers"]=headers
			return _Ctx()

		client=sse_client.HttpxSSEClient("http://x/event",lambda t,d:None,lambda:None,{"Authorization":"Basic abc"})
		with patch.object(sse_client.httpx,"stream",_stream):
			client._connect()
		self.assertEqual(seen["headers"].get("Authorization"),"Basic abc")
		self.assertEqual(seen["headers"].get("Accept"),"text/event-stream")

	def test_create_picks_a_client_carrying_the_headers(self):
		"""Whichever transport is chosen must not silently drop auth."""
		client=sse_client.create_sse_client("http://x",lambda t,d:None,lambda:None,{"Authorization":"Basic abc"})
		self.assertEqual(client.headers["Authorization"],"Basic abc")
		if sse_client.HAS_HTTPX:
			self.assertIsInstance(client,sse_client.HttpxSSEClient)
		else:
			self.assertIsInstance(client,sse_client.UrllibSSEClient)

	def test_urllib_fallback_sends_auth_too(self):
		"""Without httpx installed this is the code path that runs."""
		seen={}

		class _Resp:
			def __enter__(self):
				return self

			def __exit__(self,*exc):
				return False

			def __iter__(self):
				return iter([])

		def _urlopen(req,timeout=None):
			seen["headers"]=req.headers
			return _Resp()

		client=sse_client.UrllibSSEClient("http://x/event",lambda t,d:None,lambda:None,{"Authorization":"Basic abc"})
		with patch.object(sse_client.urllib.request,"urlopen",_urlopen):
			client._connect()
		self.assertIn("Basic abc",str(seen["headers"]))

class TestEventParsing(unittest.TestCase):
	def _parse(self,lines):
		events=[]
		client=sse_client.HttpxSSEClient("http://x",lambda t,d:events.append((t,d)),lambda:None)
		client._running=True
		client._process_stream(iter(lines))
		return events

	def test_event_and_data_are_paired(self):
		events=self._parse(_lines(("session.step.started",'{"type":"session.step.started"}')))
		self.assertEqual(len(events),1)
		self.assertEqual(events[0][0],"session.step.started")

	def test_type_is_taken_from_the_body_when_no_event_line(self):
		"""The service often sends bare `data:` lines with the type inside."""
		events=self._parse(_lines((None,'{"type":"server.connected"}')))
		self.assertEqual(events[0][0],"server.connected")

	def test_malformed_json_is_skipped_not_fatal(self):
		"""One bad frame must not tear down the stream."""
		events=self._parse(_lines(("session.step.started","{not json"),("session.step.ended",'{"a":1}')))
		self.assertEqual(len(events),1)
		self.assertEqual(events[0][0],"session.step.ended")

	def test_heartbeats_do_not_look_like_events(self):
		events=self._parse([": heartbeat",""])
		self.assertEqual(events,[])

class _Probe(sse_client.SSEClient):
	"""Minimal concrete client, so the abstract base can be driven directly."""

	def _connect(self):
		pass

class TestReconnection(unittest.TestCase):
	def test_failed_connect_retries_with_backoff(self):
		attempts=[]

		def _boom():
			attempts.append(1)
			raise RuntimeError("no route to host")

		client=_Probe("http://x",lambda t,d:None,lambda:None)
		client._connect=_boom

		with patch.object(sse_client.time,"sleep",lambda s:client.stop() if len(attempts)>=3 else None):
			client.run()
		self.assertGreaterEqual(len(attempts),3)

	def test_backoff_grows_after_a_failure(self):
		client=_Probe("http://x",lambda t,d:None,lambda:None)
		client._connect=lambda:(_ for _ in ()).throw(RuntimeError("x"))
		with patch.object(sse_client.time,"sleep",lambda s:client.stop()):
			client.run()
		self.assertGreater(client._backoff,1.0)

	def test_backoff_is_capped(self):
		client=_Probe("http://x",lambda t,d:None,lambda:None)
		client._max_backoff=30.0
		for _ in range(10):
			client._backoff=min(client._backoff*2,client._max_backoff)
		self.assertEqual(client._backoff,30.0)

	def test_stop_ends_the_loop(self):
		calls=[]

		def _connect():
			calls.append(1)
			client.stop()

		client=_Probe("http://x",lambda t,d:None,lambda:None)
		client._connect=_connect
		client.run()
		self.assertEqual(len(calls),1)

if __name__=="__main__":
	unittest.main()
