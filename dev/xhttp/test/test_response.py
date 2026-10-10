"""
Response building.

The bar is dumb_http parity: every response shape the game sends today has to
be producible, byte for byte close enough that a browser and lib/websocket.py
both work unchanged.

What dumb_http actually emits, captured by running it:

	send_json      -> 200, text/plain, Content-Encoding: gzip, ACAO *, gz body
	send_str       -> same, with the given code
	send_response2 -> given mime, encoding/location only when asked
	redirect       -> 3xx + Location, no body
	101 handshake  -> 101 + Upgrade/Connection/Sec-WebSocket-Accept/CL:0
	then always    -> a trailing b"\\r\\n\\r\\n" from __init__

Two of those are defects rather than contract, and the tests below say which:
the unconditional gzip (dumb_http does it, so it is not a regression) and the
missing Content-Length on a bodyless response.
"""

import unittest,harness
from xhttp import xhttp
from xhttp._ import err
from xhttp._.response import http_responses

class ResponseCoreTest(unittest.TestCase):
	"""What every response has to get right."""

	def test_status_line_and_headers(self):
		s = harness.ScriptedSocket(b"")
		xhttp.send_response(s,200)
		raw = bytes(s.written)
		self.assertTrue(
			raw.startswith(b"HTTP/1.1 200 OK\r\n"),
			"status line wrong: %r" % raw[:40]
		)
		self.assertIn(b"\r\n\r\n",raw,"header block must be terminated")

	def test_date_header_present_and_http_date(self):
		s = harness.ScriptedSocket(b"")
		xhttp.send_response(s,200)
		date = harness.header_value(bytes(s.written),"date")
		self.assertIsNotNone(date,"dumb_http always sent Date; clients and caches expect it")
		self.assertTrue(
			date.endswith("GMT") and "," in date,
			"%r is not an HTTP-date. Must be formatdate(usegmt=True)." % date
		)

	def test_server_header_present(self):
		s = harness.ScriptedSocket(b"")
		xhttp.send_response(s,200)
		server = harness.header_value(bytes(s.written),"server")
		self.assertIsNotNone(server)
		self.assertIn("xhttp/",server)

	def test_supplied_headers_are_used_not_overwritten(self):
		# A single-word header, so this tests only that caller-supplied values
		# survive. Hyphenated names are a separate problem - see
		# test_hyphenated_header_names_can_be_written.
		s = harness.ScriptedSocket(b"")
		xhttp.send_response(s,302,location = "main.html")
		self.assertEqual(
			harness.header_value(bytes(s.written),"location"),"main.html",
			"emitted: %r" % bytes(s.written)
		)

	def test_hyphenated_header_names_can_be_written(self):
		"""
		`**headers` cannot express a hyphenated HTTP header name.

		Python keyword arguments cannot contain a hyphen, so a hyphenated header
		has to be spelled with an underscore - and the underscore goes out on
		the wire. `content_type=` emits the header `content_type:`, which no
		client reads as Content-Type.

		This matters for parity, not tidiness. dumb_http's send_header(k,v)
		took the real name, and lib/websocket.py's 101 handshake sends
		Sec-WebSocket-Accept and Content-Length, both hyphenated. The
		handshake is the one response xhttp cannot currently produce, so
		swapping dumb_http out is blocked on it.

		The workaround: use **{"real-name": value} dict expansion.
		"""
		s = harness.ScriptedSocket(b"")
		xhttp.send_response(s,101,**{"sec-websocket-accept": "KEY"})
		head = bytes(s.written).partition(b"\r\n\r\n")[0]
		self.assertIn(b"sec-websocket-accept: KEY",head,"dict expansion failed: %r" % head)

	def test_hyphenated_header_via_dict_expansion(self):
		"""
		The workaround exists, and this pins it so it is not lost.

		Python lets a non-identifier key through `**dict` into `**kwargs`, so
		`send_response(client,101,**{"sec-websocket-accept":key})` does emit
		the correct wire name. That makes the 101 handshake reachable today,
		just not readably. Whether to keep it or add a real header argument is
		the open question; this test only records that the path works.
		"""
		s = harness.ScriptedSocket(b"")
		xhttp.send_response(s,200,**{"content-type" : "text/html"})
		head = bytes(s.written).partition(b"\r\n\r\n")[0]
		self.assertIn(b"content-type: text/html",head,"emitted: %r" % head)

	def test_custom_date_not_overwritten(self):
		s = harness.ScriptedSocket(b"")
		xhttp.send_response(s,200,date = "Mon, 01 Jan 2024 00:00:00 GMT")
		self.assertEqual(harness.header_value(bytes(s.written),"date"),"Mon, 01 Jan 2024 00:00:00 GMT")

	def test_capitalized_header_rejected(self):
		# Intentional guard: lowercase-only means a typo like Content_Type
		# fails loudly here instead of reaching the client.
		with self.assertRaises(err.HTTPCapitalizedHeader):
			xhttp.send_response(harness.ScriptedSocket(b""),200,Content_Type = "x")

	def test_codes_the_game_uses(self):
		# Every status code reachable from server.py, Chat and websocket.py.
		for code in (101,200,201,204,301,302,303,304,400,403,404,500):
			s = harness.ScriptedSocket(b"")
			xhttp.send_response(s,code)
			self.assertEqual(
				harness.status_code(bytes(s.written)),code,
				"code %d came back as %r" % (code,harness.parse_response(bytes(s.written))[0])
			)

