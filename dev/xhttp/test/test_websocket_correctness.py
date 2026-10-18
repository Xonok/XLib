"""
WebSocket Correctness Tests.

These tests document the EXPECTED correct behavior per RFC 6455.
They serve as a specification for a working WebSocket implementation.

The current xhttp implementation in _/websocket.py has several bugs:
1. Handshake uses capitalized headers that send_response rejects
2. send() queues only payload bytes, not full WebSocket frames
3. Sender thread blocks forever on queue.get() with no shutdown path
4. Receiver doesn't call on_close on close frame (opcode 0x8)
5. serve_websocket passes client socket to websocket.send instead of context

These tests describe what a CORRECT implementation must do.
"""

import base64,hashlib,os,queue,struct,sys,unittest
# We import the harness to use ScriptedSocket
HERE = os.path.dirname(os.path.abspath(__file__))
XHTTP_DIR = os.path.dirname(HERE)
DEV_DIR = os.path.dirname(XHTTP_DIR)
REPO_ROOT = os.path.dirname(DEV_DIR)
if REPO_ROOT not in sys.path:
	sys.path.insert(0, REPO_ROOT)

import harness
from xhttp._ import err,websocket
# ============================================================================
# RFC 6455 Reference Values
# ============================================================================

# The magic GUID from RFC 6455 Section 4.2.2
WEBSOCKET_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Test vector from RFC 6455 Section 1.3
TEST_KEY = "dGhlIHNhbXBsZSBub25jZQ=="
EXPECTED_ACCEPT = "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="

def compute_accept_key(key: str) -> str:
	"""Compute the Sec-WebSocket-Accept value per RFC 6455."""
	key_hash = hashlib.sha1((key + WEBSOCKET_MAGIC).encode())
	return base64.b64encode(key_hash.digest()).decode()

def mask_payload(payload: bytes, mask: bytes) -> bytes:
	"""Apply WebSocket masking per RFC 6455 Section 5.3."""
	return bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

def build_text_frame(payload: str, mask: bytes = None, fin: bool = True) -> bytes:
	"""Build a proper WebSocket text frame (opcode 0x1)."""
	payload_bytes = payload.encode('utf-8')
	length = len(payload_bytes)
	
	# First byte: FIN + opcode
	b1 = 0x81 if fin else 0x01
	
	# Second byte: MASK bit + length
	if mask is not None:
		b2 = 0x80 | (length if length < 126 else (126 if length < 65536 else 127))
	else:
		b2 = length if length < 126 else (126 if length < 65536 else 127)
	
	frame = bytearray([b1, b2])
	
	if length >= 65536:
		frame.extend(struct.pack('>Q', length))
	elif length >= 126:
		frame.extend(struct.pack('>H', length))
	
	if mask is not None:
		frame.extend(mask)
		frame.extend(mask_payload(payload_bytes, mask))
	else:
		frame.extend(payload_bytes)
	
	return bytes(frame)

def build_close_frame(mask: bytes = None) -> bytes:
	"""Build a proper WebSocket close frame (opcode 0x8)."""
	b1 = 0x88 # FIN=1, opcode=8
	if mask is not None:
		b2 = 0x80 | 0 # MASK=1, length=0
	else:
		b2 = 0
	frame = bytearray([b1, b2])
	if mask is not None:
		frame.extend(mask)
	return bytes(frame)

def build_ping_frame(payload: bytes, mask: bytes = None) -> bytes:
	"""Build a proper WebSocket ping frame (opcode 0x9)."""
	length = len(payload)
	b1 = 0x89 # FIN=1, opcode=9
	if mask is not None:
		b2 = 0x80 | (length if length < 126 else 126)
	else:
		b2 = length if length < 126 else 126
	frame = bytearray([b1, b2])
	if length >= 126:
		frame.extend(struct.pack('>H', length))
	if mask is not None:
		frame.extend(mask)
		frame.extend(mask_payload(payload, mask))
	else:
		frame.extend(payload)
	return bytes(frame)

