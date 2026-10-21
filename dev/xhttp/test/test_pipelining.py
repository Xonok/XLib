"""
Two requests in one segment: the connection hangs.

**This is a defect, not a backlog item, and it is not the same defect as the
six in `test_response.py`.**

`request.read_request` reads up to 4096 bytes at a time, so a client that
writes two requests before reading the first answer has both of them consumed
by the first read. `read_request` is careful about this: it returns the bytes
past the request's payload as `req["leftover"]`, and `_/websocket.py` does use
them.

**`wrap_handler` does not.** Its `buffer` local is `b""` for every iteration
(`_/server.py:42`), so the second `read_request` starts from an empty buffer
and calls `recv` on a socket that has nothing left to give. The connection
then **blocks forever** - and `serve_forever` starts a thread per connection
(`_/server.py:33`), so each affected connection leaks that thread.

`dev/xhttp/SPEC.md:135` says this is implemented: *"read_request returns
leftover, and wrap_handler feeds it back as the next request's buffer"*. The
parser half is: `ParseEdgeTest.test_two_requests_in_one_segment` in
`test_parse.py` pins that the first call consumes both requests. **Nothing
pins what `wrap_handler` then does with the second one**, and what it does is
hang.

Measured 2026-10-21, on this file's own code path:

    two requests in separate segments  -> the connection is answered, and ends
    two requests in one segment        -> wrap_handler never returns

**The fix is the human's** - *"updating anything in xhttp except the tests is
human work"*, ruled 2026-10-21. The shape is small: `wrap_handler` has to
carry `req["leftover"]` into the next iteration's `buffer`, and `read_request`
already takes a `buffer` argument for exactly that.

**Why the test does not hang the suite.** A test for a hang cannot assert by
waiting for the hang. So the server runs on a daemon thread and the test
asserts that the thread *finished*, with a timeout. If the fix is not there,
the thread is still running when the timeout expires and the test fails - and
the daemon thread dies with the process, rather than pinning the suite open.
"""

import socket,threading,unittest,harness
from xhttp import xhttp

REQUEST = b"GET / HTTP/1.1\r\nHost: x\r\n\r\n"

class TwoRequestsInOneSegmentTest(unittest.TestCase):
	"""
	The second request in a pipelined segment is answered too.
	"""

	def test_two_requests_in_one_segment_are_both_answered(self):
		"""
		Both requests go out in one write, so one read consumes both.

		The server runs on a daemon thread, because `wrap_handler` is
		synchronous and the assertion is about whether it *returns* - a test
		that waited for the answer would wait for the hang.
		"""
		def handler(req, *args):
			xhttp.send_response_full(req["client"],200,payload = b"hi",compress = False)
		a,b = socket.socketpair()
		finished = []
		def serve():
			try:
				xhttp.wrap_handler(handler,(),None,a,("127.0.0.1",5),2)
			finally:
				finished.append(True)
		thread = threading.Thread(target = serve)
		thread.daemon = True
		thread.start()
		# Both requests in one write, which is what makes one read take both.
		b.sendall(REQUEST + REQUEST)
		thread.join(timeout = 5)
		self.assertTrue(
			finished,
			"the connection hung: wrap_handler did not return. The leftover of "
			"the first request is dropped, so the second read asks a socket that "
			"has nothing left to give, and the thread is stuck for the life of "
			"the process - one leaked thread per affected connection.")
		b.close()

if __name__ == "__main__":
	unittest.main()