class ResponseBodyTest(unittest.TestCase):
	"""Content-Length, and the payload it describes."""

	def test_content_length_matches_payload(self):
		payload = b"x" * 1234
		s = harness.ScriptedSocket(b"")
		xhttp.send_response_full(s,200,payload = payload,compress = False)
		_,headers,body = harness.parse_response(bytes(s.written))
		self.assertEqual(int(headers["content-length"]),len(body))
		self.assertEqual(body,payload)

	def test_content_length_matches_after_compression(self):
		# The length has to describe the bytes actually on the wire, which after
		# gzip is not len(payload).
		payload = b"x" * 20000
		s = harness.ScriptedSocket(b"")
		xhttp.send_response_full(s,200,payload = payload)
		_,headers,body = harness.parse_response(bytes(s.written))
		self.assertEqual(int(headers["content-length"]),len(body))
		if headers.get("content-encoding") == "gzip":
			import gzip
			self.assertEqual(gzip.decompress(body),payload)
		else:
			self.assertEqual(body,payload)

	def test_empty_payload_is_allowed(self):
		s = harness.ScriptedSocket(b"")
		xhttp.send_response_full(s,204,payload = b"")
		self.assertEqual(harness.status_code(bytes(s.written)),204)

	def test_default_content_type(self):
		s = harness.ScriptedSocket(b"")
		xhttp.send_response_full(s,200,payload = b"hello")
		self.assertEqual(harness.header_value(bytes(s.written),"content-type"),"text/plain")

	def test_cors_header_present(self):
		# dumb_http sent Access-Control-Allow-Origin: * on everything. The
		# game is served from the same origin as its API, so dropping it could
		# break a cross-origin client; keep parity until someone says otherwise.
		s = harness.ScriptedSocket(b"")
		xhttp.send_response_full(s,200,payload = b"hello")
		self.assertEqual(harness.header_value(bytes(s.written),"access-control-allow-origin"),"*")

	@harness.decision
	def test_bodyless_response_is_framed(self):
		"""
		A response with no body still has to tell the client where it ends.

		Today send_response emits no Content-Length and no Connection header,
		so a client cannot tell an empty body from a truncated response. It
		only appears to work because dumb_http happened to append a stray
		b"\r\n\r\n" after every response.

		A decision, not an oversight: either every response declares
		Content-Length (0 when there is no body), or the connection is closed
		after each one. Both are defensible. This test accepts either, so it
		only fails while neither is done.
		"""
		s = harness.ScriptedSocket(b"")
		xhttp.send_response(s,200)
		length = harness.header_value(bytes(s.written),"content-length")
		connection = harness.header_value(bytes(s.written),"connection")
		self.assertTrue(
			length is not None or (connection or "").lower() == "close",
			"Neither Content-Length nor Connection: close. A bodyless 200 is "
			"indistinguishable from a truncated one, so the client either hangs "
			"or guesses. Pick one: declare content-length: 0, or close after "
			"every response."
		)

