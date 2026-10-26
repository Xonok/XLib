"""
HTTPS: serving it, and sending plain http:// to it.

TLS is not new in xhttp - SPEC decision 1 records the design (a plain listener,
one wrap per accepted connection, handshake in the worker thread) and
notes/xhttp.md lists "TLS request/response, with a self-signed cert" as
verified. What the suite never did was complete a handshake, so the first half
of this file does, with the throwaway certificate in fixtures/.

The second half is the redirect, restored from dumb_http's
`redirect_to_https`: a server whose whole job is to answer every request with
a redirect to the TLS site. Traveller used to run it beside the TLS listener
and dropped it with the old server. It cannot simply copy the old
implementation, because the old one assumed the standard ports - Traveller now
runs the game on 9200/9201, so the destination port has to be rewritten, not
just the scheme, and the query string has to survive.

The public front door is `serve_forever(..., redirect_from=http_port)`: one
parameter, the source port, with the destination always the listener's own
port. The formatting tests reach the internal `server.http_to_https` directly,
because that is where host, port and target become a Location and it is not
useful to start a TLS listener for each spelling; the last class tests the
public option end to end.
"""

import os,socket,ssl,unittest,harness
from xhttp import xhttp
from xhttp._ import server,err

CERTIFICATE,PRIVATE_KEY = harness.test_ssl_keys()

# Deliberately not 443: a redirect that forgets to rewrite the port would send
# the client back to the port it came from (or to whatever Host said), and a
# non-standard destination makes that visible in the Location.
HTTPS_PORT = 9443

# --- helpers --------------------------------------------------------------

def start_redirect_server(destination = HTTPS_PORT):
	"""Start server.http_to_https on a free port. Returns the port it listens on."""
	port = harness.free_port()
	promise = server.http_to_https(("127.0.0.1",port),destination,True)
	xhttp.await_startup(promise)
	return port

def request(target,host = None,method = "GET",protocol = "HTTP/1.1",body = b""):
	"""One raw request. `host=None` omits the header, as HTTP/1.0 may."""
	lines = ["%s %s %s" % (method,target,protocol)]
	if host is not None:
		lines.append("Host: " + host)
	if body:
		lines.append("Content-Length: %d" % len(body))
	return ("\r\n".join(lines) + "\r\n\r\n").encode("iso-8859-1") + body

def exchange(port,raw,timeout = 3.0):
	"""Send one raw request on a fresh connection and read one response."""
	s = socket.create_connection(("127.0.0.1",port),timeout = timeout)
	s.settimeout(timeout)
	data = bytearray()
	try:
		s.sendall(raw)
		while not harness._response_complete(data):
			chunk = s.recv(65536)
			if not chunk:
				break
			data.extend(chunk)
	finally:
		s.close()
	return bytes(data)

def tls_exchange(port,raw,timeout = 5.0):
	"""The same, over a real TLS handshake. The fixture cert is not verified."""
	context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
	context.check_hostname = False
	context.verify_mode = ssl.CERT_NONE
	s = socket.create_connection(("127.0.0.1",port),timeout = timeout)
	s.settimeout(timeout)
	tls = context.wrap_socket(s,server_hostname = "localhost")
	data = bytearray()
	try:
		tls.sendall(raw)
		while not harness._response_complete(data):
			chunk = tls.recv(65536)
			if not chunk:
				break
			data.extend(chunk)
	finally:
		tls.close()
	return bytes(data)

# --- the redirect server --------------------------------------------------

