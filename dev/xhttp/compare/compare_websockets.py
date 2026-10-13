#!/usr/bin/env python3
"""
Compare xhttp's websocket output with a known good server.
Give both the same input, see what differences show up in how they respond.
"""

import sys,os,socket,time,threading,struct,hashlib,base64

# Same path setup as harness.py
HERE = os.path.dirname(os.path.abspath(__file__))
XHTTP_DIR = os.path.dirname(HERE)
DEV_DIR = os.path.dirname(XHTTP_DIR)
if DEV_DIR not in sys.path:
	sys.path.insert(0, DEV_DIR)

# Now import xhttp (DEV_DIR on sys.path makes xhttp a namespace package)
from xhttp import xhttp
# Current (buggy) implementation
from xhttp._ import websocket as orig_websocket
# Known good implementation
from xhttp.compare.working_websocket import serve_websocket as working_serve_websocket, send as working_send, compute_accept_key

# =============================================================================
# Frame building utilities (RFC 6455 compliant)
# =============================================================================

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

def parse_frame_with_timeout(sock, timeout=2):
	"""Parse a WebSocket frame with timeout."""
	sock.settimeout(timeout)
	try:
		return parse_frame(sock)
	except socket.timeout:
		return None, None, None
	finally:
		sock.settimeout(5)

def read_handshake(sock):
	"""Read HTTP handshake response until \\r\\n\\r\\n"""
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
	return response

