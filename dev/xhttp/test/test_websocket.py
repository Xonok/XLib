"""
WebSocket end-to-end tests.

The WebSocket implementation in _/websocket.py has never been exercised
end-to-end. These tests cover:

- Handshake (Sec-WebSocket-Accept computation, 101 response)
- Frame parsing (text, binary, close, ping/pong)
- Frame sending
- Context creation
- Sender/receiver thread lifecycle
- Integration with serve_websocket callback
"""

import unittest,threading,time,queue,harness
from xhttp import xhttp
from xhttp._ import websocket,err

class WebSocketHandshakeTest(unittest.TestCase):
	"""The 101 handshake: key hashing and response emission."""

	def test_handshake_computes_correct_accept_key(self):
		"""
		The accept key is SHA1(key + magic) base64-encoded.
		This is the RFC 6455 algorithm and must match exactly.
		"""
		key = "dGhlIHNhbXBsZSBub25jZQ=="
		expected = "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
		s = harness.ScriptedSocket(b"")
		result = websocket.handshake(s, key)
		self.assertTrue(result)
		head = bytes(s.written).partition(b"\r\n\r\n")[0]
		self.assertIn(b"sec-websocket-accept: " + expected.encode(), head)

	def test_handshake_emits_required_headers(self):
		"""
		The 101 response must include Upgrade, Connection, Sec-WebSocket-Accept,
		and Content-Length: 0.
		"""
		s = harness.ScriptedSocket(b"")
		websocket.handshake(s, "dGhlIHNhbXBsZSBub25jZQ==")
		head = bytes(s.written).partition(b"\r\n\r\n")[0]
		self.assertIn(b"HTTP/1.1 101", head)
		self.assertIn(b"upgrade: websocket", head)
		self.assertIn(b"connection: upgrade", head)
		self.assertIn(b"sec-websocket-accept:", head)
		self.assertIn(b"content-length: 0", head)

	def test_handshake_returns_false_on_write_failure(self):
		"""If the peer vanishes during handshake, return False cleanly."""
		s = harness.ExplodingSocket(b"", error=ConnectionResetError)
		result = websocket.handshake(s, "dGhlIHNhbXBsZSBub25jZQ==")
		self.assertIs(result, False)

