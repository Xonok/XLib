#!/usr/bin/env python3
"""
Test script to verify the example server works.
"""

import sys,os,socket,time,threading

HERE = os.path.dirname(os.path.abspath(__file__))
DEV_DIR = os.path.dirname(os.path.dirname(HERE))
if DEV_DIR not in sys.path:
	sys.path.insert(0, DEV_DIR)

from xhttp import xhttp
from xhttp.compare.working_websocket import serve_websocket

# Test HTTP request handler
def handle_request(req):
	print(f"Handling request: {req['method']} {req['target']}")
	# Try WebSocket upgrade first
	ctx = serve_websocket(
		req,
		on_message=lambda c, ctx, m: print(f"WS message: {m}"),
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

# Start server in background thread
def run_server():
	addr = ("127.0.0.1", 8084)
	xhttp.serve_forever(addr, handle_request, ())

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

# Wait for server to start
time.sleep(2)

# Test with a simple HTTP request
print("Testing HTTP request...")
sock = socket.socket()
sock.settimeout(5)
sock.connect(("127.0.0.1", 8084))
sock.sendall(b"GET /index.html HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")

# Also test the web directory directly
print("CWD:", os.getcwd())
print("Checking file exists:", os.path.exists(os.path.join(os.getcwd(), "web", "index.html")))
print("Full path:", os.path.join(os.getcwd(), "web", "index.html"))

# Read response
response = b""
while True:
	try:
		chunk = sock.recv(4096)
		if not chunk:
			break
		response += chunk
	except socket.timeout:
		break

sock.close()

print("Response:")
print(response.decode('utf-8', errors='replace'))

print("\nDone!")