def test_server(port, handler, name):
	"""Test a WebSocket server on given port with given handler."""
	print(f"\n{'='*60}")
	print(f"Testing {name} on port {port}")
	print(f"{'='*60}")
	
	results = {}
	
	# Test 1: Handshake
	print("\n--- Test 1: Handshake ---")
	key = "dGhlIHNhbXBsZSBub25jZQ==" # RFC 6455 test key
	expected_accept = "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
	
	sock = socket.socket()
	sock.settimeout(5)
	sock.connect(("127.0.0.1", port))
	
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
	response = read_handshake(sock)
	
	print(f"Handshake response:\n{response.decode('utf-8', errors='replace')}")
	
	# Check for 101 response
	has_101 = b"HTTP/1.1 101" in response
	has_correct_accept = b"sec-websocket-accept: " + expected_accept.encode() in response
	
	results['handshake_101'] = has_101
	results['handshake_accept'] = has_correct_accept
	
	print(f"  HTTP 101: {'✓' if has_101 else '✗'}")
	print(f"  Correct Accept: {'✓' if has_correct_accept else '✗'}")
	
	if not has_101 or not has_correct_accept:
		sock.close()
		return results
	
	# Test 2: Text frame echo - check frame format
	print("\n--- Test 2: Text frame echo ---")
	payload = b"Hello WebSocket!"
	mask = b"\x12\x34\x56\x78"
	frame = build_frame(0x1, payload, mask=mask)
	
	print(f"Sending frame: {frame.hex()}")
	sock.sendall(frame)
	
	# Read response frame - also capture raw bytes to check frame format
	sock.settimeout(5)
	raw_response = b""
	while len(raw_response) < 2:
		try:
			chunk = sock.recv(2 - len(raw_response))
			if not chunk:
				break
			raw_response += chunk
		except socket.timeout:
			break
	
	if len(raw_response) >= 2:
		# Parse the frame header to get length
		fin = (raw_response[0] & 0x80) != 0
		opcode = raw_response[0] & 0x0F
		masked = (raw_response[1] & 0x80) != 0
		length = raw_response[1] & 0x7F
		
		# Read extended length if needed
		header_len = 2
		if length == 126:
			ext = sock.recv(2)
			raw_response += ext
			length = struct.unpack('>H', ext)[0]
			header_len = 4
		elif length == 127:
			ext = sock.recv(8)
			raw_response += ext
			length = struct.unpack('>Q', ext)[0]
			header_len = 10
		
		if masked:
			mask_bytes = sock.recv(4)
			raw_response += mask_bytes
			header_len += 4
		
		# Read payload
		payload_bytes = sock.recv(length)
		raw_response += payload_bytes
		
		# Now parse properly
		if masked:
			mask = raw_response[header_len-4:header_len]
			payload_data = raw_response[header_len:header_len+length]
			response_payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload_data))
		else:
			response_payload = raw_response[header_len:header_len+length]
		
		# Check if server sent masked frame (incorrect) or unmasked (correct)
		server_masked = masked
		
		print(f"Response: opcode={opcode}, fin={fin}, masked={server_masked}, payload={response_payload}")
		
		results['echo_opcode'] = opcode
		results['echo_payload'] = response_payload
		results['echo_fin'] = fin
		results['echo_server_masked'] = server_masked
		
		expected_echo = b"Echo: Hello WebSocket!"
		if opcode == 0x1 and response_payload == expected_echo:
			print(f" Echo correct: ✓")
		else:
			print(f" Echo WRONG! Expected: {expected_echo}, Got: {response_payload}")
		
		if server_masked:
			print(f" ⚠ Server sent MASKED frame (incorrect per RFC 6455)!")
		else:
			print(f" ✓ Server sent unmasked frame (correct)")
	else:
		print(f" Failed to read response frame")
		results['echo_opcode'] = None
		results['echo_payload'] = None
		results['echo_fin'] = None
		results['echo_server_masked'] = None
	
	# Test 3: Ping/Pong - check frame format
	print("\n--- Test 3: Ping/Pong ---")
	ping_payload = b"ping123"
	ping_frame = build_frame(0x9, ping_payload, mask=mask)
	
	print(f"Sending ping: {ping_frame.hex()}")
	sock.sendall(ping_frame)
	
	# Read response frame with raw capture
	sock.settimeout(5)
	raw_response = b""
	while len(raw_response) < 2:
		try:
			chunk = sock.recv(2 - len(raw_response))
			if not chunk:
				break
			raw_response += chunk
		except socket.timeout:
			break
	
	if len(raw_response) >= 2:
		fin = (raw_response[0] & 0x80) != 0
		opcode = raw_response[0] & 0x0F
		masked = (raw_response[1] & 0x80) != 0
		length = raw_response[1] & 0x7F
		
		header_len = 2
		if length == 126:
			ext = sock.recv(2)
			raw_response += ext
			length = struct.unpack('>H', ext)[0]
			header_len = 4
		elif length == 127:
			ext = sock.recv(8)
			raw_response += ext
			length = struct.unpack('>Q', ext)[0]
			header_len = 10
		
		if masked:
			mask_bytes = sock.recv(4)
			raw_response += mask_bytes
			header_len += 4
		
		payload_bytes = sock.recv(length)
		raw_response += payload_bytes
		
		if masked:
			mask = raw_response[header_len-4:header_len]
			payload_data = raw_response[header_len:header_len+length]
			pong_payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload_data))
		else:
			pong_payload = raw_response[header_len:header_len+length]
		
		server_masked = masked
		
		print(f"Pong response: opcode={opcode}, masked={server_masked}, payload={pong_payload}")
		
		results['pong_opcode'] = opcode
		results['pong_payload'] = pong_payload
		results['pong_server_masked'] = server_masked
		
		if opcode == 0xA and pong_payload == ping_payload:
			print(f" Ping/Pong correct: ✓")
		else:
			print(f" Ping/Pong WRONG! Expected opcode=0xA payload={ping_payload}, Got opcode={opcode} payload={pong_payload}")
		
		if server_masked:
			print(f" ⚠ Server sent MASKED pong frame (incorrect per RFC 6455)!")
		else:
			print(f" ✓ Server sent unmasked pong frame (correct)")
	else:
		print(f" Failed to read pong response")
		results['pong_opcode'] = None
		results['pong_payload'] = None
		results['pong_server_masked'] = None
	
	# Test 4: Close handshake - check frame format
	print("\n--- Test 4: Close handshake ---")
	close_payload = struct.pack('>H', 1000) # Normal closure
	close_frame = build_frame(0x8, close_payload, mask=mask)
	
	print(f"Sending close: {close_frame.hex()}")
	sock.sendall(close_frame)
	
	# Read response frame with raw capture
	sock.settimeout(3)
	raw_response = b""
	while len(raw_response) < 2:
		try:
			chunk = sock.recv(2 - len(raw_response))
			if not chunk:
				break
			raw_response += chunk
		except socket.timeout:
			break
	
	if len(raw_response) >= 2:
		fin = (raw_response[0] & 0x80) != 0
		opcode = raw_response[0] & 0x0F
		masked = (raw_response[1] & 0x80) != 0
		length = raw_response[1] & 0x7F
		
		header_len = 2
		if length == 126:
			ext = sock.recv(2)
			raw_response += ext
			length = struct.unpack('>H', ext)[0]
			header_len = 4
		elif length == 127:
			ext = sock.recv(8)
			raw_response += ext
			length = struct.unpack('>Q', ext)[0]
			header_len = 10
		
		if masked:
			mask_bytes = sock.recv(4)
			raw_response += mask_bytes
			header_len += 4
		
		payload_bytes = sock.recv(length)
		raw_response += payload_bytes
		
		if masked:
			mask = raw_response[header_len-4:header_len]
			payload_data = raw_response[header_len:header_len+length]
			close_response_payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload_data))
		else:
			close_response_payload = raw_response[header_len:header_len+length]
		
		server_masked = masked
		
		print(f"Close response: opcode={opcode}, masked={server_masked}, payload={close_response_payload}, fin={fin}")
		
		results['close_opcode'] = opcode
		results['close_payload'] = close_response_payload
		results['close_fin'] = fin
		results['close_server_masked'] = server_masked
		
		if opcode == 0x8:
			print(f" Close frame received: ✓")
			if close_response_payload and len(close_response_payload) >= 2:
				code = struct.unpack('>H', close_response_payload[:2])[0]
				print(f" Close code: {code}")
		elif opcode is None:
			print(f" Close WRONG! No response (server didn't send close frame)")
		else:
			print(f" Close WRONG! Expected opcode=0x8, Got opcode={opcode}")
		
		if server_masked:
			print(f" ⚠ Server sent MASKED close frame (incorrect per RFC 6455)!")
		else:
			print(f" ✓ Server sent unmasked close frame (correct)")
	else:
		print(f"Close response: TIMEOUT (no response)")
		results['close_opcode'] = 'TIMEOUT'
		results['close_payload'] = None
		results['close_fin'] = None
		results['close_server_masked'] = None
	
	sock.close()
	return results