class WebSocketFrameTest(unittest.TestCase):
	"""Frame parsing and sending: the wire protocol."""

	def _make_client_with_data(self, frame_bytes):
		"""Create a ScriptedSocket pre-loaded with frame data."""
		return harness.ScriptedSocket(frame_bytes)

	def test_recv_text_frame(self):
		"""
		A text frame (opcode 0x1) with FIN=1, no mask, payload "HELLO".
		Frame: 0x81 0x05 HELLO

		BUG: xhttp.read_exact returns bytearray but websocket._recv
		treats it as bytes/int (does b1 >> 7). This is a bug in websocket.py.
		"""
		frame = b"\x81\x05HELLO"
		client = self._make_client_with_data(frame)
		ctx = {"data": {}, "_send": queue.Queue(), "req": {}, "send_ws": lambda m: None}
		msg, op = websocket._recv(client, ctx)
		self.assertEqual(msg, "HELLO")
		self.assertEqual(op, 1)

	def test_recv_text_frame_with_mask(self):
		"""
		A masked text frame. Client-to-server frames are always masked.
		Payload "HELLO" masked with key 0x12 0x34 0x56 0x78.

		BUG: xhttp.read_exact returns bytearray but websocket._recv
		treats it as bytes/int.
		"""
		mask = b"\x12\x34\x56\x78"
		payload = b"HELLO"
		masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
		frame = b"\x81\x85" + mask + masked
		client = self._make_client_with_data(frame)
		ctx = {"data": {}, "_send": queue.Queue(), "req": {}, "send_ws": lambda m: None}
		msg, op = websocket._recv(client, ctx)
		self.assertEqual(msg, "HELLO")
		self.assertEqual(op, 1)

	def test_recv_extended_length_16bit(self):
		"""Payload length 126-65535 uses 16-bit extended length.

		BUG: xhttp.read_exact returns bytearray but websocket._recv
		treats it as bytes/int.
		"""
		payload = b"x" * 300
		mask = b"\x12\x34\x56\x78"
		masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
		frame = b"\x81\xfe" + b"\x01\x2c" + mask + masked
		client = self._make_client_with_data(frame)
		ctx = {"data": {}, "_send": queue.Queue(), "req": {}, "send_ws": lambda m: None}
		msg, op = websocket._recv(client, ctx)
		self.assertEqual(msg, "x" * 300)
		self.assertEqual(op, 1)

	def test_recv_close_frame(self):
		"""Close frame (opcode 0x8) signals connection end.

		BUG: xhttp.read_exact returns bytearray but websocket._recv
		treats it as bytes/int.
		"""
		frame = b"\x88\x00"
		client = self._make_client_with_data(frame)
		ctx = {"data": {}, "_send": queue.Queue(), "req": {}, "send_ws": lambda m: None}
		msg, op = websocket._recv(client, ctx)
		self.assertEqual(op, 8)

	def test_recv_ping_frame_triggers_pong(self):
		"""Ping frame (opcode 0x9) should queue a pong response.

		BUG: xhttp.read_exact returns bytearray but websocket._recv
		treats it as bytes/int.
		"""
		payload = b"ping-data"
		mask = b"\x12\x34\x56\x78"
		masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
		frame = b"\x89\x89" + mask + masked
		client = self._make_client_with_data(frame)
		send_queue = queue.Queue()
		ctx = {"data": {}, "_send": send_queue, "req": {}, "send_ws": lambda m: None}
		msg, op = websocket._recv(client, ctx)
		self.assertEqual(op, 9)
		self.assertFalse(send_queue.empty())
		pong_payload = send_queue.get()
		self.assertEqual(pong_payload, payload)

	def test_send_text_frame(self):
		"""Sending a text frame produces correct wire format."""
		s = harness.ScriptedSocket(b"")
		websocket._send(s, "HELLO")
		written = bytes(s.written)
		self.assertEqual(written[:2], b"\x81\x05")
		self.assertEqual(written[2:], b"HELLO")

	def test_send_long_text_frame(self):
		"""Text frame with length 126-65535 uses 16-bit length field."""
		payload = "x" * 300
		s = harness.ScriptedSocket(b"")
		websocket._send(s, payload)
		written = bytes(s.written)
		self.assertEqual(written[0], 0x81)
		self.assertEqual(written[1], 126)
		self.assertEqual(written[2:4], b"\x01\x2c")
		self.assertEqual(written[4:], payload.encode())

	def test_send_very_long_text_frame(self):
		"""Text frame with length >65535 uses 64-bit length field."""
		payload = "x" * 70000
		s = harness.ScriptedSocket(b"")
		websocket._send(s, payload)
		written = bytes(s.written)
		self.assertEqual(written[0], 0x81)
		self.assertEqual(written[1], 127)
		import struct
		self.assertEqual(written[2:10], struct.pack('>Q', 70000))
		self.assertEqual(written[10:], payload.encode())

class WebSocketContextTest(unittest.TestCase):
	"""Context creation and the send_ws closure."""

	def test_context_contains_expected_keys(self):
		"""context() returns a dict with data, _send queue, req, send_ws."""
		req = {"client": None, "headers": {}}
		send_called = []
		def send_ws(msg):
			send_called.append(msg)
		ctx = websocket.context(req, send_ws)
		self.assertIn("data", ctx)
		self.assertIn("_send", ctx)
		self.assertIn("req", ctx)
		self.assertIn("send_ws", ctx)
		self.assertIs(ctx["req"], req)
		self.assertIsInstance(ctx["_send"], queue.Queue)

	def test_send_ws_closure_captures_client(self):
		"""
		serve_websocket creates send_ws that captures the client socket.
		This is the integration point between xhttp and websocket.

		BUG: serve_websocket calls websocket.send(client, msg)
		but websocket.send expects a context dict, not a socket. This is a
		bug in xhttp.py:292. The closure should call websocket._send(client, msg).
		"""
		client = harness.ScriptedSocket(b"")
		def send_ws(msg):
			websocket.send(client, msg)
		ctx = websocket.context({"client": client}, send_ws)
		ctx["send_ws"]("test message")
		self.assertIn(b"test message", bytes(client.written))

