"""
Shared plumbing for the xhttp test suite. Not a test file - imported by the
test_*.py modules next to it.

Two jobs:

1. Put `dev/` on sys.path so `from xhttp import xhttp` works, whatever
	directory the suite is launched from. xhttp.py does `from ._ import ...`,
	which only resolves when the library is imported as a package with
	`dev/xhttp/` beneath it — the same way `dev/xcsv/tests/test_xcsv.py` does it.
	`dev/` is a namespace package, so it needs no `__init__.py`.
2. Provide the fakes and probes the tests need, so each test file stays about
	HTTP behaviour and not about scaffolding.

Conventions used by the tests:

- `edge` marks a test that needs a hand-crafted or hostile request. Those are
	tracked but deliberately deprioritised until the core path is done, so
	`run.py --core` can skip them.
- `decision` marks a test that encodes a choice the human has not made yet.
	The test states the choice it assumes, in its docstring, so failing it is a
	prompt to rule rather than a mystery.
"""

import os,sys,socket,threading,time,unittest

HERE = os.path.dirname(os.path.abspath(__file__))
XHTTP_DIR = os.path.dirname(HERE)
DEV_DIR = os.path.dirname(XHTTP_DIR)
REPO_ROOT = os.path.dirname(DEV_DIR)

if DEV_DIR not in sys.path:
	sys.path.insert(0,DEV_DIR)

from xhttp import xhttp
from xhttp._ import helper
from xhttp._ import err

# --- preflight ------------------------------------------------------------

def preflight():
	"""
	Report the state of the library before any test runs.

	The single most important thing to know is whether the response path works
	at all, because when it does not every response test fails with the same
	NameError and the real causes get lost in the noise.
	"""
	findings = []
	try:
		helper.datetime_string()
	except Exception as e:
		findings.append("response path is dead: helper.datetime_string() raised %s: %s" % (type(e).__name__,e))
	try:
		xhttp.write_response(object(),200)
	except NameError as e:
		findings.append("xhttp.write_response raises %s before writing a single byte" % e)
	except Exception:
		pass
	return findings

# --- markers --------------------------------------------------------------

def edge(test):
	"""
	Needs a hand-crafted or hostile request.

	Tagged rather than skipped, so `run.py` runs everything by default and
	`run.py --core` leaves these out. The point of running them now is to make
	the backlog visible, not to fail the build on it.
	"""
	setattr(test,"xhttp_edge",True)
	return test

def decision(test):
	"""Encodes a choice the human has not ruled on yet."""
	setattr(test,"xhttp_decision",True)
	return test

def _is_tagged(test,kind):
	return getattr(test,"xhttp_" + kind,False)

# --- fake sockets ---------------------------------------------------------

class ScriptedSocket:
	"""
	A socket that replays a fixed byte script on recv() and records what was
	written to it.

	`drip` controls how bytes are handed over: as one lump, or in slices of the
	given size, which is how a body that arrives across several TCP segments
	gets simulated.
	"""

	def __init__(self,script,drip = None):
		self.script = script
		self.drip = drip
		self.pos = 0
		self.written = bytearray()
		self.send_calls = []
		self.sendall_calls = []
		self.closed = False

	def recv(self,n):
		if self.drip:
			n = min(n,self.drip)
		chunk = self.script[self.pos:self.pos+n]
		self.pos += len(chunk)
		return chunk

	def send(self,data):
		self.send_calls.append(len(data))
		self.written.extend(data)
		return len(data)

	def sendall(self,data):
		self.sendall_calls.append(len(data))
		self.written.extend(data)

	def close(self):
		self.closed = True

	def fileno(self):
		return -1 if self.closed else 0

class PartialSendSocket(ScriptedSocket):
	"""
	A socket that accepts only part of each write, the way a real one can when
	the send buffer is nearly full.

	`send` returns a short count. `sendall` is honoured in full. A writer that
	uses `send` and ignores the return value therefore drops the tail - which is
	trap T13, expressed as a test rather than a warning.
	"""

	def __init__(self,script = b"",chunk = 16):
		super().__init__(script)
		self.chunk = chunk

	def send(self,data):
		self.send_calls.append(len(data))
		take = min(len(data),self.chunk)
		self.written.extend(data[:take])
		return take

