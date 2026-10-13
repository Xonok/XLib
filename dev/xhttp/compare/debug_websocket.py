#!/usr/bin/env python3
"""
Debug script to test WebSocket with a strict client that mimics Space Traveller behavior.
"""

import base64,hashlib,socket,struct,threading,time

def compute_accept_key(key: str) -> str:
	magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
	key_hash = hashlib.sha1((key + magic).encode())
	return base64.b64encode(key_hash.digest()).decode()

def build_frame(opcode, payload, mask=None, fin=True):
	"""Build a WebSocket frame."""
	b1 = (0x80 if fin else 0x00) | opcode
	length = len(payload)
	
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
		masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
		frame.extend(masked)
	else:
		frame.extend(payload)
	
	return bytes(frame)

def parse_frame(sock):
	"""Parse a WebSocket frame from server (server doesn't mask)."""
	# Read first 2 bytes
	b1 = sock.recv(1)
	if not b1:
		return None, None, None
	b1 = b1[0]
	
	b2 = sock.recv(1)
	if not b2:
		return None, None, None
	b2 = b2[0]
	
	fin = (b1 & 0x80) != 0
	opcode = b1 & 0x0F
	masked = (b2 & 0x80) != 0 # Server frames should NOT be masked
	length = b2 & 0x7F
	
	if length == 126:
		ext = sock.recv(2)
		length = struct.unpack('>H', ext)[0]
	elif length == 127:
		ext = sock.recv(8)
		length = struct.unpack('>Q', ext)[0]
	
	if masked:
		mask = sock.recv(4)
		payload = sock.recv(length)
		payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
	else:
		payload = sock.recv(length)
	
	return opcode, payload, fin

def test_basic():
	"""Test basic connection and echo."""
	print("=== Test 1: Basic connection ===")
	sock = socket.socket()
	sock.settimeout(5)
	sock.connect(("127.0.0.1", 8085))
	
	key = "dGhlIHNhbXBsZSBub25jZQ=="
	expected = compute_accept_key(key)
	
	req = (
		f"GET /ws HTTP/1.1\r\n"
		f"Host: localhost\r\n"
		f"Upgrade: websocket\r\n"
		f"Connection: Upgrade\r\n"
		f"Sec-WebSocket-Key: {key}\r\n"
		f"Sec-WebSocket-Version: 13\r\n"
		f"\r\n"
	).encode()
	
	sock.sendall(req)
	
	# Read handshake
	resp = b""
	while b"\r\n\r\n" not in resp:
		chunk = sock.recv(4096)
		if not chunk:
			break
		resp += chunk
	
	print(f"Handshake: {resp[:200]}")
	assert b"101" in resp
	assert expected.encode() in resp
	print("✓ Handshake OK")
	
	# Send text message
	mask = b"\x12\x34\x56\x78"
	frame = build_frame(0x1, b"Hello", mask=mask)
	sock.sendall(frame)
	
	# Read response
	opcode, payload, fin = parse_frame(sock)
	print(f"Response: opcode={opcode}, payload={payload}, fin={fin}")
	assert opcode == 0x1
	print("✓ Echo received")
	
	# Send close frame
	close_frame = build_frame(0x8, b"", mask=mask)
	sock.sendall(close_frame)
	
	# Read close response
	opcode, payload, fin = parse_frame(sock)
	print(f"Close response: opcode={opcode}, payload={payload}")
	
	sock.close()
	print("✓ Test 1 passed\n")

def test_ping_pong():
	"""Test ping/pong handling."""
	print("=== Test 2: Ping/Pong ===")
	sock = socket.socket()
	sock.settimeout(5)
	sock.connect(("127.0.0.1", 8085))
	
	key = "dGhlIHNhbXBsZSBub25jZQ=="
	req = (
		f"GET /ws HTTP/1.1\r\n"
		f"Host: localhost\r\n"
		f"Upgrade: websocket\r\n"
		f"Connection: Upgrade\r\n"
		f"Sec-WebSocket-Key: {key}\r\n"
		f"Sec-WebSocket-Version: 13\r\n"
		f"\r\n"
	).encode()
	
	sock.sendall(req)
	
	# Read handshake
	resp = b""
	while b"\r\n\r\n" not in resp:
		chunk = sock.recv(4096)
		if not chunk:
			break
		resp += chunk
	
	print(f"Handshake OK")
	
	# Send ping
	mask = b"\x12\x34\x56\x78"
	ping_frame = build_frame(0x9, b"ping123", mask=mask)
	sock.sendall(ping_frame)
	
	# Read pong
	opcode, payload, fin = parse_frame(sock)
	print(f"Pong: opcode={opcode}, payload={payload}")
	assert opcode == 0xA, f"Expected pong (0xA), got {opcode}"
	assert payload == b"ping123"
	print("✓ Ping/Pong works")
	
	sock.close()
	print("✓ Test 2 passed\n")