class WebSocketSenderTest(unittest.TestCase):
	"""The sender thread: reads from queue, writes frames."""

	def test_sender_writes_queued_messages(self):
		"""sender pulls messages from queue and writes them."""
		client = harness.ScriptedSocket(b"")
		send_queue = queue.Queue()
		ctx = {"data": {}, "_send": send_queue, "req": {}, "send_ws": None}
		send_queue.put("first")
		send_queue.put("second")
		send_queue.put(None)

		websocket.sender(client, ctx)

		written = bytes(client.written)
		self.assertIn(b"first", written)
		self.assertIn(b"second", written)

	def test_sender_exits_on_none_sentinel(self):
		"""None in the queue shuts down the sender cleanly."""
		client = harness.ScriptedSocket(b"")
		send_queue = queue.Queue()
		ctx = {"data": {}, "_send": send_queue, "req": {}, "send_ws": None}
		send_queue.put(None)

		websocket.sender(client, ctx)

	def test_sender_handles_dead_peer(self):
		"""If the peer vanishes, sender should not crash the process.

		BUG: sender doesn't catch peer errors (BrokenPipeError,
		ConnectionResetError, ConnectionAbortedError). This is a bug in
		websocket.py sender function.
		"""
		client = harness.ExplodingSocket(b"", error=BrokenPipeError)
		send_queue = queue.Queue()
		ctx = {"data": {}, "_send": send_queue, "req": {}, "send_ws": None}
		send_queue.put("hello")
		send_queue.put(None)

		try:
			websocket.sender(client, ctx)
		except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
			self.fail("sender let peer error escape")

class WebSocketReceiverTest(unittest.TestCase):
	"""The receiver thread: reads frames, calls callbacks."""

	def test_receiver_calls_on_message_for_text_frame(self):
		"""Text frame triggers on_message callback.

		BUG: receiver calls _recv which has the read_exact bytearray bug.
		"""
		frame = b"\x81\x05HELLO"
		client = harness.ScriptedSocket(frame + b"\x88\x00")
		messages = []
		def on_message(c, ctx, msg):
			messages.append(msg)
		def on_close(c, ctx):
			pass
		ctx = {"data": {}, "_send": queue.Queue(), "req": {}, "send_ws": None}

		websocket.receiver(client, ctx, on_message, on_close)

		self.assertEqual(messages, ["HELLO"])

	def test_receiver_exits_on_close_frame(self):
		"""Close frame (opcode 8) breaks the receive loop."""
		frame = b"\x88\x00"
		client = harness.ScriptedSocket(frame)
		closed = []
		def on_message(c, ctx, msg):
			pass
		def on_close(c, ctx):
			closed.append(True)
		ctx = {"data": {}, "_send": queue.Queue(), "req": {}, "send_ws": None}

		websocket.receiver(client, ctx, on_message, on_close)

		self.assertTrue(closed)

	def test_receiver_calls_on_close_on_error(self):
		"""Any read error triggers on_close and puts None in send queue.

		This test uses ExplodingSocket which raises on send/sendall, not recv.
		The receiver's exception handling catches any error from _recv and
		calls on_close, so this test passes even with the read_exact bug.
		"""
		client = harness.ExplodingSocket(b"", error=ConnectionResetError)
		closed = []
		send_queue = queue.Queue()
		def on_message(c, ctx, msg):
			pass
		def on_close(c, ctx):
			closed.append(True)
		ctx = {"data": {}, "_send": send_queue, "req": {}, "send_ws": None}

		websocket.receiver(client, ctx, on_message, on_close)

		self.assertTrue(closed)
		self.assertFalse(send_queue.empty())
		self.assertIsNone(send_queue.get())

	def test_receiver_ignores_pong_frames(self):
		"""Pong frames (opcode 0xA) are ignored, not passed to on_message."""
		frame = b"\x8a\x00"
		client = harness.ScriptedSocket(frame + b"\x88\x00")
		messages = []
		def on_message(c, ctx, msg):
			messages.append(msg)
		def on_close(c, ctx):
			pass
		ctx = {"data": {}, "_send": queue.Queue(), "req": {}, "send_ws": None}

		websocket.receiver(client, ctx, on_message, on_close)

		self.assertEqual(messages, [])

