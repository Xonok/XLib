"""
The listener, the per-connection wrapper, and the shape of a handler.

serve_forever and wrap_handler are the DONE-and-verified part of xhttp, so
these tests protect what notes/xhttp.md says already works rather than looking
for new ground. The ones that fail are regressions against that record, or
gaps the record does not mention.

The fd tests run against real socketpairs and count /proc/self/fd. They are
the only tests here that touch the real kernel interface, which is the point:
an fd leak is invisible to a mock.
"""

import os,socket,ssl,threading,time,unittest,contextlib,io,harness
from xhttp import xhttp
from xhttp._ import server

def open_fds():
	return len(os.listdir("/proc/self/fd"))

def response_head(raw):
	"""Just the status line and headers, for asserting on one of them."""
	return raw.split(b"\r\n\r\n")[0]

class ServeLiveTest(unittest.TestCase):
	"""A real socket, a real thread, a real request."""

	def test_get_gets_a_response(self):
		def handler(req, *args):
			xhttp.send_response(req["client"],200)
		with harness.LiveServer(handler) as server:
			raw = server.get("/main.html")
		self.assertEqual(harness.status_code(raw),200,"got %r" % raw)

	def test_post_body_reaches_the_handler(self):
		seen = {}
		def handler(req, *args):
			seen["payload"] = bytes(req["payload"])
			seen["method"] = req["method"]
			xhttp.send_response_full(req["client"],200,payload = b"ok")
		body = b'{"command":"auth","cname":"x"}'
		with harness.LiveServer(handler) as server:
			raw = server.post_json(body)
		self.assertEqual(seen.get("method"),"POST")
		self.assertEqual(seen.get("payload"),body)
		self.assertEqual(harness.status_code(raw),200)

	def test_several_requests_in_a_row(self):
		# The listener must keep going. One connection per request here: this
		# is about the listener surviving, not about reusing a connection.
		# Reusing one is ServeForeverKeepAliveTest, and it cannot be done from
		# here - LiveServer calls wrap_handler directly with a hardcoded 120
		# rather than going through serve_forever, so it would pass whatever
		# serve_forever did with max_requests.
		counts = []
		def handler(req, *args):
			counts.append(1)
			xhttp.send_response(req["client"],200)
		with harness.LiveServer(handler) as server:
			for _ in range(5):
				self.assertEqual(harness.status_code(server.get("/")),200)
		self.assertEqual(len(counts),5)

	def test_new_thread_returns_immediately(self):
		# serve_forever(new_thread=True) hands off and returns; the caller is
		# not left blocking on the accept loop.
		def handler(req, *args):
			pass
		start = time.time()
		promise = xhttp.serve_forever(("127.0.0.1",harness.free_port()),handler,(),None,True)
		self.assertLess(time.time() - start,1.0,"new_thread=True still blocked the caller")

	def test_bind_failure_is_reported_not_swallowed(self):
		"""
		A port clash has to reach the caller, not just the listener thread.

		dumb_http had await_startup() for this: bind on the listener thread,
		then raise the error back on the main thread, so main() never carries
		on believing the server started.

		xhttp's serve_forever(new_thread=True) returns the instant it hands off,
		and the bind then fails in a thread with nobody watching. There is no
		way to ask whether it worked.

		Checked two ways, because both halves have to hold: the background
		bind must actually fail (it does - SO_REUSEADDR does not permit a
		second listener on a listening port), and the caller must have some
		way to find out. The second is the one that currently fails.
		"""
		sock = socket.socket()
		sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
		sock.bind(("127.0.0.1",0))
		sock.listen(1)
		port = sock.getsockname()[1]

		failed = []
		def attempt():
			try:
				xhttp.serve_forever(("127.0.0.1",port),lambda req,*a: None,None,None,False)
			except OSError as e:
				failed.append(e)

		thread = threading.Thread(target = attempt,daemon = True)
		try:
			thread.start()
			thread.join(timeout = 2)
			self.assertFalse(
				thread.is_alive(),
				"the bind succeeded on an already-bound port; this test cannot "
				"tell a real clash from a broken fixture"
			)
			self.assertTrue(failed,"expected OSError from the clashing bind")
			self.assertTrue(
				hasattr(xhttp,"await_startup") or hasattr(xhttp,"serve_forever_blocking"),
				"The clash is reported to the listener thread and nowhere else. "
				"With new_thread=True, serve_forever returns before the bind is "
				"attempted, so main() cannot tell a running server from a dead "
				"one. notes/xhttp.md lists this as open; closing it needs either "
				"an await_startup equivalent or a blocking mode the caller runs "
				"on the main thread."
			)
		finally:
			sock.close()

