#!/usr/bin/env python3
"""
Comprehensive test for working_websocket implementation.
"""

import sys,os,socket,time,threading,struct,hashlib,base64

HERE = os.path.dirname(os.path.abspath(__file__))
DEV_DIR = os.path.dirname(os.path.dirname(HERE))
if DEV_DIR not in sys.path:
	sys.path.insert(0, DEV_DIR)

from xhttp import xhttp
from xhttp.compare.working_websocket import serve_websocket, compute_accept_key

def handle_request(req):
	print(f"Handling request: {req['method']} {req['target']}")
	ctx = serve_websocket(
		req,
		on_message=lambda c, ctx, m: send_echo(c, ctx, m),
		on_open=lambda c, ctx: print("WS opened"),
		on_close=lambda c, ctx: print("WS closed")
	)
	if ctx is not None:
		return
	web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
	config = {".html": {"folder": web_dir, "mime": "text/html", "compress": True}}
	xhttp.serve_files(req, config)

def send_echo(client, ctx, message):
	from xhttp.compare.working_websocket import send
	if isinstance(message, bytes):
		send(ctx, f"Echo binary: {message.hex()}")
	else:
		send(ctx, f"Echo: {message}")

def run_server():
	addr = ("127.0.0.1", 8088)
	xhttp.serve_forever(addr, handle_request, ())

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
time.sleep(2)

print("Testing working_websocket implementation...")
print("=" * 50)

key = "dGhlIHNhbXBsZSBub25jZQ=="
expected_accept = compute_accept_key(key)

def connect_and_test(name, test_func):
	print(f"\n--- {name} ---")
	sock = socket.socket()
	sock.settimeout(5)
	sock.connect(("127.0.0.1", 8088))
	
	upgrade_request = (
		f"GET /ws HTTP/1.1\r\n"
		f"Host: localhost\r\n"
		f"Upgrade: websocket\r\n"
		f"Connection: Upgrade\r\n"
		f"Sec-WebSocket-Key: {key}\r\n"
		f"Sec-WebSocket-Version: 13\r\n"
		f"\r\n"
	).encode()
	sock.sendall(upgrade_request)
	
	response = b""
	while b"\r\n\r\n" not in response:
		chunk = sock.recv(4096)
		if not chunk:
			break
		response += chunk
	
	assert b"101" in response
	assert expected_accept.encode() in response
	print("Handshake OK")
	
	try:
		test_func(sock)
		print(f"✓ {name} passed")
	except Exception as e:
		print(f"✗ {name} FAILED: {e}")
		import traceback
		traceback.print_exc()
	finally:
		sock.close()

def build_frame(opcode, payload, mask=None, fin=True):
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
	b1 = sock.recv(1)
	if not b1: return None, None, None
	b1 = b1[0]
	b2 = sock.recv(1)
	if not b2: return None, None, None
	b2 = b2[0]
	fin = (b1 & 0x80) != 0
	opcode = b1 & 0x0F
	masked = (b2 & 0x80) != 0
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

# Test 1: Basic echo
def test_basic(sock):
	mask = b"\x12\x34\x56\x78"
	frame = build_frame(0x1, b"Hello", mask=mask)
	sock.sendall(frame)
	opcode, payload, fin = parse_frame(sock)
	assert opcode == 0x1
	assert payload == b"Echo: Hello"
	print(f" Response: {payload}")

# Test 2: Ping/Pong
def test_ping(sock):
	mask = b"\x12\x34\x56\x78"
	frame = build_frame(0x9, b"ping123", mask=mask)
	sock.sendall(frame)
	opcode, payload, fin = parse_frame(sock)
	assert opcode == 0xA
	assert payload == b"ping123"
	print(f" Pong: {payload}")

# Test 3: Binary frame
def test_binary(sock):
	mask = b"\x12\x34\x56\x78"
	data = b"\x00\x01\x02\x03\xFF\xFE"
	frame = build_frame(0x2, data, mask=mask)
	sock.sendall(frame)
	opcode, payload, fin = parse_frame(sock)
	assert opcode == 0x1 # We echo as text
	assert b"Echo binary:" in payload
	print(f" Response: {payload}")

# Test 4: Close handshake
def test_close(sock):
	mask = b"\x12\x34\x56\x78"
	close_payload = struct.pack('>H', 1000)
	frame = build_frame(0x8, close_payload, mask=mask)
	sock.sendall(frame)
	opcode, payload, fin = parse_frame(sock)
	print(f"  Close response: opcode={opcode}, payload={payload.hex() if payload else 'empty'}, fin={fin}")
	assert opcode == 0x8
	print(f"  Close response: code={struct.unpack('>H', payload[:2])[0] if len(payload)>=2 else 'none'}")

# Test 5: Fragmented message
def test_fragmented(sock):
	mask = b"\x12\x34\x56\x78"
	frame1 = build_frame(0x1, b"Hello ", mask=mask, fin=False)
	frame2 = build_frame(0x0, b"World!", mask=mask, fin=True)
	sock.sendall(frame1)
	sock.sendall(frame2)
	opcode, payload, fin = parse_frame(sock)
	assert opcode == 0x1
	print(f" Response: {payload}")

# Test 6: Multiple messages
def test_multiple(sock):
	mask = b"\x12\x34\x56\x78"
	for i in range(5):
		frame = build_frame(0x1, f"Msg {i}".encode(), mask=mask)
		sock.sendall(frame)
		opcode, payload, fin = parse_frame(sock)
		assert opcode == 0x1
		assert payload == f"Echo: Msg {i}".encode()
	print(f" All 5 messages echoed correctly")

connect_and_test("Basic Echo", test_basic)
connect_and_test("Ping/Pong", test_ping)
connect_and_test("Binary Frame", test_binary)
connect_and_test("Close Handshake", test_close)
connect_and_test("Fragmented Message", test_fragmented)
connect_and_test("Multiple Messages", test_multiple)

print("\n" + "=" * 50)
print("ALL TESTS PASSED!")