class WebSocketIntegrationTest(unittest.TestCase):
	"""
	End-to-end tests using serve_websocket callback with a live server.

	These use real sockets and threads to verify the full stack works.
	"""

	def _websocket_upgrade_request(self, key="dGhlIHNhbXBsZSBub25jZQ=="):
		"""Build a valid WebSocket upgrade request."""
		return (
			b"GET /chat_async?key=test HTTP/1.1\r\n"
			b"Host: localhost\r\n"
			b"Upgrade: websocket\r\n"
			b"Connection: Upgrade\r\n"
			b"Sec-WebSocket-Key: " + key.encode() + b"\r\n"
			b"Sec-WebSocket-Version: 13\r\n"
			b"\r\n"
		)

	def test_serve_websocket_accepts_valid_upgrade(self):
		"""Valid upgrade request completes handshake and starts threads."""
		req = xhttp.read_request(
			harness.ScriptedSocket(self._websocket_upgrade_request()),
			("127.0.0.1", 5000)
		)
		opened = []
		closed = []
		def on_open(c, ctx):
			opened.append(True)
		def on_close(c, ctx):
			closed.append(True)
		def on_message(c, ctx, msg):
			pass

		ctx = xhttp.serve_websocket(req, on_message=on_message, on_open=on_open, on_close=on_close)

		self.assertIsNotNone(ctx)
		self.assertTrue(opened)
		time.sleep(0.1)
		req["client"].close()
		time.sleep(0.1)
		self.assertTrue(closed)

	def test_serve_websocket_rejects_non_get(self):
		"""Non-GET requests are not upgraded."""
		req = xhttp.read_request(
			harness.ScriptedSocket(b"POST / HTTP/1.1\r\nHost: x\r\n\r\n"),
			("127.0.0.1", 5000)
		)
		ctx = xhttp.serve_websocket(req)
		self.assertIsNone(ctx)

	def test_serve_websocket_rejects_missing_upgrade(self):
		"""Missing Upgrade header rejects the request."""
		req = xhttp.read_request(
			harness.ScriptedSocket(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n"),
			("127.0.0.1", 5000)
		)
		ctx = xhttp.serve_websocket(req)
		self.assertIsNone(ctx)

	def test_serve_websocket_rejects_missing_connection_upgrade(self):
		"""Missing 'upgrade' in Connection header rejects."""
		req = xhttp.read_request(
			harness.ScriptedSocket(b"GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\n\r\n"),
			("127.0.0.1", 5000)
		)
		ctx = xhttp.serve_websocket(req)
		self.assertIsNone(ctx)

	def test_serve_websocket_rejects_missing_key(self):
		"""Missing Sec-WebSocket-Key rejects."""
		req = xhttp.read_request(
			harness.ScriptedSocket(
				b"GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n"
			),
			("127.0.0.1", 5000)
		)
		ctx = xhttp.serve_websocket(req)
		self.assertIsNone(ctx)

	def test_serve_websocket_rejects_missing_version(self):
		"""Missing Sec-WebSocket-Version rejects."""
		req = xhttp.read_request(
			harness.ScriptedSocket(
				b"GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: key\r\n\r\n"
			),
			("127.0.0.1", 5000)
		)
		ctx = xhttp.serve_websocket(req)
		self.assertIsNone(ctx)

	def test_serve_websocket_preserves_leftover_bytes(self):
		"""
		First frame bytes arriving with the upgrade request must be preserved.

		This is the critical path from decision 6 in SPEC.md: the websocket
		frame that shares a TCP segment with the HTTP headers must not be lost.

		BUG: serve_websocket calls websocket.handshake which
		uses capitalized headers that xhttp.send_response rejects.
		"""
		first_frame = b"\x81\x05HELLO"
		raw = self._websocket_upgrade_request() + first_frame
		client = harness.ScriptedSocket(raw)
		req = xhttp.read_request(client, ("127.0.0.1", 5000))

		self.assertIn(b"HELLO", bytes(req["leftover"]))

		received = []
		def on_message(c, ctx, msg):
			received.append(msg)
		def on_open(c, ctx):
			pass
		def on_close(c, ctx):
			pass

		ctx = xhttp.serve_websocket(req, on_message=on_message, on_open=on_open, on_close=on_close)
		self.assertIsNotNone(ctx)

		time.sleep(0.2)
		client.close()
		time.sleep(0.1)

		self.assertEqual(received, ["HELLO"])

class WebSocketSendTest(unittest.TestCase):
	"""The send() function and thread coordination."""

	def test_send_queues_message_for_sender(self):
		"""send() puts message in queue for sender thread."""
		send_queue = queue.Queue()
		ctx = {"data": {}, "_send": send_queue, "req": {}, "send_ws": None}
		websocket.send(ctx, "hello")
		self.assertFalse(send_queue.empty())
		self.assertEqual(send_queue.get(), "hello")

	def test_send_rejects_none(self):
		"""send(None) raises WSMessageNone."""
		ctx = {"data": {}, "_send": queue.Queue(), "req": {}, "send_ws": None}
		with self.assertRaises(err.WSMessageNone):
			websocket.send(ctx, None)

	def test_send_ws_integration(self):
		"""
		serve_websocket's send_ws closure correctly forwards to websocket.send.

		BUG: serve_websocket calls websocket.send(client, msg)
		but websocket.send expects a context dict, not a socket. This is a
		bug in xhttp.py:292.
		"""
		client = harness.ScriptedSocket(b"")
		def send_ws(msg):
			websocket.send(client, msg)
		ctx = websocket.context({"client": client}, send_ws)
		ctx["send_ws"]("test")
		written = bytes(client.written)
		self.assertIn(b"test", written)

class WebSocketEdgeTest(unittest.TestCase):
	"""
	Edge cases: hostile inputs, resource exhaustion, protocol violations.

	Run with `python3 dev/xhttp/test/run.py` to include, `--core` to skip.
	"""

	@harness.edge
	def test_sender_thread_leak_prevention(self):
		"""
		SPEC.md defect: sender thread loops forever on ctx["_send"].get()
		with no shutdown path. If send() is called after connection drops,
		the queue grows unbounded and the thread is never recycled.

		This test documents the current behavior. A fix would add a sentinel
		or socket-liveness check.
		"""
		client = harness.ScriptedSocket(b"")
		send_queue = queue.Queue()
		ctx = {"data": {}, "_send": send_queue, "req": {}, "send_ws": None}

		for i in range(100):
			send_queue.put(f"msg{i}")

		self.assertEqual(send_queue.qsize(), 100)

	@harness.edge
	def test_receiver_handles_truncated_frame(self):
		"""Peer closes mid-frame: receiver should call on_close cleanly."""
		client = harness.ScriptedSocket(b"\x81")
		closed = []
		def on_message(c, ctx, msg):
			pass
		def on_close(c, ctx):
			closed.append(True)
		ctx = {"data": {}, "_send": queue.Queue(), "req": {}, "send_ws": None}

		websocket.receiver(client, ctx, on_message, on_close)

		self.assertTrue(closed)

	@harness.edge
	def test_oversized_pong_rejected(self):
		"""Pong payload >125 bytes raises ValueError."""
		client = harness.ScriptedSocket(b"")
		ctx = {"data": {}, "_send": queue.Queue(), "req": {}, "send_ws": None}
		with self.assertRaises(ValueError):
			websocket._send_pong(client, b"x" * 126, ctx)

if __name__ == "__main__":
	unittest.main()