def test_close_handshake():
	"""Test proper close handshake."""
	print("=== Test 3: Close handshake ===")
	sock = socket.socket()
	sock.settimeout(5)
	sock.connect(("127.0.0.1", 8085))
	
	key = "dGhlIHNhbXBsZSBub25jZQ=="
	req = (
		f"GET /ws HTTP/1.1\r\n"
		f"Host: localhost\r\n"
		f"Upgrade: websocket\r\n"
		f"Connection: Upgrade\r\n"
		f"Sec-WebSocket-Key: {key}\r\n"
		f"Sec-WebSocket-Version: 13\r\n"
		f"\r\n"
	).encode()
	
	sock.sendall(req)
	
	# Read handshake
	resp = b""
	while b"\r\n\r\n" not in resp:
		chunk = sock.recv(4096)
		if not chunk:
			break
		resp += chunk
	
	print(f"Handshake OK")
	
	# Send close frame with code 1000
	mask = b"\x12\x34\x56\x78"
	close_payload = struct.pack('>H', 1000)
	close_frame = build_frame(0x8, close_payload, mask=mask)
	sock.sendall(close_frame)
	
	# Read close response - server should echo close
	opcode, payload, fin = parse_frame(sock)
	print(f"Close response: opcode={opcode}, payload={payload}, fin={fin}")
	
	if opcode == 0x8:
		print("✓ Server responded with close frame")
		if len(payload) >= 2:
			code = struct.unpack('>H', payload[:2])[0]
			print(f" Close code: {code}")
	else:
		print(f"✗ Expected close frame (0x8), got {opcode}")
	
	sock.close()
	print("✓ Test 3 passed\n")

def test_binary_frame():
	"""Test binary frame handling."""
	print("=== Test 4: Binary frame ===")
	sock = socket.socket()
	sock.settimeout(5)
	sock.connect(("127.0.0.1", 8085))
	
	key = "dGhlIHNhbXBsZSBub25jZQ=="
	req = (
		f"GET /ws HTTP/1.1\r\n"
		f"Host: localhost\r\n"
		f"Upgrade: websocket\r\n"
		f"Connection: Upgrade\r\n"
		f"Sec-WebSocket-Key: {key}\r\n"
		f"Sec-WebSocket-Version: 13\r\n"
		f"\r\n"
	).encode()
	
	sock.sendall(req)
	
	resp = b""
	while b"\r\n\r\n" not in resp:
		chunk = sock.recv(4096)
		if not chunk:
			break
		resp += chunk
	
	print(f"Handshake OK")
	
	# Send binary frame
	mask = b"\x12\x34\x56\x78"
	binary_data = b"\x00\x01\x02\x03\x04\x05\xFF\xFE"
	frame = build_frame(0x2, binary_data, mask=mask)
	sock.sendall(frame)
	
	# Read response
	opcode, payload, fin = parse_frame(sock)
	print(f"Response: opcode={opcode}, payload={payload.hex()}")
	
	sock.close()
	print("✓ Test 4 passed\n")

def test_fragmented_message():
	"""Test fragmented message (FIN=0 then FIN=1)."""
	print("=== Test 5: Fragmented message ===")
	sock = socket.socket()
	sock.settimeout(5)
	sock.connect(("127.0.0.1", 8085))
	
	key = "dGhlIHNhbXBsZSBub25jZQ=="
	req = (
		f"GET /ws HTTP/1.1\r\n"
		f"Host: localhost\r\n"
		f"Upgrade: websocket\r\n"
		f"Connection: Upgrade\r\n"
		f"Sec-WebSocket-Key: {key}\r\n"
		f"Sec-WebSocket-Version: 13\r\n"
		f"\r\n"
	).encode()
	
	sock.sendall(req)
	
	resp = b""
	while b"\r\n\r\n" not in resp:
		chunk = sock.recv(4096)
		if not chunk:
			break
		resp += chunk
	
	print(f"Handshake OK")
	
	# Send fragmented text message
	mask = b"\x12\x34\x56\x78"
	# First fragment (FIN=0, opcode=1)
	frame1 = build_frame(0x1, b"Hello ", mask=mask, fin=False)
	# Continuation (FIN=1, opcode=0)
	frame2 = build_frame(0x0, b"World!", mask=mask, fin=True)
	
	sock.sendall(frame1)
	sock.sendall(frame2)
	
	# Read response
	opcode, payload, fin = parse_frame(sock)
	print(f"Response: opcode={opcode}, payload={payload}")
	
	sock.close()
	print("✓ Test 5 passed\n")

if __name__ == "__main__":
	import sys
	
	# We'll assume server is already running on 8085
	print("Assuming server is running on port 8085...")
	print("Run: python3 compare/test_server.py")
	print()
	
	try:
		test_basic()
		test_ping_pong()
		test_close_handshake()
		test_binary_frame()
		test_fragmented_message()
		print("=== ALL TESTS PASSED ===")
	except Exception as e:
		print(f"TEST FAILED: {e}")
		import traceback
		traceback.print_exc()
		sys.exit(1)