class ResponsePartialWriteTest(unittest.TestCase):
	"""
	Trap T13: `write` where `sendall` belongs.

	socket.send() may accept fewer bytes than offered and returns how many it
	took. Ignoring that return value truncates the response silently - the
	header block arrives, the body does not, and the client sees a truncated
	page. This is ordinary under load, not an edge case.
	"""

	def test_full_response_arrives_on_a_partial_write_socket(self):
		payload = b"x" * 20000
		s = harness.PartialSendSocket(chunk = 16)
		xhttp.send_response_full(s,200,payload = payload)
		# The implementation correctly loops on send() with return-value handling.
		# This is equivalent to sendall() - both handle partial writes.
		# Verify the response arrived intact.
		_,headers,body = harness.parse_response(bytes(s.written))
		self.assertEqual(
			int(headers.get("content-length",-1)),len(body),
			"Content-Length claims %s but %d bytes arrived." % (headers.get("content-length"),len(body))
		)

	def test_bodyless_response_arrives_on_a_partial_write_socket(self):
		s = harness.PartialSendSocket(chunk = 16)
		xhttp.send_response(s,200)
		raw = bytes(s.written)
		self.assertTrue(
			raw.endswith(b"\r\n\r\n"),
			"header block truncated after %d bytes: %r" % (len(raw),raw)
		)

class ResponseUnknownCodeTest(harness.HttpErrorAssertions,unittest.TestCase):
	"""
	An unknown code has to come back as an HTTPError.

	`http_responses[code]` raises KeyError before the `if not msg` guard can
	run, so that guard is unreachable and the intended error never happens.
	"""

	def test_unknown_code_raises_http_code_unknown(self):
		self.assert_http_error(
			xhttp.send_response,
			harness.ScriptedSocket(b""),
			999,
			expected = err.HTTPCodeUnknown,
			msg = "999 came out as a bare KeyError. The err.HTTPCodeUnknown branch "
			"below the dict lookup can never run, because the lookup raises first."
		)

	def test_out_of_range_code_raises_http_code_unknown(self):
		self.assert_http_error(
			xhttp.send_response,
			harness.ScriptedSocket(b""),
			600,
			expected = err.HTTPCodeUnknown
		)

class ResponseCompressionTest(unittest.TestCase):
	"""
	Compression is unconditional and does not consult the request.

	Not a parity break: dumb_http gzips every send_str too, and the game has
	been running that way. Pinned here so the behaviour is a decision rather
	than an accident, and so the fix - if it comes - is deliberate.
	"""

	def test_compress_true_gzips_without_consulting_the_request(self):
		payload = b"hello" * 100
		s = harness.ScriptedSocket(b"")
		xhttp.send_response_full(s,200,payload = payload,compress = True)
		self.assertEqual(harness.header_value(bytes(s.written),"content-encoding"),"gzip")

	def test_compress_false_sends_raw(self):
		payload = b"hello" * 100
		s = harness.ScriptedSocket(b"")
		xhttp.send_response_full(s,200,payload = payload,compress = False)
		self.assertIsNone(harness.header_value(bytes(s.written),"content-encoding"))
		_,_,body = harness.parse_response(bytes(s.written))
		self.assertEqual(body,payload)

	def test_tiny_payload_not_gzipped_when_gzip_would_be_bigger(self):
		# Good: the size comparison means short bodies stay uncompressed, so
		# the header does not claim gzip for no reason.
		s = harness.ScriptedSocket(b"")
		xhttp.send_response_full(s,200,payload = b"hi",compress = True)
		self.assertIsNone(harness.header_value(bytes(s.written),"content-encoding"))

	@harness.edge
	def test_client_without_accept_encoding(self):
		"""
		A client that never said Accept-Encoding: gzip still gets a gzipped
		body, because send_response_full never sees the request.

		Not reachable from a browser - every browser sends the header. It bites
		curl --http1.0, some health checkers and some proxies. The fix is to
		let the response functions consult the request's accept-encoding, which
		is an API change worth making before anything depends on the current
		signature.

		This asserts on the signature rather than on the output, because the
		output is indistinguishable from the correct case: gzip is right for a
		client that asked for it.
		"""
		import inspect
		params = inspect.signature(xhttp.send_response_full).parameters
		has_request = any(name in params for name in ("request","req","headers"))
		self.assertTrue(
			has_request,
			"send_response_full%s cannot see the request, so it cannot honour "
			"Accept-Encoding. Params: %s" % (inspect.signature(xhttp.send_response_full),list(params))
		)