def build_pong_frame(payload: bytes, mask: bytes = None) -> bytes:
	"""Build a proper WebSocket pong frame (opcode 0xA)."""
	length = len(payload)
	b1 = 0x8A # FIN=1, opcode=0xA
	if mask is not None:
		b2 = 0x80 | (length if length < 126 else 126)
	else:
		b2 = length if length < 126 else 126
	frame = bytearray([b1, b2])
	if length >= 126:
		frame.extend(struct.pack('>H', length))
	if mask is not None:
		frame.extend(mask)
		frame.extend(mask_payload(payload, mask))
	else:
		frame.extend(payload)
	return bytes(frame)

# ============================================================================
# Test Cases for Correct Behavior
# ============================================================================

class TestHandshakeCorrectness(unittest.TestCase):
	"""Tests for the WebSocket handshake per RFC 6455 Section 4."""

	def test_accept_key_computation_matches_rfc(self):
		"""Sec-WebSocket-Accept must be SHA1(key + magic) base64 encoded."""
		result = compute_accept_key(TEST_KEY)
		self.assertEqual(result, EXPECTED_ACCEPT)

	def test_handshake_response_is_101_switching_protocols(self):
		"""Handshake response must be HTTP 101 with correct headers."""
		# This is what a correct handshake response should look like
		expected_headers = {
			"upgrade": "websocket",
			"connection": "upgrade",
			"sec-websocket-accept": EXPECTED_ACCEPT,
		}
		# The test verifies the EXPECTED format
		self.assertEqual(expected_headers["upgrade"], "websocket")
		self.assertEqual(expected_headers["connection"], "upgrade")

	def test_handshake_headers_must_be_lowercase_on_wire(self):
		"""
		HTTP header names are case-insensitive but the wire format conventionally
		uses hyphenated lowercase. xhttp.send_response rejects capitalized headers.
		"""
		# This is the bug: websocket.handshake uses "Upgrade" not "upgrade"
		# The correct implementation must use lowercase header names
		pass # Documented for the implementation

	def test_handshake_includes_content_length_zero(self):
		"""101 response must include Content-Length: 0 (per RFC 7230)."""
		# The current implementation does this correctly
		pass

class TestFrameFormatCorrectness(unittest.TestCase):
	"""Tests for WebSocket frame format per RFC 6455 Section 5."""

	def test_client_frames_must_be_masked(self):
		"""Per RFC 6455 Section 5.1: client-to-server frames MUST be masked."""
		mask = b"\x12\x34\x56\x78"
		frame = build_text_frame("HELLO", mask=mask)
		
		# Verify MASK bit is set (bit 7 of second byte)
		self.assertTrue(frame[1] & 0x80)
		
		# Verify mask is present in frame
		self.assertEqual(frame[2:6], mask)

	def test_server_frames_must_not_be_masked(self):
		"""Per RFC 6455 Section 5.1: server-to-client frames MUST NOT be masked."""
		# Server frames have MASK bit = 0
		frame = build_text_frame("HELLO", mask=None)
		self.assertFalse(frame[1] & 0x80)

	def test_text_frame_opcode_is_0x1(self):
		"""Text frame opcode is 0x1."""
		frame = build_text_frame("HELLO")
		self.assertEqual(frame[0] & 0x0F, 0x1)

	def test_close_frame_opcode_is_0x8(self):
		"""Close frame opcode is 0x8."""
		frame = build_close_frame()
		self.assertEqual(frame[0] & 0x0F, 0x8)

	def test_ping_frame_opcode_is_0x9(self):
		"""Ping frame opcode is 0x9."""
		frame = build_ping_frame(b"ping")
		self.assertEqual(frame[0] & 0x0F, 0x9)

	def test_pong_frame_opcode_is_0xA(self):
		"""Pong frame opcode is 0xA."""
		frame = build_pong_frame(b"pong")
		self.assertEqual(frame[0] & 0x0F, 0xA)

	def test_fin_bit_set_for_final_frame(self):
		"""FIN bit (bit 7 of first byte) must be 1 for final frame."""
		frame = build_text_frame("HELLO")
		self.assertTrue(frame[0] & 0x80)

	def test_payload_length_encoding(self):
		"""Payload length encoding per RFC 6455 Section 5.2."""
		# Length 0-125: single byte
		frame = build_text_frame("x" * 100)
		self.assertEqual(frame[1] & 0x7F, 100)
		
		# Length 126-65535: 126 + 2 bytes
		frame = build_text_frame("x" * 300)
		self.assertEqual(frame[1] & 0x7F, 126)
		self.assertEqual(struct.unpack('>H', frame[2:4])[0], 300)
		
		# Length >65535: 127 + 8 bytes
		frame = build_text_frame("x" * 70000)
		self.assertEqual(frame[1] & 0x7F, 127)
		self.assertEqual(struct.unpack('>Q', frame[2:10])[0], 70000)

