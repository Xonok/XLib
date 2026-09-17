# Server framework

Declarative server framework that other libraries plug into. The idea: "what should happen" is declared, "how it happens" is handled by libraries.

## Goal

A developer configures *routes* and *behaviours* with minimal code; the framework wires the underlying transport details. Consumers (file-server, websocket, command-runner) are plugins, not core features.

## Design direction

- **Fresh design**, not an evolution of `xlib_legacy/dumb_http.py` (decision recorded in plans/README.md). Legacy stays reference material.
- Declarative: a route is data (path, method, handler-ish descriptor), transport handling is library logic.
- Transport agnostic where possible: HTTP today, but plugins (websocket) can extend the same connection model via upgrade.
- Concurrency: `dumb_http` used `_thread` per connection. Decide the concurrency story deliberately (blocking threads, selector loop, or async) — this shapes every consumer.

## What it must support

- Route registration with a small declarative API.
- HTTP/1.1 basics (methods, headers, keep-alive, gzip).
- Request/response helpers (send_json, redirect, streaming bodies later).
- A plugin/extension point so websocket, file-server, and command-runner can attach.
- Graceful error handling (the legacy code's "swallow socket noise, log real errors" behaviour is worth keeping).

## Consumers depending on this

- file-server (installs static serving as a route set)
- websocket (upgrade handshake + frame loop on the connection)
- command-runner (POST + websocket transports)
- webapp (view mounting)

## Out of scope for v1

- SSL/TLS (legacy had it via socket wrapping; bring back only when asked).
- HTTP/2, chunked uploads, caching headers.
- Anything consumer-specific. Plugins provide that.

## Order

Phase 2 item 8. The plugin API must be settled here — everything downstream assumes it.