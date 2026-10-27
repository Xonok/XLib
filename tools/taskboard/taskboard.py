"""taskboard — the wide all-tasks view, served as one local page.

The command starts a small HTTP server over the task store and serves one
page: `GET /api/tasks` re-reads the store and returns the board, and
`POST /api/due` applies one due-date edit through taskupdate's append path.
The model is `board.py`; this file is the command, its routes, its headers and
its lifecycle.

In order: `main` (arguments, the store check, the bind, the serve loop);
`_BoardServer` and `_Handler` (one request, its routes and its responses); the
helpers the two use. The suite imports this module for the model, so the names
from `board.py` are re-exported here rather than reached through its file.
"""
import argparse,hmac,ipaddress,json,os,socket,sys,time,traceback
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlsplit

_here = Path(__file__).resolve().parent
_root = _here.parent.parent
if str(_root) not in sys.path:
	sys.path.insert(0, str(_root))

from tools.taskboard.board import InvalidDue,StoreMissing,TaskChanged,TaskNotFound,TaskNotOpen,order_tasks,parse_due_edit,read_board,set_due,stored_due_ts,summarise,task_payload
from tools.taskview import taskupdate
from tools.taskview.taskview import resolve_csv,resolve_data_dir

_MAX_BODY = 64 * 1024
_SECURITY_HEADERS = {
	"X-Content-Type-Options": "nosniff",
	"Referrer-Policy": "no-referrer",
	"Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
}

def main(argv: list[str] | None = None) -> int:
	"""R30, R31: check the store, bind once, print one line, serve until SIGINT."""
	args = parse_args(argv)
	csv_path = _store_path(args, os.environ)
	if not csv_path.exists():
		return _refuse(f"the task store {csv_path} does not exist")
	token = args.token or os.environ.get("TASKBOARD_TOKEN")
	if not _is_loopback(args.host) and (token is None or len(token) < 16):
		return _refuse("a token of at least 16 characters is required off loopback (--token or $TASKBOARD_TOKEN)")
	try:
		payload = read_board(csv_path, int(time.time()))
		server = _board_server_class(args.host)((args.host, args.port), _Handler, csv_path, token)
	except StoreMissing as error:
		return _refuse(str(error))
	except (OSError, OverflowError) as error:
		return _refuse(f"cannot listen on {args.host}:{args.port}: {error}")
	port = server.server_address[1]
	print(f"taskboard: {_startup_url(args.host, port, token)} — store {csv_path}, {len(payload['tasks'])} open", flush=True)
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		pass
	finally:
		server.server_close()
	return 0

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
	parser = argparse.ArgumentParser(prog="taskboard", description="Serve the wide all-tasks view as one local page.")
	parser.add_argument("--csv", type=Path, default=None, help="the task store; default is $TASKVIEW_CSV or <data-dir>/tasks.csv")
	parser.add_argument("--data-dir", type=Path, default=None, help="the taskview data directory")
	parser.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
	parser.add_argument("--port", type=int, default=8780, help="bind port (default 8780; 0 picks a free port)")
	parser.add_argument("--token", default=None, help="access token; off loopback it is required and at least 16 characters")
	return parser.parse_args(argv)

def _refuse(message: str) -> int:
	sys.stderr.write(f"taskboard: {message}\n")
	return 1

def _store_path(args: argparse.Namespace, environ) -> Path:
	"""R1: --csv, then $TASKVIEW_CSV, then <data-dir>/tasks.csv.

	The data directory and the join are taskview's own functions, imported so
	the three tools cannot disagree about which file they mean.
	"""
	if args.csv is not None:
		return args.csv
	if "TASKVIEW_CSV" in environ:
		return Path(environ["TASKVIEW_CSV"])
	return resolve_csv(resolve_data_dir(args.data_dir, environ), None)

def _board_server_class(host: str) -> type:
	return _BoardServerV6 if ":" in host else _BoardServer

def _is_loopback(host: str) -> bool:
	if host == "localhost":
		return True
	try:
		return ipaddress.ip_address(host).is_loopback
	except ValueError:
		return False

def _startup_url(host: str, port: int, token: str | None) -> str:
	display = "127.0.0.1" if host in ("0.0.0.0", "") else host
	if ":" in display:
		display = f"[{display}]"
	url = f"http://{display}:{port}/"
	if token is None:
		return url
	return url + f"?token={token}"

def _etag(state: os.stat_result) -> str:
	return f'"{state.st_mtime_ns:x}-{state.st_size:x}"'