class ExplodingSocket(ScriptedSocket):
	"""
	Raises on write, the way a peer that vanished mid-response does.

	`error` picks which OS error the peer produces on write. The three are not
	interchangeable in practice: a peer that closes orderly gives
	BrokenPipeError, one that sends RST gives ConnectionResetError, one that
	aborts gives ConnectionAbortedError. All three mean "nobody is listening",
	so the write path has to survive all three - not just the one a
	socketpair.half_close() happens to produce.
	"""

	def __init__(self,script = b"",error = ConnectionResetError,message = "peer went away"):
		super().__init__(script)
		self.error = error
		self.message = message

	def send(self,data):
		self.send_calls.append(len(data))
		raise self.error(self.message)

	def sendall(self,data):
		# Recorded before raising, so a test can assert how many write attempts
		# were made - "did it try to write a body after the header write
		# already failed" is a question only the count can answer.
		self.sendall_calls.append(len(data))
		raise self.error(self.message)

# --- response inspection --------------------------------------------------

def parse_response(raw):
	"""
	Split a raw response into (status_line, headers, body).

	Handles both length-framed and close-framed bodies, because the difference
	is one of the open questions in notes/xhttp.md rather than something to
	assert on here.
	"""
	if not raw:
		return ("",{},b"")
	head,_,body = raw.partition(b"\r\n\r\n")
	lines = head.split(b"\r\n")
	status = lines[0].decode("latin-1") if lines else ""
	headers = {}
	for line in lines[1:]:
		if not line.strip():
			continue
		name,_,value = line.partition(b":")
		headers[name.decode("latin-1").strip().lower()] = value.decode("latin-1").strip()
	length = headers.get("content-length")
	if length is not None:
		try:
			body = body[:int(length)]
		except ValueError:
			pass
	return (status,headers,body)

def header_value(raw,name):
	_,headers,_ = parse_response(raw)
	return headers.get(name.lower())

def status_code(raw):
	status,_,_ = parse_response(raw)
	parts = status.split(" ")
	if len(parts) < 2:
		return None
	try:
		return int(parts[1])
	except ValueError:
		return None

# --- live server ----------------------------------------------------------

def free_port():
	s = socket.socket()
	s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
	s.bind(("127.0.0.1",0))
	port = s.getsockname()[1]
	s.close()
	return port

class LiveServer:
	"""
	xhttp.serve_forever on a real port, in a real thread.

	Bound on 127.0.0.1 only. Port 0 cannot be used: serve_forever does not
	report the port it ended up with, so the port is chosen in advance by
	free_port(). That is a small race and acceptable in tests.

	`handler` is called as handler(req, *handler_args) - serve_forever parses
	the request first and passes the parsed request dict, plus any extra
	handler_args. The req dict contains: client, client_addr, method, target,
	filepath, protocol, headers, payload, leftover.
	"""

	def __init__(self,handler,host = "127.0.0.1"):
		self.handler = handler
		self.host = host
		self.port = free_port()
		self.error = None
		self._thread = None
		self._started = threading.Event()

	def start(self):
		self._thread = threading.Thread(target = self._run,daemon = True)
		self._thread.start()
		self._started.wait(timeout = 2)
		return self

	def _run(self):
		try:
			xhttp.serve_forever((self.host,self.port),self.handler,(),None,True)
		except Exception as e:
			self.error = e
			self._started.set()

	def request(self,raw,timeout = 3.0):
		"""
		Send raw bytes, read until the response is complete or the timeout
		expires, and return everything received.

		Returning when the response is complete rather than when the peer
		close matters now that keep-alive is implemented: the server keeps the
		connection open, so waiting for a close waits out the whole timeout on
		every single request. Every response xhttp sends is length-framed
		(content-length is always written, 0 included), so a complete response
		is exactly headers + that many body bytes.

		Returns the raw response, or b"" if the server accepted nothing at all.
		"""
		deadline = time.time() + timeout
		s = socket.socket()
		s.settimeout(timeout)
		s.connect((self.host,self.port))
		s.sendall(raw)
		data = bytearray()
		try:
			while time.time() < deadline:
				s.settimeout(max(0.05,deadline - time.time()))
				chunk = s.recv(65536)
				if not chunk:
					break
				data.extend(chunk)
				if _response_complete(data):
					break
		except (socket.timeout,ConnectionResetError,BrokenPipeError):
			pass
		finally:
			s.close()
		return bytes(data)

	def get(self,target = "/",headers = (),timeout = 3.0):
		lines = ["GET %s HTTP/1.1" % target,"Host: 127.0.0.1"]
		lines.extend(headers)
		return self.request(("\r\n".join(lines) + "\r\n\r\n").encode(),timeout)

	def post_json(self,payload,target = "/",headers = (),timeout = 3.0):
		if isinstance(payload,str):
			payload = payload.encode()
		lines = ["POST %s HTTP/1.1" % target,"Host: 127.0.0.1","Content-Length: %d" % len(payload)]
		lines.extend(headers)
		lines.append("Content-Type: application/json")
		raw = ("\r\n".join(lines) + "\r\n\r\n").encode() + payload
		return self.request(raw,timeout)

	def stop(self):
		# serve_forever has no shutdown path; the thread is a daemon and the
		# process exit reclaims the port. Recorded as a gap, not worked around.
		pass

	def __enter__(self):
		return self.start()

	def __exit__(self,*exc):
		self.stop()
		return False