class WrapHandlerTest(unittest.TestCase):
	"""wrap_handler's contract: contain everything, clean up after itself."""

	def _send_request(self, sock, close = True):
		"""
		Send a minimal valid HTTP request on the socket.

		`close` adds Connection: close. wrap_handler loops while the request
		allows keep-alive, so a bare HTTP/1.1 request leaves it waiting for a
		second one - and on a raw socketpair with no timeout, that waits
		forever. Tests about a single request say so explicitly rather than
		relying on the peer vanishing.
		"""
		suffix = b"Connection: close\r\n" if close else b""
		sock.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n" + suffix + b"\r\n")

	def test_handler_runs(self):
		calls = []
		a,b = socket.socketpair()
		try:
			self._send_request(b)
			xhttp.wrap_handler(lambda req,*a: calls.append(req["client_addr"]),(),None,a,("1.2.3.4",9))
		finally:
			b.close()
		self.assertEqual(calls,[("1.2.3.4",9)])

	def test_client_socket_is_closed_afterwards(self):
		"""
		Every connection must release its descriptor.

		nothing in wrap_handler closes `client`. A handler that keeps a
		reference - which lib/websocket.py does, for the life of the socket -
		leaks one fd per connection, and the process runs out after a few
		thousand requests with no error to show for it. This is trap T12 by a
		different route: dumb_http stranded an fd on an empty request, xhttp
		strands one on every request.
		"""
		held = []
		start = open_fds()
		try:
			for _ in range(30):
				a,b = socket.socketpair()
				self._send_request(b)
				xhttp.wrap_handler(lambda req,*a: held.append(req["client"]),(),None,a,("1.2.3.4",9))
				b.close()
			leaked = open_fds() - start
			self.assertLessEqual(
				leaked,2,
				"%d descriptors left open after 30 connections. wrap_handler "
				"never closes the client socket, so a handler that holds a "
				"reference - as the websocket does - leaks one per connection."
				% leaked
			)
		finally:
			for sock in held:
				try:
					sock.close()
				except OSError:
					pass

	def test_handler_exception_does_not_escape(self):
		# Stability: a bug in one handler must not take the thread or the
		# listener with it. This is the part T4 got right.
		a,b = socket.socketpair()
		try:
			self._send_request(b)
			xhttp.wrap_handler(
				lambda req,*a: (_ for _ in ()).throw(RuntimeError("boom")),
				(),None,a,("1.2.3.4",9),
			)
		finally:
			b.close()

	def test_connection_reset_is_swallowed(self):
		"""
		When peer closes connection before sending data, wrap_handler must not
		propagate an exception. The handler is never called (read_request fails
		first), but wrap_handler should contain the error.
		"""
		a,b = socket.socketpair()
		b.close()
		try:
			# Peer closed connection before sending data
			xhttp.wrap_handler(lambda req,*a: None,(),None,a,("1.2.3.4",9))
			# If we get here, no exception escaped - test passes
		except Exception as e:
			self.fail(f"wrap_handler let exception escape: {e}")
		finally:
			try:
				a.close()
			except OSError:
				pass

	def test_dead_handler_answers_the_client(self):
		"""
		Trap T4: a handler that dies leaves the client with nothing.

		dumb_http's wrap_error held no handler instance, so the signature could
		not carry one - that is why the notes record this as unfixed. The
		client sees a connection that opens and closes with zero bytes, which
		browsers report as an empty page or a network error.

		Whatever the shape of the fix, the observable requirement is the same:
		a client gets *some* valid response. The test only checks that it is
		not silence, so it does not constrain how the 500 is produced.
		"""
		a,b = socket.socketpair()
		b.settimeout(2)
		try:
			self._send_request(b) # send on b, wrap_handler reads from a
			xhttp.wrap_handler(
				lambda req,*a: (_ for _ in ()).throw(RuntimeError("boom")),
				(),None,a,("1.2.3.4",9),
			)
			try:
				received = b.recv(65536)
			except socket.timeout:
				received = None
			self.assertTrue(
				received,
				"The client got nothing at all. A handler that raises should "
				"still produce a response - a 500 is enough - so the failure is "
				"visible to the user instead of being an empty page."
			)
		finally:
			b.close()
			try:
				a.close()
			except OSError:
				pass

	def _status_for(self,raw):
		"""The status wrap_handler sends for a request the parser refuses."""
		a,b = socket.socketpair()
		b.settimeout(2)
		handled = []
		try:
			b.sendall(raw)
			xhttp.wrap_handler(lambda req,*a: handled.append(req),(),None,a,("1.2.3.4",9))
			self.assertEqual(handled,[],"the handler ran for a request the parser should have refused")
			return harness.status_code(b.recv(65536))
		finally:
			b.close()
			try:
				a.close()
			except OSError:
				pass

	@harness.edge
	def test_unsupported_version_answers_505(self):
		# read_request raises HTTPHeaderVersion. What the client sees is the
		# mapping in wrap_handler, which the parse-level test cannot prove.
		self.assertEqual(
			self._status_for(b"GET / HTTP/9.9\r\nHost: x\r\n\r\n"),
			505
		)

	@harness.edge
	def test_double_dot_answers_400(self):
		# The parser refuses the decoded traversal; the client is told why.
		self.assertEqual(
			self._status_for(b"GET /../../etc/passwd HTTP/1.1\r\nHost: x\r\n\r\n"),
			400
		)

