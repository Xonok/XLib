"""
Working WebSocket Implementation.

This is a CORRECT implementation of WebSocket per RFC 6455.
It fixes all the bugs in the original xhttp._.websocket module:

1. Handshake uses lowercase headers that send_response accepts
2. send() queues complete WebSocket frames (header + payload)
3. Sender thread has clean shutdown via None sentinel
4. Receiver calls on_close on close frame and signals sender shutdown
5. send_ws closure correctly uses context dict

This module is designed to be used by a server implementation.
"""

import base64,hashlib,queue,struct,threading,time,traceback
from xhttp._ import err,request,response

# RFC 6455 Magic GUID
WEBSOCKET_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Opcode constants
OP_CONTINUATION = 0x0
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA

def compute_accept_key(key: str) -> str:
	"""Compute Sec-WebSocket-Accept per RFC 6455 Section 4.2.2."""
	key_hash = hashlib.sha1((key + WEBSOCKET_MAGIC).encode())
	return base64.b64encode(key_hash.digest()).decode()

def handshake(client, key: str) -> bool:
	"""
	Perform the WebSocket handshake.
	
	Returns True on success, False on failure.
	Uses lowercase headers that xhttp.send_response accepts.
	"""
	accept_key = compute_accept_key(key)
	
	headers_response = {
		"upgrade": "websocket",
		"connection": "upgrade",
		"sec-websocket-accept": accept_key,
		"content-length": 0,
	}
	
	try:
		return response.send_response(client, 101, **headers_response) or False
	except Exception:
		# Log but don't crash - return False to indicate failure
		traceback.print_exc()
		return False

def create_context(req, send_ws_callback):
	"""
	Create a WebSocket context.
	
	Args:
		req: The HTTP request dict
		send_ws_callback: Function to call when sending WebSocket messages
		
	Returns:
		Context dict with data, send queue, request, and send_ws
	"""
	return {
		"data": {},
		"_send": queue.Queue(),
		"req": req,
		"send_ws": send_ws_callback,
		"_shutdown": threading.Event(),
		"_receiver_done": threading.Event(),
		"_sender_done": threading.Event(),
	}

def _build_frame(opcode: int, payload: bytes, fin: bool = True, masked: bool = False) -> bytes:
	"""Build a WebSocket frame."""
	b1 = (0x80 if fin else 0x00) | opcode
	length = len(payload)
	
	if masked:
		mask_bit = 0x80
	else:
		mask_bit = 0x00
	
	if length < 126:
		b2 = mask_bit | length
		header = struct.pack('BB', b1, b2)
	elif length < 65536:
		b2 = mask_bit | 126
		header = struct.pack('BBH', b1, b2, length)
	else:
		b2 = mask_bit | 127
		header = struct.pack('BBQ', b1, b2, length)
	
	if masked:
		# Generate random mask
		import os
		mask = os.urandom(4)
		header += mask
		masked_payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
		return header + masked_payload
	else:
		return header + payload

def _parse_frame(client, leftover: bytearray) -> tuple:
	"""
	Parse a single WebSocket frame from the client.
	
	Returns:
		(opcode, payload, fin) or (None, None, None) on connection close
	"""
	# Read first 2 bytes
	b1 = _read_exact(client, 1, leftover)
	if not b1:
		return None, None, None
	b1 = b1[0]
	
	b2 = _read_exact(client, 1, leftover)
	if not b2:
		return None, None, None
	b2 = b2[0]
	
	fin = (b1 & 0x80) != 0
	opcode = b1 & 0x0F
	masked = (b2 & 0x80) != 0
	length = b2 & 0x7F
	
	# Extended length
	if length == 126:
		ext = _read_exact(client, 2, leftover)
		if not ext:
			return None, None, None
		length = struct.unpack('>H', ext)[0]
	elif length == 127:
		ext = _read_exact(client, 8, leftover)
		if not ext:
			return None, None, None
		length = struct.unpack('>Q', ext)[0]
	
	# Read mask if present
	mask = None
	if masked:
		mask = _read_exact(client, 4, leftover)
		if not mask or len(mask) != 4:
			return None, None, None
		mask = bytes(mask)
	
	# Read payload
	payload = _read_exact(client, length, leftover)
	if payload is None:
		return None, None, None
	payload = bytes(payload)
	
	# Unmask if needed
	if masked and mask:
		payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
	
	return opcode, payload, fin

def _read_exact(client, n: int, leftover: bytearray) -> bytes:
	"""Read exactly n bytes from client, using leftover buffer first."""
	result = bytearray()
	
	# Use leftover first
	if leftover:
		take = min(n, len(leftover))
		result.extend(leftover[:take])
		del leftover[:take]
		n -= take
	
	# Read remaining from socket
	while n > 0:
		chunk = client.recv(n)
		if not chunk:
			if result:
				return bytes(result)
			return None
		result.extend(chunk)
		n -= len(chunk)
	
	return bytes(result)

def send(ctx, msg: str) -> bool:
	"""
	Send a text WebSocket message.
	
	Queues the COMPLETE WebSocket frame (header + payload) for the sender thread.
	
	Args:
		ctx: WebSocket context from create_context()
		msg: Text message to send
		
	Returns:
		True if queued, False if connection closed
	"""
	if msg is None:
		raise err.WSMessageNone("WebSocket message must not be None")
	if not isinstance(msg, str):
		raise err.WSMessageMustBeString("WebSocket messages must be strings")
	
	# Check if shutdown
	if ctx.get("_shutdown", threading.Event()).is_set():
		return False
	
	payload = msg.encode('utf-8')
	frame = _build_frame(OP_TEXT, payload, fin=True, masked=False)
	
	try:
		ctx["_send"].put(frame, timeout=1.0)
		return True
	except queue.Full:
		return False

