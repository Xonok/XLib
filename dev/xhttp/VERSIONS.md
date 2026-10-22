# Xhttp version history

> **Convention:** each entry cites the epiq ref of the release's ticket (e.g. `[ABC1234]`). Entries without a ref were released before this convention.

## 1_0_1 [VC9QWYY]

Keep-alive, and percent-decoding of the request target. Both found by
migrating two projects' frontends to xhttp and refreshing
traveller: the page load stalled partway, which looked like one bad image and
was not.

`serve_forever` spawned `wrap_handler` without `max_requests`, so it took the
default of 1. Every connection served one request and closed, while responses
were `HTTP/1.1` and never said `Connection: close` - so browsers reused the
connection, the server closed without reading the request already in flight,
and that file was silently lost. 384 requests over 6 keep-alive connections
gave 6 answered and 378 lost. Through the proxy it arrived as an RST
rather than a clean close. The `max_requests=120` in the public wrapper was
dead code; nothing reached it.

Four changes: `serve_forever` passes `max_requests`; the last response on a
connection carries `Connection: close` (thread-local, because `socket.socket`
has `__slots__`); `serve_files` no longer closes a socket it does not own; and
a peer closing between keep-alive requests closes quietly rather than printing
a traceback.

`read_request` also never decoded the target, so `%20` 404'd - and
Space-Traveller/img holds names with spaces in them. Decoding moves the payload
behind the `..` guard, so the guard now reads the decoded filepath and `target`
stays verbatim. Decoding the whole target instead truncates queries:
`key=a%23b` becomes `key=a`, which is the websocket login key.

**Known failing, deliberately.** `ContentNegotiationTest` is 6 failures in this
release. xhttp gzips regardless of `Accept-Encoding`, so a client that never
asked is sent `Content-Encoding: gzip`. Pre-existing, inherited from dumb_http;
ruled an issue and not yet fixed. The tests are the marker for it.

The suite is **239 tests, 6 failures, 1 skipped** - up from 223.

## 1_0_0 [2X0B2XW]

Initial release of xhttp, the hand-written HTTP/WebSocket server that replaces
`dumb_http`.

Public API: serve_forever, await_startup, wrap_handler, serve_files,
serve_websocket, read_request, read_json, read_str, read_exact, send_response,
send_response_full, send_str, send_json, send_redirect, send_file,
send_not_found, config_valid.

Plus the error classes, as `err_*` names on the module: err_HTTPError,
err_HTTPHeaderInvalid, err_HTTPHeaderNewline, err_HTTPHeaderTooBig,
err_HTTPRequestInvalid, err_HTTPDoubleDotForbidden, err_HTTPHeaderVersion,
err_HTTPHeaderDuplicate, err_HTTPChunkedEncoding, err_HTTPNegativeContentLength,
err_HTTPContentLengthBad, err_HTTPPayloadTooBig, err_HTTPBodyIncomplete,
err_JSONDecodeError, err_StrDecodeError, err_HTTPCapitalizedHeader,
err_HTTPCodeUnknown, err_WSMessageNone, err_WSMessageMustBeString.

They are separate classes so a caller can tell *which* error it was — to forward
some to the client, say — and `err_HTTPError` is the broad catch for the cases
where that distinction is not wanted, so xhttp can be silenced without silencing
python's errors generally. A bundle has no internals, so the root file is the
only place they can be reached from; that is what these names are for.

No release tag and no separate release commit: `tools/release/release.py` writes
the file and the commit that lands it is the release commit.