class HttpToHttpsTest(unittest.TestCase):
	"""Every request is answered with a redirect to the https destination."""

	def setUp(self):
		self.port = start_redirect_server()
		self.host = "127.0.0.1:%d" % self.port

	def test_get_is_redirected_to_the_https_port(self):
		raw = exchange(self.port,request("/main.html",host = self.host))
		self.assertEqual(harness.status_code(raw),308,"got %r" % raw)
		self.assertEqual(
			harness.header_value(raw,"location"),
			"https://127.0.0.1:%d/main.html" % HTTPS_PORT,
			"the redirect kept the http port, or lost the target. Got %r" % raw
		)

	def test_query_string_is_carried_over(self):
		"""
		The old redirect used urlparse(...).path, so `?v=2` was dropped.

		Traveller has no query on a page load today, but the redirect server
		answers every GET, and a lost query is invisible in a browser that
		gets the page anyway - the page just behaves as if the parameter was
		never sent. Percent-encoding is kept verbatim for the same reason: it
		is the client's bytes, and the https server decodes them the same way.
		"""
		raw = exchange(self.port,request("/main.html?v=2&name=a%20b",host = self.host))
		self.assertEqual(
			harness.header_value(raw,"location"),
			"https://127.0.0.1:%d/main.html?v=2&name=a%%20b" % HTTPS_PORT,
			"got %r" % raw
		)

	def test_host_without_a_port_gets_the_destination_port(self):
		raw = exchange(self.port,request("/",host = "example.com"))
		self.assertEqual(
			harness.header_value(raw,"location"),
			"https://example.com:%d/" % HTTPS_PORT,
			"got %r" % raw
		)

	def test_ipv6_host_keeps_its_brackets(self):
		"""
		An IPv6 Host arrives bracketed and colon-ful: `[::1]:9200`.

		The handler has a branch for it, so the branch has to produce a whole
		bracketed address - `[::1]`, not `[` and not `[:9443`. RFC 3986 wants
		the brackets kept in the authority.
		"""
		raw = exchange(self.port,request("/",host = "[::1]:9200"))
		self.assertEqual(
			harness.header_value(raw,"location"),
			"https://[::1]:%d/" % HTTPS_PORT,
			"got %r" % raw
		)

	@harness.decision
	def test_missing_host_is_refused(self):
		"""
		No Host means no absolute URL to redirect to.

		HTTP/1.0 clients may omit it, and a redirect server has nothing else
		to name the destination with. 400 makes the reason visible to the
		client; letting the handler raise gives it a 500, which reads like
		the server broke rather than the request.
		"""
		raw = exchange(self.port,request("/",host = None,protocol = "HTTP/1.0"))
		self.assertEqual(
			harness.status_code(raw),400,
			"a request without Host got %r. The redirect needs a hostname, "
			"and the refusal belongs in the response, not in a traceback."
			% raw
		)

	@harness.decision
	def test_post_is_redirected_without_becoming_a_get(self):
		"""
		308, not 301.

		301 lets a client repeat a POST as a GET with the body dropped. The
		game sends its commands as POSTed JSON, so that turns a lost redirect
		into a lost command rather than a lost page. 308 is defined to keep
		the method and body.
		"""
		body = b'{"command":"auth","cname":"x"}'
		raw = exchange(self.port,request("/command",host = self.host,method = "POST",body = body))
		self.assertEqual(
			harness.status_code(raw),308,
			"a POST was answered with %r. A 301/302/303 turns it into a GET "
			"and drops the body; only 307/308 keep it." % raw
		)
		self.assertEqual(
			harness.header_value(raw,"location"),
			"https://127.0.0.1:%d/command" % HTTPS_PORT,
			"got %r" % raw
		)

	def test_destination_443_is_written_without_a_port(self):
		"""The default https port is implicit in a URL; `:443` is noise."""
		port = start_redirect_server(443)
		raw = exchange(port,request("/main.html",host = "127.0.0.1:%d" % port))
		self.assertEqual(
			harness.header_value(raw,"location"),
			"https://127.0.0.1/main.html",
			"got %r" % raw
		)

# --- TLS serving ----------------------------------------------------------