def _is_json(content_type: str | None) -> bool:
	if content_type is None:
		return False
	return content_type.split(";")[0].strip().lower() == "application/json"

def _cookie_token(header: str | None) -> str | None:
	if not header:
		return None
	for part in header.split(";"):
		name, _, value = part.strip().partition("=")
		if name == "taskboard":
			return value
	return None

def _parse_edit(body: bytes) -> tuple | str:
	"""The three request keys, or the message explaining why they are not usable."""
	try:
		request = json.loads(body)
	except (json.JSONDecodeError, UnicodeDecodeError):
		return "the body is not valid JSON"
	if not isinstance(request, dict):
		return "the body must be a JSON object"
	task_id = request.get("id")
	value = request.get("value")
	expected_chg_ts = request.get("expected_chg_ts")
	# `bool` is an `int` in Python, and `true` is not a task id or a version.
	if type(task_id) is not int:
		return "id must be an integer"
	if not isinstance(value, str):
		return "value must be a string"
	if type(expected_chg_ts) is not int:
		return "expected_chg_ts must be an integer"
	return task_id, value, expected_chg_ts

class _BoardServer(ThreadingHTTPServer):
	"""The listener, carrying the store and token every request needs."""
	daemon_threads = True
	def __init__(self, address, handler, csv_path: Path, token: str | None):
		super().__init__(address, handler)
		self.csv_path = csv_path
		self.token = token

class _BoardServerV6(_BoardServer):
	address_family = socket.AF_INET6

