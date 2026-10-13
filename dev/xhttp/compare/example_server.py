#!/usr/bin/env python3
"""
Example WebSocket Server using the working WebSocket implementation.

This server demonstrates correct WebSocket handling that works with browsers.
Run with: python3 example_server.py

Then open http://localhost:8080 in a browser to test.
"""

import os,sys,threading,time

HERE = os.path.dirname(os.path.abspath(__file__))
DEV_DIR = os.path.dirname(os.path.dirname(HERE))
if DEV_DIR not in sys.path:
	sys.path.insert(0, DEV_DIR)

from xhttp import xhttp
from xhttp.compare.working_websocket import serve_websocket

# ============================================================================
# WebSocket Handler
# ============================================================================

# Store active connections for broadcast
active_connections = []
connections_lock = threading.Lock()

def on_ws_open(client, ctx):
	"""Called when a new WebSocket connection is established."""
	with connections_lock:
		active_connections.append(ctx)
	print(f"WebSocket opened. Active connections: {len(active_connections)}")
	# Send welcome message
	send_ws_message(ctx, "Welcome! You are connected to the WebSocket server.")

def on_ws_message(client, ctx, message):
	"""Called when a message is received from a client."""
	print(f"Received: {message}")
	
	# Echo the message back
	send_ws_message(ctx, f"Echo: {message}")
	
	# Broadcast to all other connections
	broadcast(f"User said: {message}", exclude=ctx)

def on_ws_close(client, ctx):
	"""Called when a WebSocket connection closes."""
	with connections_lock:
		if ctx in active_connections:
			active_connections.remove(ctx)
	print(f"WebSocket closed. Active connections: {len(active_connections)}")

def send_ws_message(ctx, message):
	"""Send a message to a specific client."""
	from xhttp.compare.working_websocket import send
	send(ctx, message)

def broadcast(message, exclude=None):
	"""Broadcast a message to all connected clients."""
	from xhttp.compare.working_websocket import send
	with connections_lock:
		for ctx in active_connections:
			if ctx is not exclude:
				send(ctx, message)

# ============================================================================
# HTTP Request Handler
# ============================================================================

def handle_request(req):
	"""Main request handler - routes to WebSocket or file server."""
	print(f"Handling request: {req['method']} {req['target']}")
	# Try WebSocket upgrade first
	ctx = serve_websocket(
		req,
		on_message=on_ws_message,
		on_open=on_ws_open,
		on_close=on_ws_close
	)
	
	if ctx is not None:
		# WebSocket handled - serve_websocket runs sender in this thread
		print("WebSocket connection handled")
		return
	
	print("Falling through to file server")
	# Fall through to file server
	web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
	config = {
		".html": {"folder": web_dir, "mime": "text/html", "compress": True},
		".js": {"folder": web_dir, "mime": "application/javascript", "compress": True},
		".css": {"folder": web_dir, "mime": "text/css", "compress": True},
		".json": {"folder": web_dir, "mime": "application/json", "compress": True},
		".png": {"folder": web_dir, "mime": "image/png", "compress": False},
		".jpg": {"folder": web_dir, "mime": "image/jpeg", "compress": False},
		".ico": {"folder": web_dir, "mime": "image/x-icon", "compress": False},
	}
	
	xhttp.serve_files(req, config)

# ============================================================================
# Server Startup
# ============================================================================

if __name__ == "__main__":
	import argparse
	
	parser = argparse.ArgumentParser(description="WebSocket Example Server")
	parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
	parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
	parser.add_argument("--ssl-cert", help="SSL certificate file")
	parser.add_argument("--ssl-key", help="SSL private key file")
	args = parser.parse_args()
	
	addr = (args.host, args.port)
	ssl_keys = None
	if args.ssl_cert and args.ssl_key:
		ssl_keys = (args.ssl_cert, args.ssl_key)
		print(f"Starting HTTPS/WSS server on https://{args.host}:{args.port}")
	else:
		print(f"Starting HTTP/WS server on http://{args.host}:{args.port}")
	
	print("WebSocket endpoint: ws://{args.host}:{args.port}/ws")
	print("Web UI: http://{args.host}:{args.port}/")
	print("Press Ctrl+C to stop")
	
	try:
		promise = xhttp.serve_forever(addr, handle_request, (), ssl_keys=ssl_keys, new_thread=True)
		xhttp.await_startup(promise)
		
		# Keep main thread alive
		while True:
			time.sleep(1)
	except KeyboardInterrupt:
		print("\nShutting down...")
	except Exception as e:
		print(f"Server error: {e}")
		import traceback
		traceback.print_exc()