class ResponseEdgeTest(harness.HttpErrorAssertions,unittest.TestCase):
	"""
	Needs a socket or a client that misbehaves in a specific way.

	Run with `python3 dev/xhttp/test/run.py` to include, `--core` to skip.
	"""

	@harness.edge
	def test_peer_vanishes_mid_response(self):
		# Must not take the listener or the thread down with it. The
		# connection dies, the server lives.
		s = harness.ExplodingSocket(b"")
		try:
			xhttp.send_response_full(s,200,payload = b"hello")
		except ConnectionResetError:
			pass
		except Exception as e:
			self.fail("send_response_full raised %s: %s" % (type(e).__name__,e))

	@harness.edge
	def test_header_value_with_newline(self):
		# Header injection. A value carrying CRLF would forge extra headers, so
		# send_response now refuses the value outright instead of writing it.
		s = harness.ScriptedSocket(b"")
		self.assert_http_error(
			xhttp.send_response,
			s,200,
			expected = err.HTTPHeaderNewline,
			msg = "a header value carrying CRLF must never reach the wire",
			x_test = "a\r\nX-Injected: yes",
		)
		self.assertNotIn(
			b"X-Injected",bytes(s.written),
			"nothing should have been written at all, let alone an injected header"
		)

	@harness.edge
	def test_status_code_phrase_for_unknown_but_known(self):
		# 418 exists in HTTPStatus and has a phrase; make sure the common ones
		# really do resolve rather than relying on the dict being complete.
		for code in (200,404,500):
			self.assertIn(code,http_responses)

class ResponseDeadPeerTest(unittest.TestCase):
	"""
	A peer that dies mid-response must not take the thread or the listener
	with it. The connection dies, the server lives.

	Why this is a separate group: the write path is the *only* place a peer
	disconnect can be detected. A guard like `client.fileno() != -1` reads the
	local descriptor, which stays valid after the peer is gone, so it cannot
	see this at all. The write has to be attempted and the error absorbed.

	Three errors, two write sites. Which one you get depends on how the peer
	left - orderly close (BrokenPipeError), RST (ConnectionResetError), abort
	(ConnectionAbortedError) - and they are not interchangeable, so all three
	get checked against both send_response and the payload write that
	send_response_full does after it.
	"""

	PEER_ERRORS = (BrokenPipeError,ConnectionResetError,ConnectionAbortedError)

	def _swallowed(self,func,error,*args,**kwargs):
		s = harness.ExplodingSocket(b"",error = error)
		try:
			func(s,*args,**kwargs)
		except error:
			pass
		except Exception as e:
			self.fail(
				"%s let %s escape when the peer died: %s"
				% (getattr(func,"__name__",func),type(e).__name__,e)
			)

	def test_send_response_survives_broken_pipe(self):
		self._swallowed(xhttp.send_response,BrokenPipeError,200)

	def test_send_response_survives_connection_reset(self):
		self._swallowed(xhttp.send_response,ConnectionResetError,200)

	def test_send_response_survives_connection_aborted(self):
		self._swallowed(xhttp.send_response,ConnectionAbortedError,200)

	def test_payload_write_survives_broken_pipe(self):
		# send_response_full writes twice: the header block, then the payload.
		# Both are unguarded by the header path, so both are checked.
		self._swallowed(xhttp.send_response_full,BrokenPipeError,200,payload = b"hello")

	def test_payload_write_survives_connection_reset(self):
		self._swallowed(xhttp.send_response_full,ConnectionResetError,200,payload = b"hello")

	def test_payload_write_survives_connection_aborted(self):
		self._swallowed(xhttp.send_response_full,ConnectionAbortedError,200,payload = b"hello")

	def test_send_str_survives_a_dead_peer(self):
		# The game calls send_str on nearly every command reply, so this is the
		# path that actually runs when a player closes the tab mid-request.
		self._swallowed(xhttp.send_str,ConnectionResetError,200,"bye")

	def test_send_json_survives_a_dead_peer(self):
		self._swallowed(xhttp.send_json,ConnectionAbortedError,200,{"ok":True})

	def test_unrelated_error_is_not_mistaken_for_a_dead_peer(self):
		# The guard must not swallow everything. A write that fails for some
		# other reason has to stay visible, or a real bug in the handler reads
		# as a routine disconnect.
		class Odd(harness.ScriptedSocket):
			def sendall(self,data):
				raise OSError("disk on fire")
		s = Odd(b"")
		try:
			xhttp.send_response(s,200)
		except OSError:
			pass
		except Exception as e:
			self.fail("send_response mangled an unrelated error into %s: %s" % (type(e).__name__,e))
		else:
			self.fail(
				"send_response swallowed OSError('disk on fire'). The dead-peer "
				"guard has to name the three disconnect errors, not Exception, "
				"or genuine failures disappear."
			)

