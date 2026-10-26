# XHTTP

This is a replacement for dumb\_http.py and websocket.py
It's meant to be more generic and easier to use, but support the same features.

## What it provides

HTTP/1.1 with keep-alive, TLS on the accepted connection
(`serve_forever(..., ssl_keys=(certificate, private_key))`), an optional
HTTP-to-HTTPS redirect (`redirect_from=http_port`), WebSocket, file serving
from a caller-supplied mapping, and gzip filtered through the request's
`Accept-Encoding`.

## Key differences compared to dumb_http

No class bloat. Classes are only used where they are entirely unavoidable - for error types.
Modular - use what you want, disregard the rest. Provides simple tools for typical use cases and can easily be overloaded with custom code if needed.
The library is a leaf node. It doesn't look for config - the caller provides it whatever is needed.

## XLib rules

This library(xhttp) is not AI-written and should not be edited by AI.
Tests for it are AI-written and should be updated as needed.
