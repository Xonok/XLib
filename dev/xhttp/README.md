# XHTTP

This is a replacement for dumb\_http.py and websocket.py
It's meant to be more generic and easier to use, but support the same features.

## Key differences compared to dumb_http

No class bloat. Classes are only used where they are entirely unavoidable - for error types.
Modular - use what you want, disregard the rest. Provides simple tools for typical use cases and can easily be overloaded with custom code if needed.
The library is a leaf node. It doesn't look for config - the caller provides it whatever is needed.
