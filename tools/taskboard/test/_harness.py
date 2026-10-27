"""Shared fixture for the taskboard suite: a private store and a live server.

The spec pins the command and its startup line but not a server factory, so the
HTTP tests start the real process and read the URL it prints. The pure and
store tests import the module directly. `load_board` turns a missing module
into one clear assertion failure per test instead of an import error that
stops the runner before it reports anything.
"""
import contextlib,csv,io,json,os,re,signal,socket,subprocess,sys,tempfile,threading,time,urllib.parse
from http.client import HTTPConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "tools" / "taskboard" / "taskboard.py"
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

from tools.taskview import taskupdate

URL_RE = re.compile(r"https?://[^\s]+")
PAYLOAD_KEYS = {"id", "title", "due_ts", "due_date", "due_label", "category", "tags", "chg_ts"}

def load_board():
	"""The implementation module, with a missing file reported as a test failure."""
	try:
		from tools.taskboard import taskboard
	except ImportError as error:
		raise AssertionError(f"tools/taskboard/taskboard.py is not implemented yet: {error}") from error
	return taskboard

def seed_store(path, task_id=1, title="task", status="open", due_ts=None, chg_ts=1000, category="", tags="", importance="", description=""):
	"""Append one row to `path`, quietly, through the real writer."""
	path = Path(path)
	path.parent.mkdir(parents=True, exist_ok=True)
	with contextlib.redirect_stdout(io.StringIO()):
		taskupdate.append_row(path, task_id, status, title, due_ts, chg_ts, category, tags, importance, description)
	return path

class Store:
	"""A temporary task store, so no test can touch the real one."""
	def __init__(self):
		self._folder = tempfile.TemporaryDirectory(prefix="taskboard-test-")
		self.dir = Path(self._folder.name)
		self.csv = self.dir / "tasks.csv"
	def __enter__(self):
		return self
	def __exit__(self, *exc):
		self.close()
	def close(self):
		self._folder.cleanup()
	def add(self, task_id=1, title="task", status="open", due_ts=None, chg_ts=1000, category="", tags="", importance="", description=""):
		return seed_store(self.csv, task_id, title, status, due_ts, chg_ts, category, tags, importance, description)
	def rows(self):
		"""The data rows, header and comments excluded."""
		if not self.csv.exists():
			return []
		with self.csv.open("r", encoding="utf-8") as handle:
			return [row for row in csv.reader(handle) if row and not row[0].startswith("//") and row[0] != "id"]
	def last_row(self, task_id):
		rows = [row for row in self.rows() if row and row[0] == str(task_id)]
		return rows[-1] if rows else None
	def read_task(self, task_id):
		return taskupdate.read_task(self.csv, task_id)
	def fingerprint(self):
		state = self.csv.stat()
		return (state.st_mtime_ns, state.st_size, self.csv.read_bytes())
	def names(self):
		return sorted(path.name for path in self.dir.iterdir())

class Response:
	"""One HTTP response, read whole."""
	def __init__(self, status, reason, headers, body):
		self.status = status
		self.reason = reason
		self.headers = headers
		self.body = body
	def header(self, name):
		for key, value in self.headers:
			if key.lower() == name.lower():
				return value
		return None
	def json(self):
		return json.loads(self.body.decode("utf-8"))

def request(url, method="GET", body=None, headers=None):
	parts = urllib.parse.urlsplit(url)
	connection = HTTPConnection(parts.hostname, parts.port or 80, timeout=5)
	path = parts.path or "/"
	if parts.query:
		path += "?" + parts.query
	try:
		connection.request(method, path, body=body, headers=headers or {})
		response = connection.getresponse()
		return Response(response.status, response.reason, response.getheaders(), response.read())
	finally:
		connection.close()

def get(server, path, headers=None):
	return request(server.base + path, headers=headers)

def post_json(server, path, payload, headers=None):
	body = json.dumps(payload).encode("utf-8")
	all_headers = {"Content-Type": "application/json"}
	all_headers.update(headers or {})
	return request(server.base + path, "POST", body, all_headers)

def due_payload(task_id, value, chg_ts):
	return {"id": task_id, "value": value, "expected_chg_ts": chg_ts}

def cookie(response):
	header = response.header("Set-Cookie")
	if not header:
		return None
	return header.split(";", 1)[0].strip()

class Server:
	"""A running `taskboard.py`, its output collected line by line."""
	def __init__(self, process, url, stdout_lines, stderr_lines):
		self.process = process
		self.url = url
		parts = urllib.parse.urlsplit(url)
		self.base = f"{parts.scheme}://{parts.netloc}"
		self.stdout_lines = stdout_lines
		self.stderr_lines = stderr_lines
	def startup(self):
		"""The line that carries the startup URL, wherever it was printed."""
		for line in self.stdout_lines + self.stderr_lines:
			if URL_RE.search(line):
				return line
		return ""
	def stop(self, sig=signal.SIGINT):
		if self.process.poll() is None:
			self.process.send_signal(sig)
		try:
			return self.process.wait(timeout=5)
		except subprocess.TimeoutExpired:
			self.process.kill()
			return self.process.wait()
	def output(self):
		return "".join(self.stdout_lines) + "".join(self.stderr_lines)
	def __enter__(self):
		return self
	def __exit__(self, *exc):
		self.stop()

def _collect(stream, lines):
	for line in stream:
		lines.append(line)

def start_with_args(args, env=None, timeout=10):
	"""Start the command and wait for the URL on its first output line."""
	command = [sys.executable, str(SERVER)] + [str(arg) for arg in args]
	environment = os.environ.copy()
	environment.pop("TASKVIEW_CSV", None)
	environment.pop("TASKVIEW_DATA_DIR", None)
	for key, value in (env or {}).items():
		if value is None:
			environment.pop(key, None)
		else:
			environment[key] = value
	process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment)
	stdout_lines, stderr_lines = [], []
	threading.Thread(target=_collect, args=(process.stdout, stdout_lines), daemon=True).start()
	threading.Thread(target=_collect, args=(process.stderr, stderr_lines), daemon=True).start()
	deadline = time.time() + timeout
	while time.time() < deadline:
		for line in stdout_lines + stderr_lines:
			match = URL_RE.search(line)
			if match:
				return Server(process, match.group(0), stdout_lines, stderr_lines)
		if process.poll() is not None:
			raise AssertionError(f"taskboard exited {process.returncode} before printing a URL: {''.join(stdout_lines)}{''.join(stderr_lines)}")
		time.sleep(0.01)
	process.kill()
	raise AssertionError(f"taskboard printed no URL within {timeout}s: {''.join(stdout_lines)}{''.join(stderr_lines)}")

def start_server(store, *args, host="127.0.0.1", port=0, token=None, env=None):
	command = ["--csv", str(store.csv), "--host", host, "--port", port]
	if token is not None:
		command += ["--token", token]
	command += list(args)
	return start_with_args(command, env)

def run_taskboard(*args, env=None, timeout=10):
	"""Run the command to completion; return (exit code, stdout, stderr)."""
	command = [sys.executable, str(SERVER)] + [str(arg) for arg in args]
	environment = os.environ.copy()
	environment.pop("TASKVIEW_CSV", None)
	environment.pop("TASKVIEW_DATA_DIR", None)
	for key, value in (env or {}).items():
		if value is None:
			environment.pop(key, None)
		else:
			environment[key] = value
	finished = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=timeout)
	return finished.returncode, finished.stdout, finished.stderr

def free_port():
	with socket.socket() as sock:
		sock.bind(("127.0.0.1", 0))
		return sock.getsockname()[1]
