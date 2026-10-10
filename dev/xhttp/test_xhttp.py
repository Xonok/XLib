import sys,os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xhttp import read_request
from _ import err
HTTPHeaderInvalid = err.HTTPHeaderInvalid
HTTPHeaderDuplicate = err.HTTPHeaderDuplicate
HTTPChunkedEncoding = err.HTTPChunkedEncoding
HTTPContentLengthBad = err.HTTPContentLengthBad

# ============================================================
# TEST CATEGORY 1: Unsupported / Missing Features
# These test features that don't exist yet (TBD in xhttp.py).
# Expected: AttributeError or NotImplementedError
# ============================================================

def test_missing_serve_file_callback():
	"""Test that serve_file_callback function doesn't exist yet (TBD feature)."""
	print("Testing missing serve_file_callback (TBD feature)...")
	try:
		from xhttp import serve_file_callback
		print("  UNEXPECTED: serve_file_callback exists (should be missing)")
		return "unexpected_exists"
	except (AttributeError, ImportError):
		print("  EXPECTED: serve_file_callback not found (AttributeError/ImportError)")
		return "unsupported"
	except Exception as e:
		print(f"  UNEXPECTED: {type(e).__name__}: {e}")
		return "error"

def test_missing_websocket_callback():
	"""Test that websocket_callback function doesn't exist yet (TBD feature)."""
	print("Testing missing websocket_callback (TBD feature)...")
	try:
		from xhttp import websocket_callback
		print("  UNEXPECTED: websocket_callback exists (should be missing)")
		return "unexpected_exists"
	except (AttributeError, ImportError):
		print("  EXPECTED: websocket_callback not found (AttributeError/ImportError)")
		return "unsupported"
	except Exception as e:
		print(f"  UNEXPECTED: {type(e).__name__}: {e}")
		return "error"

def test_send_file_exists():
	"""Test that send_file function exists."""
	print("Testing send_file (file response function)...")
	try:
		from xhttp import send_file
		print("  send_file exists - checking if callable...")
		return "exists"
	except AttributeError:
		print("  send_file not found")
		return "unsupported"
	except Exception as e:
		print(f"  Error: {type(e).__name__}: {e}")
		return "error"

def test_serve_files_exists():
	"""Test that serve_files callback handler exists."""
	print("Testing serve_files (file server callback)...")
	try:
		from xhttp import serve_files
		print("  serve_files exists - checking if callable...")
		return "exists"
	except AttributeError:
		print("  serve_files not found")
		return "unsupported"
	except Exception as e:
		print(f"  Error: {type(e).__name__}: {e}")
		return "error"

def test_send_not_found_exists():
	"""Test that send_not_found function exists."""
	print("Testing send_not_found (404 fallback function)...")
	try:
		from xhttp import send_not_found
		print("  send_not_found exists - checking if callable...")
		return "exists"
	except AttributeError:
		print("  send_not_found not found")
		return "unsupported"
	except Exception as e:
		print(f"  Error: {type(e).__name__}: {e}")
		return "error"

# ============================================================
# TEST CATEGORY 2: Runtime Errors in Existing Functions
# These test error handling when functions actually run.
# Expected: Specific exceptions for invalid input
# ============================================================

def test_malformed_header():
	print("Testing malformed header (no colon)...")
	class MockSocket:
		def __init__(self, data):
			self.data = data
			self.pos = 0
		def recv(self, n):
			chunk = self.data[self.pos:self.pos+n]
			self.pos += len(chunk)
			return chunk

	# Data with a header line without a colon: "X-Bad-Header"
	data = b"GET / HTTP/1.1\r\nX-Bad-Header\r\n\r\n"
	client = MockSocket(data)
	try:
		read_request(client, ("127.0.0.1", 12345))
		print("  Test Failed: No exception for malformed header")
		return "failed"
	except HTTPHeaderInvalid as e:
		print(f"  EXPECTED: HTTPHeaderInvalid caught: {e}")
		return "passed"
	except ValueError as e:
		print(f"  BUG: ValueError caught instead of HTTPHeaderInvalid: {e}")
		return "failed"
	except Exception as e:
		print(f"  Test Failed: Unexpected exception: {type(e).__name__}: {e}")
		return "failed"

def test_newline_issue():
	print("\nTesting newline issue (using \\n instead of \\r\\n)...")
	class MockSocket:
		def __init__(self, data):
			self.data = data
			self.pos = 0
		def recv(self, n):
			chunk = self.data[self.pos:self.pos+n]
			self.pos += len(chunk)
			return chunk

	# Data with \n instead of \r\n - should be rejected as invalid
	data = b"GET / HTTP/1.1\nHeader: Value\n\n"
	client = MockSocket(data)
	try:
		read_request(client, ("127.0.0.1", 12345))
		print("  Test Failed: No exception for bare LF line endings")
		return "failed"
	except HTTPHeaderInvalid as e:
		print(f"  EXPECTED: HTTPHeaderInvalid caught: {e}")
		return "passed"
	except Exception as e:
		print(f"  Test Failed: Unexpected exception: {type(e).__name__}: {e}")
		return "failed"