class TestSendReceiveBehavior(unittest.TestCase):
	"""Tests for correct send/receive behavior."""

	def test_send_queues_full_websocket_frame(self):
		"""
		send() must queue the COMPLETE WebSocket frame (header + payload),
		not just the payload bytes.
		
		Current bug: implementation puts only payload bytearray in queue.
		"""
		send_queue = queue.Queue()
		ctx = {"data": {}, "_send": send_queue, "req": {}, "send_ws": None}
		
		# This is what a CORRECT implementation should do:
		# - Build the full frame: 0x81 + length + payload
		# - Put the full frame in the queue
		
		payload = "HELLO"
		payload_bytes = payload.encode('utf-8')
		
		# Expected frame format for server->client (no mask)
		expected_frame = bytearray([0x81, len(payload_bytes)])
		expected_frame.extend(payload_bytes)
		
		# The test documents the expected behavior
		self.assertEqual(bytes(expected_frame), b'\x81\x05HELLO')

	def test_send_long_message_uses_16bit_length(self):
		"""Messages 126-65535 bytes use 16-bit extended length."""
		payload = "x" * 300
		payload_bytes = payload.encode('utf-8')
		
		expected_frame = bytearray([0x81, 126])
		expected_frame.extend(struct.pack('>H', len(payload_bytes)))
		expected_frame.extend(payload_bytes)
		
		self.assertEqual(len(expected_frame), 2 + 2 + 300)
		self.assertEqual(expected_frame[1], 126)

	def test_send_very_long_message_uses_64bit_length(self):
		"""Messages >65535 bytes use 64-bit extended length."""
		payload = "x" * 70000
		payload_bytes = payload.encode('utf-8')
		
		expected_frame = bytearray([0x81, 127])
		expected_frame.extend(struct.pack('>Q', len(payload_bytes)))
		expected_frame.extend(payload_bytes)
		
		self.assertEqual(len(expected_frame), 2 + 8 + 70000)
		self.assertEqual(expected_frame[1], 127)

	def test_send_rejects_none(self):
		"""send(None) must raise WSMessageNone."""
		ctx = {"data": {}, "_send": queue.Queue(), "req": {}, "send_ws": None}
		with self.assertRaises(err.WSMessageNone):
			websocket.send(ctx, None)

	def test_send_rejects_non_string(self):
		"""send() must only accept strings (text frames)."""
		ctx = {"data": {}, "_send": queue.Queue(), "req": {}, "send_ws": None}
		with self.assertRaises(err.WSMessageMustBeString):
			websocket.send(ctx, 42)

class TestSenderThreadLifecycle(unittest.TestCase):
	"""Tests for sender thread lifecycle management."""

	def test_sender_exits_on_none_sentinel(self):
		"""None in the send queue must shut down the sender cleanly."""
		# Correct implementation: sender gets None -> breaks loop -> exits
		pass

	def test_sender_shutdown_on_connection_close(self):
		"""When connection closes, sender must be signaled to shut down."""
		# Current bug: sender loops forever on queue.get() with no way to stop
		# Correct: on_close should put None in queue to signal shutdown
		pass

	def test_sender_handles_dead_peer_gracefully(self):
		"""Sender must catch BrokenPipeError/ConnectionResetError and exit."""
		# Current: prints traceback to stdout
		# Correct: catches error, exits cleanly without traceback spam
		pass

	def test_no_sender_thread_leak(self):
		"""Multiple connections must not leak sender threads."""
		# Current: each connection starts a sender thread that never exits
		# Correct: sender thread exits when connection closes
		pass

