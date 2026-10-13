#!/usr/bin/env python3
"""
Test script to verify the WebSocket functionality works.
"""

import sys,os,socket,time,threading,struct,hashlib,base64

# Add repo root to path
HERE = os.path.dirname(os.path.abspath(__file__))
DEV_DIR = os.path.dirname(os.path.dirname(HERE))
if DEV_DIR not in sys.path:
	sys.path.insert(0, DEV_DIR)

from xhttp import xhttp
from xhttp.compare.working_websocket import serve_websocket, compute_accept_key

# Test HTTP request handler
def handle_request(req):
	print(f"Handling request: {req['method']} {req['target']}")
	# Try WebSocket upgrade first
	ctx = serve_websocket(
		req,
		on_message=lambda c, ctx, m: send_echo(c, ctx, m),
		on_open=lambda c, ctx: print("WS opened"),
		on_close=lambda c, ctx: print("WS closed")
	)
	
	if ctx is not None:
		print("WebSocket connection handled")
		return
	
	print("Falling through to file server")
	web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
	config = {
		".html": {"folder": web_dir, "mime": "text/html", "compress": True},
	}
	
	xhttp.serve_files(req, config)

def send_echo(client, ctx, message):
	"""Echo the message back to the client."""
	from xhttp.compare.working_websocket import send
	send(ctx, f"Echo: {message}")

# Start server in background thread
def run_server():
	addr = ("127.0.0.1", 8085)
	xhttp.serve_forever(addr, handle_request, ())

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

# Wait for server to start
time.sleep(2)

print("Testing WebSocket handshake...")

# Test WebSocket handshake
key = "dGhlIHNhbXBsZSBub25jZQ==" # RFC 6455 test key
expected_accept = "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="

# Verify our compute_accept_key works
computed = compute_accept_key(key)
print(f"Computed accept: {computed}")
print(f"Expected accept: {expected_accept}")
assert computed == expected_accept, "Accept key computation failed!"
print("✓ Accept key computation correct")

# Now test actual WebSocket connection
sock = socket.socket()
sock.settimeout(5)
sock.connect(("127.0.0.1", 8085))

# Send WebSocket upgrade request
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

# Read handshake response
response = b""
while True:
	try:
		chunk = sock.recv(4096)
		if not chunk:
			break
		response += chunk
		if b"\r\n\r\n" in response:
			break
	except socket.timeout:
		break

print("Handshake response:")
print(response.decode('utf-8', errors='replace'))

# Check for 101 response
assert b"HTTP/1.1 101" in response, "Not a 101 response"
assert b"sec-websocket-accept: " + expected_accept.encode() in response, "Wrong accept key"
print("✓ WebSocket handshake successful!")

# Now send a text frame
# Frame format: FIN=1, opcode=1 (text), MASK=1, payload length, mask, masked payload
payload = b"Hello WebSocket!"
mask = b"\x12\x34\x56\x78"
masked_payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

frame = bytearray()
frame.append(0x81) # FIN=1, opcode=1
frame.append(0x80 | len(payload)) # MASK=1, length
frame.extend(mask)
frame.extend(masked_payload)

print(f"Sending frame: {frame.hex()}")
sock.sendall(frame)

# Read response frame
response_frame = sock.recv(4096)
print(f"Received frame: {response_frame.hex()}")

# Parse response frame
if len(response_frame) >= 2:
	fin = (response_frame[0] & 0x80) != 0
	opcode = response_frame[0] & 0x0F
	masked = (response_frame[1] & 0x80) != 0
	length = response_frame[1] & 0x7F
	
	print(f"FIN: {fin}, opcode: {opcode}, masked: {masked}, length: {length}")
	
	if opcode == 0x1: # Text frame
		# Server frames are not masked
		payload_start = 2
		if length == 126:
			payload_start = 4
		elif length == 127:
			payload_start = 10
		
		response_payload = response_frame[payload_start:payload_start+length]
		print(f"Response payload: {response_payload.decode('utf-8', errors='replace')}")

sock.close()

print("\nDone! WebSocket test passed!")
