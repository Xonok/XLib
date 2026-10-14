# XHTTP Review

Advisory review and architectural assessment of **xhttp**, conducted on 2026-10-12.

## 1. Architectural Strengths & Design Wins

- **Class-Free Design:** Eliminating classes (except for error hierarchies under `err.py`) avoids state bundling and tight coupling, making data flow explicit and transparent.
- **Socket & Threading Discipline:**
	- Using a plain listening socket without `ssl` wrap avoids the self-defeating `super().accept()` bypass hack.
	- Performing TLS handshakes and request reading inside worker threads prevents slow clients from serializing incoming connections.
	- Setting a default 60-second timeout on accepted sockets defends against stalled half-open connections.
- **Precise IO Boundaries:** Avoiding `makefile()` prevents fd reference cycles and file descriptor leaks. Strict reading up to `\r\n\r\n` ensures no over-reading of post-header bytes, safeguarding websocket handshakes and payload integrity.

## 2. Test Suite & Parity Status

- **Core Functionality:** `./test_xhttp.sh --core` passes cleanly (131 tests passed), confirming robust behavior across parsing, response building, compression, file serving, and error handling.
- **Dumb HTTP Parity:** Achieves full 8/8 capability parity with `dumb_http`.
- **Test Suite Issue:** `test_websocket.py` currently fails to load due to an `IndentationError` at line 288 (`client = harness.ScriptedSocket(frame)`).

## 3. Open Items & Risks Requiring Attention

### A. Websocket Implementation Status
`dev/xhttp/_/websocket.py` provides a native implementation of WebSockets, but remains incomplete and unverified end-to-end:
- **Thread Lifecycle & Leak in `sender`:** The `sender` thread loops indefinitely on `ctx["_send"].get()` without a graceful shutdown sentinel or socket-liveness check. If a connection drops while messages are queued, the thread persists and memory grows unboundedly.
- **Missing End-to-End Integration:** The websocket has not been exercised through live integration tests.

### B. Security & File Serving (`send_file`)
- **Path Traversal Check:** `send_file` currently checks for the literal token `".."`. This is susceptible to bypasses (e.g., encoded sequences, symlinks). It should be strengthened with a canonicalized `os.path.realpath` check contained within the root folder's `realpath`.
- **Config Shape Mismatch:** `xhttp` unpacks three tuple elements (`folder, mime, compress`), while consuming projects use four elements (`folder, mime, compress, cache`).

### C. Request Header Case Sensitivity
`read_request` lowercases all incoming header keys into a plain Python `dict`. External handlers accessing headers using standard HTTP capitalization get `None` unless they lowercase the lookup. Subclassing `dict` case-insensitively or standardizing header access would prevent subtle bugs.

## 4. Advisory Recommendations

1. Fix the test suite loader error (`IndentationError` in `test_websocket.py`).
2. Implement a clean shutdown sentinel/liveness check for the websocket `sender` thread.
3. Upgrade the path traversal check in `send_file` to use strict realpath containment.