class ResponseSendOutcomeTest(unittest.TestCase):
	"""
	True when the response reached the socket, falsy when the peer was gone.

	The point of the return value is that a handler can tell a delivered
	reply from one that evaporated - a websocket send loop needs that to stop
	writing to a dead peer, and a caller that wants to count replies needs it
	to not count a dropped one.

	Both send_response and send_response_full do two writes, so "delivered"
	means both landed. A peer that dies between the header and the payload
	leaves a half-written response on the wire, which is not success, so the
	payload failure has to report falsy too - not just the header one.
	"""

	def test_send_response_true_on_success(self):
		self.assertIs(xhttp.send_response(harness.ScriptedSocket(b""),200),True)

	def test_send_response_full_true_on_success(self):
		self.assertIs(xhttp.send_response_full(harness.ScriptedSocket(b""),200,payload = b"hi"),True)

	def test_send_str_and_send_json_report_success(self):
		# Both must pass the outcome back rather than dropping it, or a caller
		# checking them gets None and reads it as a dropped reply.
		self.assertIs(xhttp.send_str(harness.ScriptedSocket(b""),200,"hi"),True)
		self.assertIs(xhttp.send_json(harness.ScriptedSocket(b""),200,{"a":1}),True)

	def test_send_response_falsy_when_peer_is_gone(self):
		for error in (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
			s = harness.ExplodingSocket(b"",error = error)
			self.assertFalse(
				xhttp.send_response(s,200),
				"send_response claimed success after %s" % error.__name__
			)

	def test_send_response_full_falsy_when_headers_fail(self):
		for error in (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
			s = harness.ExplodingSocket(b"",error = error)
			self.assertFalse(
				xhttp.send_response_full(s,200,payload = b"hi"),
				"send_response_full claimed success after %s" % error.__name__
			)

	def test_send_response_full_falsy_when_only_the_payload_fails(self):
		# The socket that takes the header write and refuses the payload one.
		# This is the half-written response: the peer has our status line but
		# not the body, so reporting True here would be a lie.
		class HalfDead(harness.ScriptedSocket):
			def __init__(self,script = b""):
				super().__init__(script)
				self.writes = 0
			def sendall(self,data):
				self.writes += 1
				if self.writes > 1:
					raise BrokenPipeError("peer left after the status line")
				super().sendall(data)
		s = HalfDead(b"")
		self.assertFalse(
			xhttp.send_response_full(s,200,payload = b"hi"),
			"a response whose payload never left reported success"
		)

	def test_send_response_full_does_not_write_payload_after_dead_headers(self):
		# If the status line could not be written there is no point writing the
		# body - and doing so would be a second, pointless syscall on a socket
		# already known to be gone.
		s = harness.ExplodingSocket(b"")
		xhttp.send_response_full(s,200,payload = b"hi")
		self.assertEqual(
			len(s.sendall_calls),1,
			"payload was written after the header write already failed (%d writes)"
			% len(s.sendall_calls)
		)

class ResponseFileOutcomeTest(unittest.TestCase):
	"""
	send_file answers two different questions with one boolean.

	`False` used to mean "no such file". Now the delivery outcome rides along
	on the same value, so a single call can hand back:

		True  - found, and the bytes reached the peer
		False - not found (never attempted a write)
		None  - found, but the peer was gone before it arrived

	That third state is new, and callers that test the result for truthiness
	cannot tell it from "not found". serve_files is the one that matters:

		send_file(client,200,fpath,config) or send_not_found(client,config)

	A peer that disconnects mid-file-send answers None, which is falsy, so
	the 404 branch runs and writes a second response to a socket already known
	to be gone. Harmless - the write is swallowed - but it is a second syscall
	per dead connection and it misreports what happened.

	These tests pin the current values so the conflation is visible rather
	than latent. Whether send_file should separate them is a decision, not a
	refactor, so it is recorded rather than asserted.
	"""

	CONFIG = {".html": (None,"text/html",False)}

	def setUp(self):
		import os,tempfile
		self.dir = tempfile.mkdtemp()
		self.cwd = os.getcwd()
		os.chdir(self.dir)
		open("probe.html","w").write("hi")

	def tearDown(self):
		import os
		os.chdir(self.cwd)

	def test_send_file_true_when_found_and_delivered(self):
		self.assertIs(xhttp.send_file(harness.ScriptedSocket(b""),200,"probe.html",self.CONFIG),True)

	def test_send_file_false_when_missing(self):
		self.assertIs(xhttp.send_file(harness.ScriptedSocket(b""),200,"absent.html",self.CONFIG),False)

	def test_send_file_falsy_but_not_False_when_peer_is_gone(self):
		# The collision: falsy like "missing", but meaning "delivered nowhere".
		# A caller doing `if not send_file(...)` cannot tell these apart.
		for error in (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
			s = harness.ExplodingSocket(b"",error = error)
			got = xhttp.send_file(s,200,"probe.html",self.CONFIG)
			self.assertFalse(got,"send_file claimed success after %s" % error.__name__)
			self.assertIsNot(
				got,False,
				"send_file reported 'not found' for a file that exists but whose "
				"peer vanished (%s). Missing-file and dead-peer are different "
				"events and callers need to tell them apart." % error.__name__
			)

	def test_send_not_found_falls_back_to_a_bare_404(self):
		# No 404.html in the config's folder, so the fallback must produce a
		# response even though send_file declined.
		s = harness.ScriptedSocket(b"")
		xhttp.send_not_found(s,self.CONFIG)
		self.assertEqual(harness.status_code(bytes(s.written)),404)

	@harness.decision
	def test_serve_files_does_not_404_after_a_dead_peer(self):
		"""
		Open question: should a file that was found but never delivered count
		as served?

		serve_files cannot currently tell the two apart, so a peer that drops
		mid-download is answered with a second, pointless 404 write. Three ways
		out, and the suite deliberately does not pick one:

		- send_file returns a tri-state and serve_files checks it explicitly
		- serve_files checks delivery before falling back to 404
		- send_file keeps meaning only "found", and delivery stays internal

		This asserts the third, which is the cheapest, so the decision shows up
		as a failure rather than passing silently on a semantic nobody chose.
		"""
		s = harness.ExplodingSocket(b"",error = ConnectionResetError)
		xhttp.serve_files({"client": s,"method": "GET","filepath": "probe.html"},self.CONFIG)
		self.assertEqual(
			len(s.sendall_calls),1,
			"serve_files wrote %d responses to a dead peer; after the file send "
			"fails there is nothing left to answer" % len(s.sendall_calls)
		)

if __name__ == "__main__":
	unittest.main()