def run_original_server(port):
	"""Run server with original xhttp websocket."""
	def handle_request(req):
		ctx = xhttp.serve_websocket(
			req,
			on_message=lambda c, ctx, m: orig_websocket.send(ctx, f"Echo: {m}"),
			on_open=lambda c, ctx: print(f" [{port}] WS opened"),
			on_close=lambda c, ctx: print(f" [{port}] WS closed")
		)
		if ctx is not None:
			return
		# Fall through to file server
		web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
		config = {".html": {"folder": web_dir, "mime": "text/html", "compress": True}}
		xhttp.serve_files(req, config)
	
	def run_server():
		addr = ("127.0.0.1", port)
		xhttp.serve_forever(addr, handle_request, ())
	
	server_thread = threading.Thread(target=run_server, daemon=True)
	server_thread.start()
	time.sleep(2) # Wait for server to start

def run_working_server(port):
	"""Run server with working_websocket."""
	def handle_request(req):
		ctx = working_serve_websocket(
			req,
			on_message=lambda c, ctx, m: working_send(ctx, f"Echo: {m}"),
			on_open=lambda c, ctx: print(f" [{port}] WS opened"),
			on_close=lambda c, ctx: print(f" [{port}] WS closed")
		)
		if ctx is not None:
			return
		# Fall through to file server
		web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
		config = {".html": {"folder": web_dir, "mime": "text/html", "compress": True}}
		xhttp.serve_files(req, config)
	
	def run_server():
		addr = ("127.0.0.1", port)
		xhttp.serve_forever(addr, handle_request, ())
	
	server_thread = threading.Thread(target=run_server, daemon=True)
	server_thread.start()
	time.sleep(2) # Wait for server to start