def test_duplicate_header():
	print("\nTesting duplicate header...")
	class MockSocket:
		def __init__(self, data):
			self.data = data
			self.pos = 0
		def recv(self, n):
			chunk = self.data[self.pos:self.pos+n]
			self.pos += len(chunk)
			return chunk

	data = b"GET / HTTP/1.1\r\nHeader: Value1\r\nHeader: Value2\r\n\r\n"
	client = MockSocket(data)
	try:
		read_request(client, ("127.0.0.1", 12345))
		print("  Test Failed: No exception for duplicate header")
		return "failed"
	except HTTPHeaderDuplicate as e:
		print(f"  EXPECTED: HTTPHeaderDuplicate caught: {e}")
		return "passed"
	except Exception as e:
		print(f"  Test Failed: Exception caught: {type(e).__name__}: {e}")
		return "failed"

def test_chunked_encoding():
	print("\nTesting chunked encoding (not supported)...")
	class MockSocket:
		def __init__(self, data):
			self.data = data
			self.pos = 0
		def recv(self, n):
			chunk = self.data[self.pos:self.pos+n]
			self.pos += len(chunk)
			return chunk

	data = b"GET / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n"
	client = MockSocket(data)
	try:
		read_request(client, ("127.0.0.1", 12345))
		print("  Test Failed: No exception for chunked encoding")
		return "failed"
	except HTTPChunkedEncoding as e:
		print(f"  EXPECTED: HTTPChunkedEncoding caught: {e}")
		return "passed"
	except Exception as e:
		print(f"  Test Failed: Exception caught: {type(e).__name__}: {e}")
		return "failed"

def test_invalid_content_length():
	print("\nTesting invalid content-length...")
	class MockSocket:
		def __init__(self, data):
			self.data = data
			self.pos = 0
		def recv(self, n):
			chunk = self.data[self.pos:self.pos+n]
			self.pos += len(chunk)
			return chunk

	data = b"GET / HTTP/1.1\r\nContent-Length: not-a-number\r\n\r\n"
	client = MockSocket(data)
	try:
		read_request(client, ("127.0.0.1", 12345))
		print("  Test Failed: No exception for invalid content-length")
		return "failed"
	except HTTPContentLengthBad as e:
		print(f"  EXPECTED: HTTPContentLengthBad caught: {e}")
		return "passed"
	except Exception as e:
		print(f"  Test Failed: Exception caught: {type(e).__name__}: {e}")
		return "failed"

def test_valid_request():
	print("\nTesting valid request...")
	class MockSocket:
		def __init__(self, data):
			self.data = data
			self.pos = 0
		def recv(self, n):
			chunk = self.data[self.pos:self.pos+n]
			self.pos += len(chunk)
			return chunk

	data = b"GET /path HTTP/1.1\r\nHost: example.com\r\nContent-Length: 5\r\n\r\nhello"
	client = MockSocket(data)
	try:
		result = read_request(client, ("127.0.0.1", 12345))
		if result["method"] == "GET" and result["target"] == "/path" and result["payload"] == b"hello":
			print("  Test Passed: Valid request parsed correctly")
			return "passed"
		else:
			print(f"  Test Failed: Unexpected result: {result}")
			return "failed"
	except Exception as e:
		print(f"  Test Failed: Exception caught: {type(e).__name__}: {e}")
		return "failed"

# ============================================================
# TEST RUNNER
# ============================================================

def run_tests():
	print("=" * 60)
	print("XHTTP TEST SUITE")
	print("=" * 60)
	
	# Category 1: Unsupported features
	print("\n--- CATEGORY 1: Unsupported / Missing Features ---")
	unsupported_results = []
	unsupported_results.append(("serve_file_callback", test_missing_serve_file_callback()))
	unsupported_results.append(("websocket_callback", test_missing_websocket_callback()))
	unsupported_results.append(("send_file", test_send_file_exists()))
	unsupported_results.append(("serve_files", test_serve_files_exists()))
	unsupported_results.append(("send_not_found", test_send_not_found_exists()))
	
	print("\nUnsupported feature summary:")
	for name, result in unsupported_results:
		status = {
			"unsupported": "UNSUPPORTED (expected)",
			"unexpected_exists": "EXISTS (unexpected)",
			"exists": "EXISTS (known)",
			"error": "ERROR"
		}.get(result, result)
		print(f"  {name}: {status}")
	
	# Category 2: Runtime errors
	print("\n--- CATEGORY 2: Runtime Error Handling ---")
	runtime_results = []
	runtime_results.append(("malformed_header", test_malformed_header()))
	runtime_results.append(("newline_issue", test_newline_issue()))
	runtime_results.append(("duplicate_header", test_duplicate_header()))
	runtime_results.append(("chunked_encoding", test_chunked_encoding()))
	runtime_results.append(("invalid_content_length", test_invalid_content_length()))
	runtime_results.append(("valid_request", test_valid_request()))
	
	print("\nRuntime error handling summary:")
	passed = sum(1 for _, r in runtime_results if r == "passed")
	failed = sum(1 for _, r in runtime_results if r == "failed")
	for name, result in runtime_results:
		status = "PASSED" if result == "passed" else "FAILED"
		print(f"  {name}: {status}")
	
	print(f"\n--- SUMMARY ---")
	print(f"Unsupported features (expected missing): {sum(1 for _, r in unsupported_results if r == 'unsupported')}")
	print(f"Runtime tests passed: {passed}/{len(runtime_results)}")
	print(f"Runtime tests failed: {failed}/{len(runtime_results)}")
	
	if failed > 0:
		print("\nSOME TESTS FAILED")
		return 1
	else:
		print("\nALL RUNTIME TESTS PASSED")
		return 0

if __name__ == "__main__":
	sys.exit(run_tests())