class _Handler(BaseHTTPRequestHandler):
	"""One request: authentication, routing, and the response the route sends."""
	protocol_version = "HTTP/1.1"
	server_version = "taskboard"
	routes = {
		"/": ("GET", "text/html; charset=utf-8", "index.html", "no-store"),
		"/board.js": ("GET", "text/javascript; charset=utf-8", "board.js", "no-cache"),
		"/board.css": ("GET", "text/css; charset=utf-8", "board.css", "no-cache"),
		"/api/tasks": ("GET", "application/json; charset=utf-8", None, "no-store"),
		"/api/due": ("POST", "application/json; charset=utf-8", None, "no-store"),
	}
	edit_error_kinds = {400: "bad-request", 404: "not-found", 409: "conflict"}
	def do_GET(self):
		self._dispatch("GET")
	def do_POST(self):
		self._dispatch("POST")
	def do_HEAD(self):
		self._dispatch("HEAD")
	def do_PUT(self):
		self._dispatch("PUT")
	def do_DELETE(self):
		self._dispatch("DELETE")
	def do_PATCH(self):
		self._dispatch("PATCH")
	def do_OPTIONS(self):
		self._dispatch("OPTIONS")
	def log_message(self, format, *args):
		"""R31: no access lines; a page polled every two seconds would out-log the store."""
	def _dispatch(self, method: str):
		parsed = urlsplit(self.path)
		route = parsed.path
		query = parse_qs(parsed.query)
		try:
			if not self._accepted(route, query):
				return
			spec = self.routes.get(route)
			if spec is None:
				self._error(404, "not-found", f"no such route: {route}")
				return
			allowed, content_type, asset, cache = spec
			if method != allowed:
				self._error(405, "method-not-allowed", f"{method} is not allowed on {route}", {"Allow": allowed})
				return
			if asset is not None:
				self._send_asset(asset, content_type, cache)
			elif route == "/api/tasks":
				self._send_tasks()
			else:
				self._receive_edit()
		except (BrokenPipeError, ConnectionResetError):
			self.close_connection = True
		except Exception:
			traceback.print_exc()
			self._try_error(500, "internal", "the server failed to handle the request")
	def _accepted(self, route: str, query: dict) -> bool:
		"""R24: no token on loopback; otherwise a cookie, bootstrapped once from the URL."""
		token = self.server.token
		if token is None:
			return True
		supplied = query.get("token", [""])[0]
		if route == "/" and self.command == "GET" and hmac.compare_digest(supplied, token):
			cookie = f"taskboard={token}; HttpOnly; SameSite=Strict; Path=/"
			self._send(303, b"", None, {"Location": "/", "Set-Cookie": cookie})
			return False
		jar = _cookie_token(self.headers.get("Cookie"))
		if jar is not None and hmac.compare_digest(jar, token):
			return True
		self._error(401, "unauthorized", "a valid token is required")
		return False
	def _send_asset(self, name: str, content_type: str, cache: str):
		try:
			body = (_here / name).read_bytes()
		except OSError:
			self._error(500, "internal", "the page assets are missing")
			return
		self._send(200, body, content_type, {"Cache-Control": cache})
	def _send_tasks(self):
		csv_path = self.server.csv_path
		try:
			state = csv_path.stat()
		except OSError:
			self._error(503, "store-missing", f"the task store {csv_path} does not exist")
			return
		etag = _etag(state)
		if self.headers.get("If-None-Match") == etag:
			self._send(304, b"", None, {"ETag": etag, "Cache-Control": "no-store"})
			return
		try:
			payload = read_board(csv_path, int(time.time()))
		except StoreMissing as error:
			self._error(503, "store-missing", str(error))
			return
		self._send_json(200, payload, {"ETag": etag})
	def _receive_edit(self):
		"""R9–R12, R25: one due-date edit, refused or applied through `set_due`."""
		if not _is_json(self.headers.get("Content-Type")):
			self._error(415, "unsupported-media-type", "POST /api/due needs application/json")
			return
		origin = self.headers.get("Origin")
		if origin is not None and origin != f"http://{self.headers.get('Host', '')}":
			self._error(403, "forbidden", "the request came from another origin")
			return
		body = self._read_body()
		if body is None:
			return
		request = _parse_edit(body)
		if isinstance(request, str):
			self._error(400, "bad-request", request)
			return
		task_id, value, expected_chg_ts = request
		now = int(time.time())
		try:
			row = taskupdate.read_task(self.server.csv_path, task_id)
		except OSError as error:
			self._reject(task_id, value, str(error), 409)
			return
		current_due_ts = stored_due_ts(row)
		try:
			new_due_ts = parse_due_edit(value, current_due_ts, now)
		except InvalidDue as error:
			self._reject(task_id, value, str(error), 400)
			return
		try:
			payload = set_due(self.server.csv_path, task_id, new_due_ts, expected_chg_ts, now)
		except TaskNotFound as error:
			self._reject(task_id, value, str(error), 404)
			return
		except TaskChanged as error:
			self._log(f"rejected #{task_id} {value!r}: the task changed since the page read it")
			self._error(409, "conflict", "the task changed since the page read it", extra={"task": error.current})
			return
		except (StoreMissing, TaskNotOpen) as error:
			self._reject(task_id, value, str(error), 409)
			return
		self._log(f"edit #{task_id}: due {taskupdate.fmt_due(current_due_ts)} -> {taskupdate.fmt_due(new_due_ts)} from {value!r}")
		self._send_json(200, payload)
	def _read_body(self) -> bytes | None:
		try:
			length = int(self.headers.get("Content-Length") or "")
		except ValueError:
			self._error(400, "bad-request", "a Content-Length header is required")
			return None
		if length < 0:
			self._error(400, "bad-request", "a Content-Length header is required")
			return None
		if length > _MAX_BODY:
			self._error(413, "payload-too-large", f"a request body is limited to {_MAX_BODY} bytes", close=True)
			return None
		return self.rfile.read(length)
	def _reject(self, task_id: int, value: str, message: str, code: int):
		self._log(f"rejected #{task_id} {value!r}: {message}")
		self._error(code, self.edit_error_kinds[code], message)
	def _log(self, message: str):
		print(f"taskboard: {message}", flush=True)
	def _try_error(self, code: int, kind: str, message: str):
		try:
			self._error(code, kind, message)
		except OSError:
			self.close_connection = True
	def _error(self, code: int, kind: str, message: str, headers=None, extra=None, close=False):
		body = {"error": kind, "message": message}
		if extra:
			body.update(extra)
		self._send_json(code, body, headers, close)
	def _send_json(self, code: int, payload: dict, headers=None, close=False):
		body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
		all_headers = {"Cache-Control": "no-store"}
		all_headers.update(headers or {})
		self._send(code, body, "application/json; charset=utf-8", all_headers, close)
	def _send(self, code: int, body: bytes, content_type: str | None, headers=None, close=False):
		if close:
			self.close_connection = True
		self.send_response(code)
		for name, value in _SECURITY_HEADERS.items():
			self.send_header(name, value)
		for name, value in (headers or {}).items():
			self.send_header(name, value)
		if close:
			self.send_header("Connection", "close")
		if content_type is not None:
			self.send_header("Content-Type", content_type)
		if code != 304:
			self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		if self.command != "HEAD" and code != 304 and body:
			self.wfile.write(body)

if __name__ == "__main__":
	sys.exit(main())