def main():
	print("="*60)
	print("WEBSOCKET IMPLEMENTATION COMPARISON")
	print("="*60)
	
	# Test original (buggy) implementation
	print("\nStarting ORIGINAL xhttp websocket server on port 8086...")
	run_original_server(8086)
	original_results = test_server(8086, None, "ORIGINAL xhttp websocket")
	
	# Give some time for threads to clean up
	time.sleep(1)
	
	# Test working implementation
	print("\nStarting WORKING websocket server on port 8087...")
	run_working_server(8087)
	working_results = test_server(8087, None, "WORKING websocket")
	
	# Compare results
	print("\n" + "="*60)
	print("COMPARISON SUMMARY")
	print("="*60)
	
	tests = [
		('handshake_101', 'Handshake HTTP 101'),
		('handshake_accept', 'Handshake Accept Key'),
		('echo_opcode', 'Echo Opcode (should be 0x1)'),
		('echo_payload', 'Echo Payload'),
		('echo_fin', 'Echo FIN bit'),
		('echo_server_masked', 'Echo Server Masked (should be False)'),
		('pong_opcode', 'Pong Opcode (should be 0xA)'),
		('pong_payload', 'Pong Payload'),
		('pong_server_masked', 'Pong Server Masked (should be False)'),
		('close_opcode', 'Close Opcode (should be 0x8)'),
		('close_payload', 'Close Payload'),
		('close_fin', 'Close FIN bit'),
		('close_server_masked', 'Close Server Masked (should be False)'),
	]
	
	for key, desc in tests:
		orig = original_results.get(key, 'N/A')
		work = working_results.get(key, 'N/A')
		match = "✓ MATCH" if orig == work else "✗ DIFFER"
		print(f" {desc}:")
		print(f" Original: {orig}")
		print(f" Working: {work}")
		print(f" {match}")
	
	print("\n" + "="*60)
	print("DETAILED DIFFERENCES:")
	print("="*60)
	
	# Detailed analysis
	if original_results.get('handshake_101') != working_results.get('handshake_101'):
		print("  ⚠ Handshake HTTP status differs")
	if original_results.get('handshake_accept') != working_results.get('handshake_accept'):
		print("  ⚠ Handshake Accept key differs - likely header case issue")
	
	if original_results.get('echo_opcode') != 0x1:
		print(f"  ⚠ Original echo opcode wrong: {original_results.get('echo_opcode')} (expected 0x1)")
	if original_results.get('echo_payload') != b"Echo: Hello WebSocket!":
		print(f"  ⚠ Original echo payload wrong: {original_results.get('echo_payload')}")
	
	if original_results.get('pong_opcode') != 0xA:
		print(f"  ⚠ Original pong opcode wrong: {original_results.get('pong_opcode')} (expected 0xA)")
	if original_results.get('pong_payload') != b"ping123":
		print(f"  ⚠ Original pong payload wrong: {original_results.get('pong_payload')}")
	
	if original_results.get('close_opcode') == 'TIMEOUT':
		print(f" ⚠ Original close: TIMEOUT - server didn't respond to close frame")
	elif original_results.get('close_opcode') != 0x8:
		print(f"  ⚠ Original close opcode wrong: {original_results.get('close_opcode')} (expected 0x8)")
	
	print("\nDone!")

if __name__ == "__main__":
	main()