class TlsServeTest(unittest.TestCase):
	"""serve_forever's ssl_keys path, with a handshake actually performed."""

	@classmethod
	def setUpClass(cls):
		def handler(req,*args):
			xhttp.send_response_full(req["client"],200,payload = b"secure")
		cls.port = harness.free_port()
		promise = xhttp.serve_forever(
			("127.0.0.1",cls.port),handler,(),(CERTIFICATE,PRIVATE_KEY),True
		)
		xhttp.await_startup(promise)

	def test_https_request_is_answered(self):
		raw = tls_exchange(self.port,request("/",host = "localhost"))
		self.assertEqual(harness.status_code(raw),200,"got %r" % raw)
		self.assertIn(b"secure",raw)

	@harness.edge
	def test_plaintext_request_does_not_stop_the_listener(self):
		"""
		A client that speaks HTTP to a TLS port fails the handshake.

		That failure is per-connection and must not take the listener with it:
		the next TLS client still gets served. It is also the normal case when
		someone pastes an http:// URL into a browser pointed at the https
		port, so it must not print a traceback either - but a traceback is
		only noise, while a dead listener is an outage, so that is what this
		asserts.
		"""
		plain = socket.create_connection(("127.0.0.1",self.port),timeout = 3.0)
		plain.settimeout(3.0)
		try:
			plain.sendall(request("/",host = "localhost"))
			try:
				plain.recv(1024)
			except OSError:
				pass
		finally:
			plain.close()
		raw = tls_exchange(self.port,request("/",host = "localhost"))
		self.assertEqual(
			harness.status_code(raw),200,
			"the listener stopped serving after a plaintext connection. Got %r" % raw
		)

# --- the redirect as a serve_forever option ------------------------------

class RedirectOptionTest(unittest.TestCase):
	"""
	serve_forever(..., redirect_from=http_port) starts the redirect beside the
	real listener, so a caller does not have to manage two servers itself.

	There is one parameter, and it is the *source* port: the destination is
	always the port the server is listening on. ssl_keys is required, because
	the destination a redirect names is https.
	"""

	@staticmethod
	def _ok(req,*args):
		xhttp.send_response_full(req["client"],200,payload = b"ok")

	def start(self):
		"""A TLS server with its redirect. Returns (listen port, http port)."""
		main_port = harness.free_port()
		http_port = harness.free_port()
		promise = xhttp.serve_forever(
			("127.0.0.1",main_port),self._ok,(),(CERTIFICATE,PRIVATE_KEY),True,
			redirect_from = http_port,
		)
		xhttp.await_startup(promise)
		return main_port,http_port

	def test_redirect_runs_beside_the_main_listener(self):
		main_port,http_port = self.start()
		redirected = exchange(http_port,request("/main.html",host = "127.0.0.1:%d" % http_port))
		self.assertEqual(harness.status_code(redirected),308,"got %r" % redirected)
		self.assertEqual(
			harness.header_value(redirected,"location"),
			"https://127.0.0.1:%d/main.html" % main_port,
			"the redirect went to the wrong port; its destination must be the "
			"listener's own port. Got %r" % redirected
		)
		served = tls_exchange(main_port,request("/",host = "localhost"))
		self.assertEqual(harness.status_code(served),200,"got %r" % served)

	def test_redirect_without_ssl_keys_is_refused(self):
		"""
		An https redirect without a certificate sends clients to a port that
		cannot speak TLS. Refusing at the call is the only point where the
		caller can still fix it; silently starting a redirector to a plain
		listener is the worst outcome.
		"""
		with self.assertRaises(err.HTTPRedirectNoSSL):
			xhttp.serve_forever(
				("127.0.0.1",harness.free_port()),self._ok,(),None,True,
				redirect_from = harness.free_port(),
			)

	@harness.decision
	def test_redirect_bind_failure_is_reported(self):
		"""
		A port cannot be enabled and silently not bound.

		Port 80 is commonly taken by another web server, and the point of the
		option is that the caller does not manage the second listener. If the
		redirect cannot bind, await_startup has to raise: "server started"
		while nothing answers on the http port is a worse failure than not
		starting. The same property is already required of the main listener
		in test_server.ServeLiveTest.
		"""
		squatter = socket.socket()
		squatter.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
		squatter.bind(("127.0.0.1",0))
		squatter.listen(1)
		http_port = squatter.getsockname()[1]
		main_port = harness.free_port()
		try:
			promise = xhttp.serve_forever(
				("127.0.0.1",main_port),self._ok,(),(CERTIFICATE,PRIVATE_KEY),True,
				redirect_from = http_port,
			)
			with self.assertRaises(OSError):
				xhttp.await_startup(promise)
		finally:
			squatter.close()

if __name__ == "__main__":
	unittest.main()