class WrapHandlerEdgeTest(unittest.TestCase):
	"""
	Needs a specific socket-level failure. `python3 dev/xhttp/test/run.py` to
	include, `--core` to skip.
	"""

	@harness.edge
	def test_ssl_error_is_swallowed(self):
		# A client that speaks plaintext to a TLS port. Must not print a
		# traceback per attempt - notes/xhttp.md records the pass clauses for
		# exactly this, and the listener must not die on it.
		#
		# This used to pass `None` as the ssl_context, so it tested plain HTTP
		# and proved nothing. The handshake is what raises here, so the context
		# has to be a real one.
		certificate,private_key = harness.test_ssl_keys()
		context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
		context.load_cert_chain(certificate,private_key)
		a,b = socket.socketpair()
		try:
			b.sendall(b"GET / HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
			xhttp.wrap_handler(lambda req,*a: None,(),context,a,("1.2.3.4",9))
		finally:
			b.close()
			try:
				a.close()
			except OSError:
				pass

	@harness.edge
	def test_accepted_socket_has_no_timeout(self):
		"""
		notes/xhttp.md decision 3: accepted sockets inherit no timeout, so a
		peer that connects and stalls blocks a thread forever.

		Keep-alive turned this from a latent risk into the normal path. Every
		idle keep-alive connection sits in read_request's recv with nothing to
		return, and thread-per-connection means each idle peer costs a whole
		thread until it goes away. So this now *demonstrates* the block rather
		than reading gettimeout() and hoping - the assertion is that
		wrap_handler is still running after the request is fully answered,
		with the peer neither sending nor closing.

		The recorded defence - "adding one is the only defence" - is not
		implemented here: serve_forever sets 60s on accepted sockets, so
		production is bounded, but wrap_handler on its own is not.
		"""
		a,b = socket.socketpair()
		returned = []
		try:
			b.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
			thread = threading.Thread(
				target = lambda: (
					xhttp.wrap_handler(lambda req,*a: None,(),None,a,("1.2.3.4",9)),
					returned.append(1),
				),
				daemon = True,
			)
			thread.start()
			# The handler is a no-op, so the request is answered instantly.
			# If wrap_handler comes back it did so by not waiting; if it is
			# still alive it is parked in recv holding the thread.
			gave_up = harness.wait_for(lambda: bool(returned),timeout = 1.0)
			thread.join(timeout = 1.0)
			self.assertFalse(
				gave_up,
				"wrap_handler returned even though the peer neither sent another "
				"request nor closed. If that is intended, the idle-connection "
				"behaviour needs recording; if not, keep-alive is looping on a "
				"socket with no timeout and no way out."
			)
			self.assertIsNone(a.gettimeout(),"socketpair fds do not carry a timeout either")
		finally:
			# Close the peer so the parked recv sees EOF and the thread unwinds.
			b.close()
			thread.join(timeout = 2.0)
			try:
				a.close()
			except OSError:
				pass

class ServeForeverKeepAliveTest(unittest.TestCase):
	"""
	Keep-alive as a browser uses it: several requests down one connection.

	There was no test for this, and the file said otherwise - the comment in
	ServeLiveTest.test_several_requests_in_a_row pointed at a
	`WrapHandlerKeepAliveTest` that was never written. It was never written
	because of how a keep-alive test is reached here: harness.LiveServer does
	not call serve_forever. It re-implements the accept loop and calls
	wrap_handler directly with a hardcoded 120, so a keep-alive test written
	against LiveServer passes no matter what serve_forever does.

	And serve_forever passed no max_requests at all, so wrap_handler took its
	own default of 1: every connection served one request and closed, while the
	responses advertised HTTP/1.1 and never said `Connection: close`. A browser
	reused the connection, the server closed without reading the request
	already in flight, and that file was silently lost. Traveller's page load
	died on whichever image happened to be in flight, which is why it looked
	like one bad file.

	These tests therefore start the real serve_forever on a real port. Nothing
	stops the listener afterwards; low-level threads are not joined at
	interpreter exit, so a leaked one costs a port and nothing else.
	"""

	def _serve(self,handler,max_requests = None):
		"""Start the real serve_forever on a real port. Returns the port."""
		port = harness.free_port()
		if max_requests is None:
			promise = xhttp.serve_forever(("127.0.0.1",port),handler,(),None,True)
		else:
			# The root wrapper does not forward max_requests, so a listener
			# with a short budget has to be started through the internal it
			# wraps. Worth knowing: it is not reachable from the public API.
			promise = server.serve_forever(("127.0.0.1",port),handler,(),None,True,None,max_requests)
		xhttp.await_startup(promise)
		return port

	def _read_one(self,s):
		"""
		One length-framed response. b"" means the peer went away without one.

		Which of the two it is depends on timing. A server that closes with
		the request still unread in its receive buffer gets answered by the
		kernel with RST rather than FIN, so the same defect arrives as an
		orderly close or as ConnectionResetError from one run to the next.
		Both are the same defect, so both have to land as one assertion rather
		than as a failure that alternates with an error.
		"""
		buf = bytearray()
		while True:
			try:
				chunk = s.recv(65536)
			except (ConnectionResetError,BrokenPipeError):
				return bytes(buf)
			if not chunk:
				return bytes(buf)
			buf.extend(chunk)
			if harness._response_complete(buf):
				return bytes(buf)

	def _two_on_one_connection(self,port,headers = ()):
		"""
		Two requests down one socket, both answers read back.

		A lost second request has to come back as b"" - the server going away
		with nothing written - rather than as a timeout, or the test cannot
		tell the defect this class exists for from a slow machine.
		"""
		s = socket.create_connection(("127.0.0.1",port))
		s.settimeout(3.0)
		out = []
		try:
			for target in ("/one","/two"):
				lines = ["GET %s HTTP/1.1" % target,"Host: 127.0.0.1"]
				lines.extend(headers)
				try:
					s.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
				except (ConnectionResetError,BrokenPipeError):
					out.append(b"")
					break
				out.append(self._read_one(s))
		finally:
			s.close()
		return out

	@staticmethod
	def _handler(req, *args):
		xhttp.send_response_full(req["client"],200,payload = b"ok")

	def test_two_requests_on_one_connection_both_answered(self):
		"""The regression: serve_forever must keep a connection alive."""
		port = self._serve(self._handler)
		first,second = self._two_on_one_connection(port)
		self.assertEqual(harness.status_code(first),200,"first request: %r" % first)
		self.assertEqual(
			harness.status_code(second),200,
			"serve_forever answered the first request and closed instead of "
			"reading the second. A browser reuses connections, so the second "
			"request is lost rather than refused - empty second response is %r" % second
		)

	def test_last_response_says_connection_close(self):
		"""
		The response before the socket closes has to say so.

		Without the header the client is told, by omission, that the
		connection is still good - and anything it writes next is lost. That is
		the same defect as above, only arriving on the last request instead of
		the first.
		"""
		port = self._serve(self._handler,max_requests = 2)
		first,second = self._two_on_one_connection(port)
		self.assertEqual(harness.status_code(first),200,"first request: %r" % first)
		self.assertNotIn(
			b"connection: close",response_head(first).lower(),
			"the server is staying open for another request, so it must not "
			"claim otherwise"
		)
		self.assertIn(
			b"connection: close",response_head(second).lower(),
			"this is the last response before the socket closes, so it has to "
			"say so. Second response was %r" % second
		)

	def test_client_asked_to_close_is_told_so(self):
		"""`Connection: close` in the request is echoed in the response."""
		port = self._serve(self._handler)
		first,second = self._two_on_one_connection(port,headers = ("Connection: close",))
		self.assertEqual(harness.status_code(first),200,"first request: %r" % first)
		self.assertIn(
			b"connection: close",response_head(first).lower(),
			"the client asked to close. Echoing it is what RFC 9112 asks for, "
			"and it costs nothing. First response was %r" % first
		)
		self.assertEqual(second,b"","the client asked to close, so nothing follows")

	def test_peer_disconnect_between_requests_is_quiet(self):
		"""
		A browser dropping an idle keep-alive connection is ordinary traffic.

		Once keep-alive is on, every idle connection the browser closes ends in
		EOF, which read_request reports as HTTPHeaderInvalid. Printing a
		traceback for it fills the log with the normal case and buries the real
		faults - the same reason TimeoutError is already swallowed beside it.
		"""
		a,b = socket.socketpair()
		b.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
		b.close()
		printed = io.StringIO()
		try:
			with contextlib.redirect_stdout(printed):
				xhttp.wrap_handler(self._handler,(),None,a,("127.0.0.1",5),120)
		finally:
			a.close()
		self.assertEqual(
			printed.getvalue(),"",
			"a peer closing between keep-alive requests was reported as an "
			"error. HTTPHeaderInvalid is raised only when the peer closed "
			"before sending a complete request - malformed input with a "
			"terminator is HTTPRequestInvalid, and a bad version is "
			"HTTPHeaderVersion, both of which are still reported. Got: %r" % printed.getvalue()
		)

if __name__ == "__main__":
	unittest.main()
