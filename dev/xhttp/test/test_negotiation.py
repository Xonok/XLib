"""
What the content-coding negotiation has to guarantee, once it exists.

**Complements `ContentNegotiationTest` in `test_response.py`**, which pins the
defect: xhttp gzips whatever the client asked for, and six tests are red on
purpose (epi `BFNRBG7`). This file pins the two things that class does not,
and which the fix would otherwise be free to get wrong:

1. **Outside a request, the server's own choice stands.** The ruling, 2026-10-21:
   the negotiation is a *filter* on the server's `compress` decision, so a
   direct caller of the public API still gets what `compress=True` asked for.
   Nothing inside the library reaches that case - the only cross-thread send
   is a bodiless 101 in the websocket receiver, and Space-Traveller sends
   inline in the request thread - so it reaches only a caller who owns the
   socket, and the library should not silently override that caller's
   instruction.

2. **The filter is recomputed for every request on a connection.** A keep-alive
   connection carries several requests, each with its own `Accept-Encoding`. A
   filter that latched - the most likely mistake in a thread-local
   implementation, where the state is set once and not cleared - would let the
   first request's answer stand for the rest.

**Three of the four pass today, and one is red.** The first two are guards, not
defect markers: the defect is already pinned by the six in `test_response.py`,
and these two pass today and must still pass after the fix - they are there to
catch an implementer who reads "no request" as "no gzip", and who reads "the
caller said compress=False" as "the caller said nothing".

The differential one also passes today. It holds whatever the negotiation does
and only bites if the filter latches across a keep-alive connection.

**The fourth is red, on purpose**, and it is the one acceptance test the six
cannot give: that two requests on the SAME connection, with different headers,
get different answers. The six each use a fresh connection, so nothing in the
suite says the negotiation happens per request rather than per connection.

So the acceptance set for the fix is **seven red tests in xhttp**: the six, and
this one.

**The requests are sent one at a time, each after the previous answer is
read.** That is the pattern a browser uses, and it is deliberate: two requests
in one segment take a different path through `read_request`, and that path is
broken in a way this file does not want to depend on. See
`test_pipelining.py`.

The implementation is the human's. Ruled 2026-10-21: *"updating anything in
xhttp except the tests is human work."*
"""

import socket,threading,unittest,gzip,harness
from xhttp import xhttp

PAYLOAD = b"hello" * 100 # compresses enough that gzip is smaller

def _read_response(sock):
	"""
	One response off a socket: the header block, then exactly as many body
	bytes as content-length says.

	Reading the body by its declared length is the point - the body may be
	compressed, so it cannot be found by looking for a delimiter.
	"""
	head = b""
	while b"\r\n\r\n" not in head:
		chunk = sock.recv(4096)
		if not chunk:
			break
		head += chunk
	head,_,rest = head.partition(b"\r\n\r\n")
	length = 0
	for line in head.split(b"\r\n")[1:]:
		name,_,value = line.partition(b":")
		if name.strip().lower() == b"content-length":
			length = int(value.strip())
	while len(rest) < length:
		chunk = sock.recv(4096)
		if not chunk:
			break
		rest += chunk
	return head + b"\r\n\r\n" + rest[:length]

class OutsideARequestTest(unittest.TestCase):
	"""
	No request means no client statement to filter against.

	The server's own `compress` flag is the base decision, and the negotiation
	only ever removes gzip from it.
	"""

	def test_outside_a_request_the_servers_own_choice_stands(self):
		"""
		The ruling, 2026-10-21.

		A direct caller owns the socket and passed `compress=True`. There is no
		`Accept-Encoding` to consult, so there is nothing to filter against and
		the server's own decision stands: the body goes out compressed.

		This passes today and must still pass after the fix. It is the guard
		against an implementer who reads "no request" as "no gzip" - which
		would silently change what `compress=True` means for every direct
		caller of the public API.
		"""
		payload = b"x" * 20000
		s = harness.ScriptedSocket(b"")
		xhttp.send_response_full(s,200,payload = payload)
		_,headers,body = harness.parse_response(bytes(s.written))
		self.assertEqual(headers.get("content-encoding"),"gzip",
			"outside a request the server's own choice stands")
		self.assertEqual(gzip.decompress(body),payload,"and the body round-trips")
		self.assertEqual(int(headers["content-length"]),len(body),
			"and the length describes the bytes actually sent")

	def test_outside_a_request_the_caller_can_still_refuse(self):
		"""`compress=False` is the caller's instruction too, and it wins."""
		payload = b"x" * 20000
		s = harness.ScriptedSocket(b"")
		xhttp.send_response_full(s,200,payload = payload,compress = False)
		_,headers,body = harness.parse_response(bytes(s.written))
		self.assertIsNone(headers.get("content-encoding"),
			"the caller said not to compress and it did not")
		self.assertEqual(body,payload,"and the body is the payload")
		self.assertEqual(int(headers["content-length"]),len(body),
			"and the length describes the bytes actually sent")

