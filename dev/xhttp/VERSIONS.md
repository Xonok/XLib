# Xhttp version history

> **Convention:** each entry cites the epiq ref of the release's ticket (e.g. `[ABC1234]`). Entries without a ref were released before this convention.

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