def wait_for(predicate,timeout = 2.0,interval = 0.02):
	"""Poll until predicate() is true. Returns whether it became true."""
	deadline = time.time() + timeout
	while time.time() < deadline:
		if predicate():
			return True
		time.sleep(interval)
	return predicate()

def _response_complete(data):
	"""
	True once `data` holds a whole length-framed response.

	False while the headers are still arriving, and false for a body that has
	not fully landed - so the caller can stop reading without truncating.
	A response with no readable content-length is never treated as complete,
	which leaves the caller's timeout to decide rather than cutting a body
	in half.
	"""
	head,sep,rest = bytes(data).partition(b"\r\n\r\n")
	if not sep:
		return False
	for line in head.split(b"\r\n")[1:]:
		name,_,value = line.partition(b":")
		if name.strip().lower() != b"content-length":
			continue
		try:
			length = int(value.strip())
		except ValueError:
			return False
		return len(rest) >= length
	return False

def open_fd_count():
	"""How many descriptors this process holds. Linux only, which is the target."""
	return len(os.listdir("/proc/self/fd"))

class HttpErrorAssertions:
	"""
	Mixin for tests that care *how* a request was refused, not just that it was.

	unittest reports an AssertionError as a failure and anything else as an
	error. A bare ValueError escaping read_request would therefore show up as
	an ERROR, which reads like a broken test rather than the defect it is. This
	converts every wrong-outcome into one clean failure carrying the reason.
	"""

	def assert_http_error(self,func,*args,expected = None,msg = None,**kwargs):
		"""
		Call func(*args, **kwargs) and require it to raise an HTTPError.

		`expected` narrows to a subclass, e.g. err.HTTPChunkedEncoding.
		`msg` says what the test is protecting, in the failure text.
		"""
		what = getattr(func,"__name__",repr(func))
		where = "%s should have refused this with %s" % (what,getattr(expected,"__name__","an HTTPError"))
		if msg:
			where += ". " + msg
		try:
			result = func(*args,**kwargs)
		except err.HTTPError as e:
			if expected is not None and not isinstance(e,expected):
				self.fail("%s, but raised %s instead. %s" % (where,type(e).__name__,e))
			return e
		except Exception as e:
			self.fail(
				"%s, but %s escaped instead: %s\n"
				"That is not an HTTPError, so a caller cannot tell a bad request from a "
				"broken server, and the error-to-response mapping has nothing to key on."
				% (where,type(e).__name__,e)
			)
		self.fail("%s, but it returned %r" % (where,result))
