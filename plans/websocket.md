# Websocket logic

Websocket protocol handling as a library, plus a server-framework plugin layer.

## Goal

Correct websocket framing send/receive on top of a socket-like object, reused between server connections and (later) clients. The protocol part is transport-free; the server plugin wires it to an HTTP upgrade.

## Design direction

- Protocol layer: frame encode/decode (text, binary, ping/pong, close, continuation frames), mask handling, length encodings (125/126/127).
- `xlib_legacy/websocket.py` is the prior art — it already does handshake + basic frames but lacks continuation frames and client mode. Use it as reference, not as the base (server framework is fresh).
- Receive loop is a reader that yields messages/opcodes rather than the legacy thread+dangling references.
- Send path must be thread-safe (the legacy code used a queue + sender thread; keep that idea, fix the "sender uses a stale `c`" bug).
- Automatic ping/keepalive obligation decided explicitly (who sends pings).

## Plugins / integrations

- Server plugin: recognize the HTTP upgrade request, perform handshake, hand the connection to command-runner or app code.
- Binary framing support even though most traffic today is JSON text frames.

## Depends on

- server-framework (for the plugin layer only).
- Nothing in the protocol core.

## Order

Phase 2 item 10 (protocol can proceed in parallel with item 8; plugin layer after).

## Open questions

- Client-side websocket in scope for v1? (protocol is shared; opening outgoing sockets is extra).
- Max message size / backpressure policy.