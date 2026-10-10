"""
Request parsing - the core path.

read_request has to handle what a browser and the game's own client actually
send. That is the bar here: a plain GET, a POST with a JSON body, a body that
arrives across several TCP segments, and a websocket upgrade where the first
frame may share a segment with the headers.

Each test names the dumb_http behaviour it is protecting, because the goal is
that dumb_http's callers can move over unchanged.
"""

import unittest,harness
from xhttp import xhttp
from xhttp._ import err

class ParseCoreTest(unittest.TestCase):
	"""What ordinary traffic does."""

	def parse(self,raw,drip = None,**kwargs):
		client = harness.ScriptedSocket(raw,drip = drip)
		return client,xhttp.read_request(client,("127.0.0.1",5000),**kwargs)

	def test_plain_get(self):
		client,req = self.parse(b"GET /main.html HTTP/1.1\r\nHost: x\r\n\r\n")
		self.assertEqual(req["method"],"GET")
		self.assertEqual(req["target"],"/main.html")
		self.assertEqual(req["protocol"],"HTTP/1.1")
		self.assertEqual(req["headers"]["host"],"x")
		self.assertEqual(bytes(req["payload"]),b"")

	def test_query_string_survives_in_target(self):
		# ed66b138 shipped a bug where self.path was overwritten with a parsed
		# value, losing the query string and breaking websocket login with a
		# KeyError on every connection. The raw target must stay intact and
		# query parsing must be the caller's business.
		_,req = self.parse(b"GET /chat_async?key=abc123 HTTP/1.1\r\nHost: x\r\n\r\n")
		self.assertEqual(req["target"],"/chat_async?key=abc123")
		self.assertIn("key=abc123",req["target"])

	def test_header_names_lowercased_values_stripped(self):
		_,req = self.parse(b"GET / HTTP/1.1\r\nX-Real-IP: 10.0.0.5\r\nAccept-Encoding: gzip\r\n\r\n")
		self.assertEqual(req["headers"]["x-real-ip"],"10.0.0.5")
		self.assertEqual(req["headers"]["accept-encoding"],"gzip")

	def test_post_body_read_exactly(self):
		body = b'{"command":"auth"}'
		_,req = self.parse(b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: %d\r\n\r\n" % len(body) + body)
		self.assertEqual(bytes(req["payload"]),body)

	def test_post_body_arriving_in_pieces(self):
		# A body split across segments is ordinary, not an edge case: recv
		# short-reads by design.
		body = b'{"command":"auth"}'
		_,req = self.parse(b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: %d\r\n\r\n" % len(body) + body,drip = 3)
		self.assertEqual(bytes(req["payload"]),body)

	def test_large_post_body(self):
		payload = b"x" * 200000
		raw = b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: %d\r\n\r\n" % len(payload) + payload
		_,req = self.parse(raw,drip = 8192)
		self.assertEqual(bytes(req["payload"]),payload)

	def test_duplicate_header_rejected(self):
		# dumb_http silently kept the last value. xhttp rejects. Duplicates are
		# a smuggling vector, so rejecting is the right call; this test pins it.
		with self.assertRaises(err.HTTPHeaderDuplicate):
			self.parse(b"GET / HTTP/1.1\r\nA: 1\r\nA: 2\r\n\r\n")

	def test_client_addr_carried_through(self):
		_,req = self.parse(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
		self.assertEqual(req["client_addr"],("127.0.0.1",5000))

class ParseWebsocketBoundaryTest(unittest.TestCase):
	"""
	The one framing constraint that decides how simple parsing can be:
	bytes after the header block must still be reachable.

	notes/xhttp.md decision 6: "Never read past \\r\\n\\r\\n." A websocket
	client's first frame can arrive in the same segment as the request, so if
	the header loop over-reads, those bytes have to come back out somehow.
	"""

	def test_leftover_bytes_after_headers_are_not_lost(self):
		raw = b"GET /chat_async?key=k HTTP/1.1\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n\x81\x85\x00\x00\x00\x00HELLO"
		client = harness.ScriptedSocket(raw)
		req = xhttp.read_request(client,("127.0.0.1",5000))
		leftover = None
		for candidate in ("leftover","rest","buffer","remaining","payload"):
			if candidate in req:
				leftover = req[candidate]
				break
		self.assertIsNotNone(
			leftover,
			"No key in the returned dict carries the bytes read past the header "
			"block. read_request consumed %d of %d bytes and %r is all the caller "
			"gets back, so a websocket frame that shared the segment with the "
			"request is destroyed. Either read up to the terminator, or return "
			"the remainder under one of these names." % (client.pos,len(raw),sorted(req.keys()))
		)
		self.assertIn(b"HELLO",bytes(leftover))

	def test_leftover_with_no_body_headers_at_all(self):
		# Same problem, no Content-Length to make it look handled. This is the
		# plain GET that dumb_http's handler sees for every page load.
		raw = b"GET / HTTP/1.1\r\nHost: x\r\n\r\nEXTRA"
		client = harness.ScriptedSocket(raw)
		req = xhttp.read_request(client,("127.0.0.1",5000))
		self.assertEqual(bytes(req["payload"]),b"", "a GET with no Content-Length has no body")
		leftover = None
		for candidate in ("leftover","rest","buffer","remaining"):
			if candidate in req:
				leftover = req[candidate]
				break
		self.assertIsNotNone(
			leftover,
			"bytes past the header block were read off the socket and dropped. "
			"Either stop reading at \\r\\n\\r\\n or hand the remainder back."
		)
		self.assertIn(b"EXTRA",bytes(leftover))

class ParseFramingTest(harness.HttpErrorAssertions,unittest.TestCase):
	"""
	Content-Length is a promise about how many bytes follow. Reading more than
	that is how request smuggling starts, and it also misreports the payload to
	the command layer.
	"""

	def test_payload_truncated_to_content_length(self):
		client = harness.ScriptedSocket(b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: 2\r\n\r\n" + b"A"*40)
		req = xhttp.read_request(client,("127.0.0.1",5000))
		self.assertEqual(
			bytes(req["payload"]),b"AA",
			"Content-Length is 2 but %d bytes were returned. Everything past the "
			"declared length belongs to the next request, not this one." % len(req["payload"])
		)

	def test_zero_content_length_means_no_body(self):
		client = harness.ScriptedSocket(b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: 0\r\n\r\nJUNKJUNK")
		req = xhttp.read_request(client,("127.0.0.1",5000))
		self.assertEqual(bytes(req["payload"]),b"")

	def test_incomplete_body_raises_http_error(self):
		# Peer closed early. Must be an HTTPError so the caller can answer 400
		# rather than crashing out of the handler.
		self.assert_http_error(
			xhttp.read_request,
			harness.ScriptedSocket(b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: 100\r\n\r\nshort"),
			("127.0.0.1",5000),
			expected = err.HTTPBodyIncomplete,
			msg = "A peer that hangs up mid-body is ordinary (a cancelled upload, "
		"a killed tab), and the caller needs to tell it apart from a server fault."
		)

	def test_negative_content_length_rejected(self):
		# -1 clears the "too big" check, then reaches recv() with a negative
		# buffersize, which is a ValueError from the socket layer rather than
		# an HTTPError. Either reject it or treat it as zero, but not let it
		# reach recv.
		self.assert_http_error(
			xhttp.read_request,
			harness.ScriptedSocket(b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: -1\r\n\r\n"),
			("127.0.0.1",5),
			expected = err.HTTPContentLengthBad,
			msg = "A negative length is nonsense and should be refused as a bad "
		"request. Left alone it reaches recv() with a negative buffersize, "
		"which raises ValueError from the socket layer instead."
		)

	def test_non_numeric_content_length_rejected(self):
		self.assert_http_error(
			xhttp.read_request,
			harness.ScriptedSocket(b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: banana\r\n\r\n"),
			("127.0.0.1",5),
			expected = err.HTTPContentLengthBad
		)

	def test_content_length_over_limit_rejected(self):
		self.assert_http_error(
			xhttp.read_request,
			harness.ScriptedSocket(b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: 999999999\r\n\r\n"),
			("127.0.0.1",5),
			expected = err.HTTPPayloadTooBig,
			max_content_len = 1000
		)

class ParseJsonTest(harness.HttpErrorAssertions,unittest.TestCase):
	"""
	read_json must signal invalid JSON as an HTTPError, not let
	json.JSONDecodeError escape. Callers need to distinguish bad requests
	from server faults.
	"""

	def test_invalid_json_raises_http_error(self):
		# Invalid JSON must be an HTTPError so caller can answer 400
		body = b"not json!!"
		self.assert_http_error(
			xhttp.read_json,
			harness.ScriptedSocket(b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: %d\r\n\r\n" % len(body) + body),
			("127.0.0.1",5000),
			expected = err.HTTPError,
			msg = "Invalid JSON must raise an HTTPError, not json.JSONDecodeError. "
			"Otherwise every malformed request becomes a 500 and the real fault "
			"is invisible in logs."
		)

	def test_valid_json_parsed(self):
		# Valid JSON should be parsed and returned in payload
		body = b'{"cmd":"test"}'
		req = xhttp.read_json(harness.ScriptedSocket(b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: %d\r\n\r\n" % len(body) + body),("127.0.0.1",5000))
		self.assertEqual(req["payload"],{"cmd":"test"})

	def test_empty_payload_rejected(self):
		# Empty body with Content-Length: 0 should be rejected as invalid JSON
		self.assert_http_error(
			xhttp.read_json,
			harness.ScriptedSocket(b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: 0\r\n\r\n"),
			("127.0.0.1",5000),
			expected = err.HTTPError,
			msg = "Empty payload is not valid JSON"
		)

class ParseTransferEncodingTest(harness.HttpErrorAssertions,unittest.TestCase):
	"""
	Chunked bodies are refused, so the check has to actually catch them.

	Only the exact lowercase string "chunked" is refused today. "Chunked",
	"CHUNKED" and "chunked, gzip" all pass, and the chunked body is then
	discarded while its bytes stay in the socket for whatever reads next.
	"""

	def assert_refused(self,raw):
		self.assert_http_error(
			xhttp.read_request,
			harness.ScriptedSocket(raw),
			("127.0.0.1",5000),
			expected = err.HTTPChunkedEncoding,
			msg = "Ignoring chunked framing and then leaving the body in the "
		"socket is the classic smuggling setup. The check has to be "
		"case-insensitive and list-aware, not an equality test."
		)

	def test_exact_chunked_refused(self):
		self.assert_refused(b"POST / HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nHELLO\r\n0\r\n\r\n")

	def test_chunked_capitalised_refused(self):
		self.assert_refused(b"POST / HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: Chunked\r\n\r\n5\r\nHELLO\r\n0\r\n\r\n")

	def test_chunked_uppercase_refused(self):
		self.assert_refused(b"POST / HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: CHUNKED\r\n\r\n5\r\nHELLO\r\n0\r\n\r\n")

	def test_chunked_in_a_list_refused(self):
		self.assert_refused(b"POST / HTTP/1.1\r\nHost: x\r\nTransfer-Encoding: chunked, gzip\r\n\r\n5\r\nHELLO\r\n0\r\n\r\n")

	def test_content_length_with_chunked_refused(self):
		# Both present is the ambiguous case that RFC 7230 says to refuse.
		self.assert_refused(b"POST / HTTP/1.1\r\nHost: x\r\nContent-Length: 4\r\nTransfer-Encoding: chunked\r\n\r\nabcd")

class ParseMalformedTest(harness.HttpErrorAssertions,unittest.TestCase):
	"""
	A malformed request must come back as an HTTPError. Anything else escapes
	the handler's error handling, and a client that sends one bad line takes
	the connection down with no response at all - trap T4.
	"""

	def test_header_line_without_colon(self):
		self.assert_http_error(
			xhttp.read_request,
			harness.ScriptedSocket(b"GET / HTTP/1.1\r\nX-Bad-Header\r\n\r\n"),
			("127.0.0.1",5),
			expected = err.HTTPHeaderInvalid,
			msg = "A header line with no colon currently raises a bare ValueError "
		"from tuple unpacking. Trivial to send, and it kills the handler "
		"with nothing sent back."
		)

	def test_empty_request(self):
		self.assert_http_error(
			xhttp.read_request,
			harness.ScriptedSocket(b""),
			("127.0.0.1",5),
			expected = err.HTTPHeaderInvalid,
			msg = "A peer that connects and says nothing must be refused cleanly."
		)

	def test_connection_closed_mid_headers(self):
		self.assert_http_error(
			xhttp.read_request,
			harness.ScriptedSocket(b"GET / HTTP/1.1\r\nHost: x\r\n"),
			("127.0.0.1",5),
			msg = "Hanging up mid-headers must not look like a valid request."
		)

	def test_request_line_with_one_token(self):
		self.assert_http_error(
			xhttp.read_request,
			harness.ScriptedSocket(b"GET\r\nHost: x\r\n\r\n"),
			("127.0.0.1",5),
			expected = err.HTTPRequestInvalid
		)

	def test_header_over_size_limit(self):
		raw = b"GET / HTTP/1.1\r\nX: " + b"a"*9000 + b"\r\n\r\n"
		self.assert_http_error(
			xhttp.read_request,
			harness.ScriptedSocket(raw),
			("127.0.0.1",5),
			expected = err.HTTPHeaderTooBig,
			max_header_len = 8192,
			msg = "An oversized header block must be refused as 431, not as a "
		"generic invalid-header error. Right now the size check only "
		"runs after a recv that has already blown the budget, and a "
		"block that never completes is reported as merely invalid."
		)

class ParseEdgeTest(harness.HttpErrorAssertions,unittest.TestCase):
	"""
	Needs a hand-crafted request. Real clients do not send these, so they are
	tracked rather than blocking. They become important once the core path is
	done.

	Run with `python3 dev/xhttp/test/run.py` to include, `--core` to skip.
	"""

	@harness.edge
	def test_bare_lf_line_endings(self):
		# Some very old clients and some proxies emit \n only.
		self.assert_http_error(
			xhttp.read_request,
			harness.ScriptedSocket(b"GET / HTTP/1.1\nHost: x\n\n"),
			("127.0.0.1",5),
			msg = "Bare-LF requests are either refused cleanly or accepted; today "
		"they fall out as invalid-header, which is at least an HTTPError."
		)

	@harness.edge
	def test_unsupported_http_version(self):
		# HTTP/9.9 is not a thing. Parser now raises HTTPHeaderVersion.
		self.assert_http_error(
			xhttp.read_request,
			harness.ScriptedSocket(b"GET / HTTP/9.9\r\nHost: x\r\n\r\n"),
			("127.0.0.1",5),
			expected = err.HTTPHeaderVersion,
			msg = "unknown HTTP versions should be refused at the parsing boundary"
		)

	@harness.edge
	def test_absolute_form_target(self):
		# Proxies send the whole URI in the request line.
		req = xhttp.read_request(harness.ScriptedSocket(b"GET http://elsewhere/x HTTP/1.1\r\nHost: x\r\n\r\n"),("127.0.0.1",5))
		self.assertEqual(req["target"],"http://elsewhere/x")

	@harness.edge
	def test_two_requests_in_one_segment(self):
		# Pipelining. Parser consumes both requests in a single read.
		# This test documents the current behavior.
		raw = b"GET /one HTTP/1.1\r\nHost: x\r\n\r\nGET /two HTTP/1.1\r\nHost: x\r\n\r\n"
		client = harness.ScriptedSocket(raw)
		req1 = xhttp.read_request(client,("127.0.0.1",5))
		self.assertEqual(req1["target"], "/one")
		# First call consumes both requests
		self.assertEqual(client.pos, len(raw), "both requests were consumed in first read")

	@harness.edge
	def test_path_traversal_target(self):
		# T7. Not exploitable until serve_file exists, but the target is
		# accepted verbatim, so nothing upstream is rejecting it.
		# Now: parser raises HTTPDoubleDotForbidden.
		self.assert_http_error(
			xhttp.read_request,
			harness.ScriptedSocket(b"GET /../../etc/passwd HTTP/1.1\r\nHost: x\r\n\r\n"),
			("127.0.0.1",5),
			expected = err.HTTPDoubleDotForbidden,
			msg = "traversal segments should be refused at the parsing boundary"
		)

	@harness.edge
	def test_obsolete_line_folding(self):
		# A continuation line starts with whitespace and has no colon.
		self.assert_http_error(
			xhttp.read_request,
			harness.ScriptedSocket(b"GET / HTTP/1.1\r\nX: a\r\n  b\r\n\r\n"),
			("127.0.0.1",5),
			msg = "RFC 7230 obs-fold. Obsolete, but it has no colon, so it hits the "
		"same unpacking path as a genuinely broken header."
		)

if __name__ == "__main__":
	unittest.main()