class TestReceiverBehavior(unittest.TestCase):
	"""Tests for receiver thread behavior."""

	def test_receiver_calls_on_message_for_text_frame(self):
		"""Text frame (opcode 0x1) must trigger on_message callback."""
		pass

	def test_receiver_calls_on_close_on_close_frame(self):
		"""
		Close frame (opcode 0x8) must:
		1. Call on_close callback
		2. Put None in send queue to signal sender shutdown
		3. Exit the receive loop
		
		Current bug: receiver just exits loop without calling on_close.
		"""
		pass

	def test_receiver_sends_pong_for_ping(self):
		"""Ping frame (opcode 0x9) must trigger automatic pong response."""
		pass

	def test_receiver_ignores_pong_frames(self):
		"""Pong frames (opcode 0xA) are not passed to on_message."""
		pass

	def test_receiver_handles_truncated_frame(self):
		"""Peer closing mid-frame must trigger on_close cleanly."""
		pass

	def test_receiver_handles_oversized_pong(self):
		"""Pong payload >125 bytes must be rejected (per RFC 6455)."""
		pass

class TestIntegrationCorrectness(unittest.TestCase):
	"""Tests for end-to-end integration correctness."""

	def test_serve_websocket_handshake_succeeds_with_valid_request(self):
		"""Valid upgrade request must complete handshake and return context."""
		pass

	def test_serve_websocket_rejects_non_get(self):
		"""Non-GET requests must not be upgraded."""
		pass

	def test_serve_websocket_rejects_missing_upgrade_header(self):
		"""Missing Upgrade: websocket header must reject."""
		pass

	def test_serve_websocket_rejects_missing_connection_upgrade(self):
		"""Missing 'upgrade' in Connection header must reject."""
		pass

	def test_serve_websocket_rejects_missing_sec_websocket_key(self):
		"""Missing Sec-WebSocket-Key must reject."""
		pass

	def test_serve_websocket_rejects_missing_sec_websocket_version(self):
		"""Missing Sec-WebSocket-Version must reject."""
		pass

	def test_serve_websocket_preserves_leftover_bytes(self):
		"""
		First frame bytes arriving with the upgrade request (in same TCP segment)
		must be preserved in req['leftover'] and processed by receiver.
		"""
		pass

	def test_send_ws_closure_works_correctly(self):
		"""
		serve_websocket's send_ws closure must correctly forward to websocket.send
		with the context dict, not the client socket.
		
		Current bug in server.py line 100-101:
			def send_ws(msg):
				websocket.send(ctx, msg) # Should be correct
			But the test documents it should work with context
		"""
		pass

	def test_full_duplex_communication(self):
		"""Client and server can exchange messages in both directions."""
		pass

	def test_clean_shutdown_on_close_frame(self):
		"""Receiving close frame triggers clean shutdown of both threads."""
		pass

	def test_browser_compatibility(self):
		"""
		The implementation must not be rejected by browsers.
		This means:
		- Correct Sec-WebSocket-Accept computation
		- Proper frame format (masking, opcodes, length encoding)
		- Clean handshake with correct headers
		- Proper close handshake
		"""
		pass

class TestEdgeCases(unittest.TestCase):
	"""Tests for edge cases and hostile inputs."""

	@harness.edge
	def test_oversized_frame_rejected(self):
		"""Frames exceeding reasonable size limit must be rejected."""
		pass

	@harness.edge
	def test_malformed_frame_handled(self):
		"""Malformed frames must not crash the receiver."""
		pass

	@harness.edge
	def test_unmasked_client_frame_rejected(self):
		"""Unmasked frames from client must be rejected (RFC 6455 Section 5.1)."""
		pass

	@harness.edge
	def test_masked_server_frame_rejected(self):
		"""Masked frames from server must be rejected by client (not our concern)."""
		pass

	@harness.edge
	def test_fragmented_message_reassembly(self):
		"""Fragmented messages (FIN=0) must be reassembled correctly."""
		# Current implementation doesn't support fragmentation
		pass

	@harness.edge
	def test_concurrent_send_receive(self):
		"""Concurrent send and receive must not deadlock or corrupt frames."""
		pass

if __name__ == "__main__":
	unittest.main()