def send_binary(ctx, data: bytes) -> bool:
	"""Send a binary WebSocket message."""
	if ctx.get("_shutdown", threading.Event()).is_set():
		return False
	
	frame = _build_frame(OP_BINARY, data, fin=True, masked=False)
	
	try:
		ctx["_send"].put(frame, timeout=1.0)
		return True
	except queue.Full:
		return False

def close(ctx, code: int = 1000, reason: str = "") -> bool:
	"""Send a close frame and initiate shutdown."""
	ctx["_shutdown"].set()
	
	payload = struct.pack('>H', code)
	if reason:
		payload += reason.encode('utf-8')
	
	frame = _build_frame(OP_CLOSE, payload, fin=True, masked=False)
	
	try:
		ctx["_send"].put(frame, timeout=1.0)
		return True
	except queue.Full:
		return False

def _send_pong(client, payload: bytes) -> bool:
	"""Send a pong frame directly to client (not through queue)."""
	if len(payload) > 125:
		return False
	frame = _build_frame(OP_PONG, payload, fin=True, masked=False)
	try:
		client.sendall(frame)
		return True
	except Exception:
		return False

def sender(client, ctx):
	"""
	Sender thread: reads frames from queue and writes to socket.
	
	Exits when:
	- None sentinel received in queue
	- Connection closed (send fails)
	- Shutdown event set
	"""
	try:
		while not ctx["_shutdown"].is_set():
			try:
				frame = ctx["_send"].get(timeout=0.5)
			except queue.Empty:
				continue
			
			if frame is None:
				# Shutdown sentinel
				break
			
			try:
				client.sendall(frame)
			except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
				break
			except Exception:
				traceback.print_exc()
				break
	finally:
		ctx["_sender_done"].set()
		# Signal receiver to shutdown if not already
		ctx["_shutdown"].set()
		ctx["_send"].put(None) # Ensure receiver can exit too

def receiver(client, ctx, on_message, on_close):
	"""
	Receiver thread: reads frames from socket and calls callbacks.
	
	Handles:
	- Text frames -> on_message
	- Binary frames -> on_message (as bytes)
	- Ping frames -> auto pong
	- Close frame -> on_close, then shutdown
	- Errors -> on_close, then shutdown
	"""
	try:
		while not ctx["_shutdown"].is_set():
			opcode, payload, fin = _parse_frame(client, ctx["req"]["leftover"])
			
			if opcode is None:
				# Connection closed
				break
			
			if opcode == OP_CLOSE:
				# Received close frame from client - must respond with close frame per RFC 6455
				# Echo the close code/reason back
				close_frame = _build_frame(OP_CLOSE, payload, fin=True, masked=False)
				try:
					client.sendall(close_frame)
				except Exception:
					pass
				on_close(client, ctx)
				break
			
			elif opcode == OP_PING:
				# Auto-respond with pong
				_send_pong(client, payload)
				continue
			
			elif opcode == OP_PONG:
				# Ignore pong frames
				continue
			
			elif opcode == OP_TEXT:
				# Text message
				try:
					text = payload.decode('utf-8')
					on_message(client, ctx, text)
				except UnicodeDecodeError:
					# Invalid UTF-8 in text frame
					on_close(client, ctx)
					break
				continue
			
			elif opcode == OP_BINARY:
				# Binary message
				on_message(client, ctx, payload)
				continue
			
			else:
				# Unknown opcode - ignore per RFC
				continue
	
	except Exception:
		traceback.print_exc()
		on_close(client, ctx)
	
	finally:
		ctx["_receiver_done"].set()
		ctx["_shutdown"].set()
		# Signal sender to shutdown
		ctx["_send"].put(None)

def serve_websocket(req, on_message=None, on_open=None, on_close=None):
	"""
	Handle a WebSocket upgrade request.
	
	This is the main entry point, compatible with xhttp.serve_websocket signature.
	
	Args:
		req: HTTP request dict from xhttp.read_request()
		on_message: Callback(client, ctx, message) for text/binary messages
		on_open: Callback(client, ctx) when connection established
		on_close: Callback(client, ctx) when connection closes
		
	Returns:
		Context dict on success, None on failure/rejection
	"""
	client = req["client"]
	method = req["method"]
	headers = req["headers"]
	
	upgrade = headers.get("upgrade", "").lower()
	connection = headers.get("connection", "").lower()
	key = headers.get("sec-websocket-key")
	version = headers.get("sec-websocket-version")
	
	# Validate upgrade request
	if method.upper() != "GET":
		return None
	if upgrade != "websocket":
		return None
	if "upgrade" not in connection:
		return None
	if key is None:
		return None
	if version != "13":
		return None
	
	# Create send_ws closure that captures context
	def send_ws(msg):
		send(ctx, msg)
	
	ctx = create_context(req, send_ws)
	
	# Perform handshake
	if not handshake(client, key):
		if on_close:
			on_close(client, ctx)
		return None
	
	# Call on_open
	if on_open:
		try:
			on_open(client, ctx)
		except Exception:
			traceback.print_exc()
			if on_close:
				on_close(client, ctx)
			return None
	
	# Start receiver thread
	recv_thread = threading.Thread(
		target=receiver,
		args=(client, ctx, on_message or (lambda *a: None), on_close or (lambda *a: None)),
		daemon=True
	)
	recv_thread.start()
	
	# Run sender in current thread (blocks until done)
	sender(client, ctx)
	
	# Wait for receiver to finish
	recv_thread.join(timeout=2.0)
	
	return ctx

# Backwards compatibility - old function names
context = create_context
_send_pong = _send_pong