class PerRequestTest(unittest.TestCase):
	"""
	A connection carries several requests, and each has its own header.

	`wrap_handler` reads one request, answers it, and reads the next on the
	same thread. So whatever state the negotiation keeps is per-thread, and a
	state that is set once and not cleared would answer the second request with
	the first request's header.
	"""

	def _answers(self,accept_encodings):
		"""
		Several requests on ONE connection, each with its own Accept-Encoding.

		Each request is written after the previous answer has been read, so
		each one arrives on its own. The server runs on its own thread because
		`wrap_handler` is synchronous and blocks on the next request once it
		has answered the first.

		Returns the raw response bytes, one per request.
		"""
		def handler(req, *args):
			xhttp.send_response_full(req["client"],200,payload = PAYLOAD,compress = True)
		a,b = socket.socketpair()
		finished = []
		def serve():
			try:
				xhttp.wrap_handler(handler,(),None,a,("127.0.0.1",5),len(accept_encodings))
			finally:
				finished.append(True)
				a.close()
		thread = threading.Thread(target = serve)
		thread.daemon = True
		thread.start()
		answers = []
		b.settimeout(5)
		for accept_encoding in accept_encodings:
			header = "" if accept_encoding is None else "Accept-Encoding: %s\r\n" % accept_encoding
			b.sendall(("GET / HTTP/1.1\r\nHost: x\r\n" + header + "\r\n").encode())
			answers.append(_read_response(b))
		thread.join(timeout = 5)
		b.close()
		return answers

	def test_the_second_request_is_answered_as_if_it_were_the_only_one(self):
		"""
		The filter is per request, not per connection.

		Two connections. The first asks for gzip and then sends no
		`Accept-Encoding`; the second sends no `Accept-Encoding` at all. The
		second request of the first connection has to be answered exactly as
		the only request of the second connection is - because the request
		itself is the same, and what the client sent on the *previous* request
		is not evidence about this one.

		The shape is differential on purpose. A filter that latched would
		answer the first connection's second request from the earlier header
		and the two would differ; an unlatched one answers them the same. So
		the test holds whatever the negotiation does and only bites on a leak.
		"""
		after_a_gzip_request = self._answers(["gzip",None])
		after_a_silent_request = self._answers([None])
		self.assertEqual(len(after_a_gzip_request),2,"both requests were answered")
		self.assertEqual(len(after_a_silent_request),1,"the one request was answered")
		self.assertEqual(
			harness.header_value(after_a_gzip_request[1],"content-encoding"),
			harness.header_value(after_a_silent_request[0],"content-encoding"),
			"the second request must be answered as if it were the only one on "
			"the connection, and not from the first request's header")
		self.assertEqual(
			harness.header_value(after_a_gzip_request[1],"content-length"),
			harness.header_value(after_a_silent_request[0],"content-length"),
			"and the length has to agree with whichever body went out")

	def test_each_request_on_a_connection_gets_its_own_answer(self):
		"""
		Two requests, two different headers, two different answers.

		Today every request is gzipped, so this cannot distinguish a correct
		negotiation from a missing one - the six in `test_response.py` are what
		pin that. What it does pin is that the two requests are answered
		*differently* once the negotiation exists, so an implementation that
		answers every request from the first one cannot pass.
		"""
		answers = self._answers(["gzip","identity"])
		self.assertEqual(len(answers),2,"both requests were answered")
		first = harness.header_value(answers[0],"content-encoding")
		second = harness.header_value(answers[1],"content-encoding")
		self.assertNotEqual(
			first,second,
			"a client that asked for gzip and a client that asked for identity "
			"cannot get the same answer, so the filter cannot be answering "
			"every request from the first one")

if __name__ == "__main__":
	unittest.main()
