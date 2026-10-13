#!/usr/bin/env python3
"""
Test ping/pong and other features with ORIGINAL xhttp implementation.
"""

import sys,os,socket,time,threading,struct,hashlib,base64

HERE = os.path.dirname(os.path.abspath(__file__))
DEV_DIR = os.path.dirname(os.path.dirname(HERE))
if DEV_DIR not in sys.path:
	sys.path.insert(0, DEV_DIR)

from xhttp import xhttp
from xhttp._ import websocket

def handle_request(req):
	print(f"Handling request: {req['method']} {req['target']}")
	ctx = xhttp.serve_websocket(
		req,
		on_message=lambda c, ctx, m: websocket.send(ctx, f"Echo: {m}"),
		on_open=lambda c, ctx: print("WS opened"),
		on_close=lambda c, ctx: print("WS closed")
	)
	if ctx is not None:
		return
	web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
	config = {".html": {"folder": web_dir, "mime": "text/html", "compress": True}}
	xhttp.serve_files(req, config)

def run_server():
	addr = ("127.0.0.1", 8087)
	xhttp.serve_forever(addr, handle_request, ())

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
time.sleep(2)

print("Testing ping/pong with ORIGINAL xhttp...")
print("=" * 50)

key = "dGhlIHNhbXBsZSBub25jZQ=="
sock = socket.socket()
sock.settimeout(5)
sock.connect(("127.0.0.1", 8087))

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

print("Handshake OK")

# Test 1: Send ping
print("\n--- Test 1: Ping ---")
mask = b"\x12\x34\x56\x78"
ping_payload = b"ping123"
ping_frame = bytearray()
ping_frame.append(0x89) # FIN=1, opcode=9
ping_frame.append(0x80 | len(ping_payload))
ping_frame.extend(mask)
masked_ping = bytes(b ^ mask[i % 4] for i, b in enumerate(ping_payload))
ping_frame.extend(masked_ping)

print(f"Sending ping: {ping_frame.hex()}")
sock.sendall(ping_frame)

# Read response
resp = sock.recv(4096)
print(f"Response: {resp.hex()}")
if len(resp) >= 2:
	opcode = resp[0] & 0x0F
	print(f"Opcode: {opcode} (expected 0xA for pong)")
	if opcode == 0xA:
		print("✓ Got pong!")
	else:
		print("✗ Did not get pong")

# Test 2: Send pong (server should ignore)
print("\n--- Test 2: Pong from client ---")
pong_payload = b"pong456"
pong_frame = bytearray()
pong_frame.append(0x8A) # FIN=1, opcode=0xA
pong_frame.append(0x80 | len(pong_payload))
pong_frame.extend(mask)
masked_pong = bytes(b ^ mask[i % 4] for i, b in enumerate(pong_payload))
pong_frame.extend(masked_pong)

print(f"Sending pong: {pong_frame.hex()}")
sock.sendall(pong_frame)

# Should not get a response for pong
sock.settimeout(1)
try:
	resp = sock.recv(4096)
	print(f"Unexpected response: {resp.hex()}")
except socket.timeout:
	print("✓ No response to pong (correct)")

# Test 3: Send binary frame
print("\n--- Test 3: Binary frame ---")
sock.settimeout(5)
binary_data = b"\x00\x01\x02\x03\xFF\xFE"
bin_frame = bytearray()
bin_frame.append(0x82) # FIN=1, opcode=2
bin_frame.append(0x80 | len(binary_data))
bin_frame.extend(mask)
masked_bin = bytes(b ^ mask[i % 4] for i, b in enumerate(binary_data))
bin_frame.extend(masked_bin)

print(f"Sending binary: {bin_frame.hex()}")
sock.sendall(bin_frame)

resp = sock.recv(4096)
print(f"Response: {resp.hex()}")
if len(resp) >= 2:
	opcode = resp[0] & 0x0F
	print(f"Opcode: {opcode}")

sock.close()
print("\nDone!")
