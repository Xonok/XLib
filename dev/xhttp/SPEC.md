# xhttp

A hand-written HTTP/WebSocket server library, and the replacement for
`dumb_http.py`.

> **Provenance.** Written inside Space-Traveller as `lib/xhttp/`, then moved
> here on 2026-10-10 so it could be developed and consumed while still a dev
> version. The design record came with it, from `notes/xhttp.md` there; the
> Space-Traveller decision entry of 2026-10-04 holds the original rationale and
> stays there, since it is that repo's record. This file is the current
> version of that record — status re-measured, not carried over.

## Why it exists

Four goals, as given:

- "Get rid of classes. They promote bundling state as a default. While it's
	useful sometimes, it's bad as a default due to tight coupling and data
	flow opacity."
- "Make calling the library require as few lines and as little work as
	possible. Standard HTTP choices like how to serve files need to be provided
	by config."
- "API functions need to be at the start of the file and well named."
- "Previous features must not be lost."

Written by hand on purpose. A class-free version already existed
(`Whitepage/lib/dumb_http_funcs.py`, committed 2026-08-07 as `641ecc8`) and was
**not** used as a starting point — the point of the rework is a hand-written,
maximally simple thing, and a port is not that. Do not "helpfully" port it in
later.

## Module map

```
dev/xhttp/
	xhttp.py        entry point: the public interface
	_/
		err.py        HTTPError and its subclasses
		helper.py
		websocket.py  native websocket; frames and handshakes itself
	test/           test suite, 115 tests
	SPEC.md         this file
	README.md       short overview
```

`_/websocket.py` is **not** a port of Space-Traveller's `lib/websocket.py`. It
is a fresh implementation that works directly on the accepted socket. That
difference matters — see decision 7.

## Decisions

Each of these forecloses something. If a future change wants to reverse one,
the reason below is the thing that has to be re-argued.

**1. The listening socket is a plain `socket.socket()`; only the accepted
connection is wrapped.**

`dumb_http` wrapped the *listener* with `ssl` and then deliberately bypassed
the resulting `SSLSocket.accept()` via `super(type(sock),sock).accept()`,
re-wrapping by hand. That is self-defeating: it installs an `SSLSocket` purely
to route around it. Four designs were tested with a real handshake; a plain
listener plus a per-connection wrap works identically, and dropping the listener
wrap also drops the `super()` trick, because `accept()` on a plain socket is
already the right `accept()`.

Verified: wrapping twice is a hard error — `SSL: UNEXPECTED_MESSAGE` — so with
a wrapped listener the bypass is *mandatory*. Removing the listener wrap is
what makes it unnecessary.

**2. The handshake happens in the worker thread, not the accept loop.**

`wrap_socket(..., server_side=True)` defaults to `do_handshake_on_connect=True`,
which performs the handshake inline. Done in the accept loop, handshakes are
serialised behind the slowest one. `dumb_http` avoided this; an intermediate
version of `xhttp` reintroduced it and was corrected.

**3. Accepted sockets get a timeout of their own.**

The original measurement, and the reason this decision needed making:

```
listener gettimeout      : 1.0
accepted sock gettimeout : None     -> NOT inherited
```

An accepted socket is fully blocking, so a peer that connects and stalls
mid-handshake blocks a thread for as long as it likes. `xhttp.py:47` now sets
`settimeout(60)` on accepted sockets, which is the only defence. Verified in
the test suite as `test_accepted_socket_has_no_timeout`.

**4. No `settimeout` on the listening socket.**

`settimeout(1)` makes `accept()` raise `TimeoutError` once a second while
idle, and in `xhttp`'s accept loop that reached the blanket handler and printed
a traceback every second. A blocking `accept()` in `while True` needs no
timeout, and "the listener must never crash" is better served by not having one
to expire.

This is the opposite of `dumb_http`, where the same idle timeout was swallowed
*silently* by a `socket.error` / `EWOULDBLOCK` clause. Two places disagreeing
about the same exception is worse than either behaviour alone.

**5. No `makefile`. Use `recv` and `sendall`.**

On the write side `makefile` is actively harmful — a `wfile.write` monkeypatch
creates a reference cycle that leaks the fd. On the read side it buys exactly
one thing, `read(n)` filling to exactly `n`, which is a loop you need anyway
because `recv` short-reads normally:

```
BufferedReader.read(10) -> b'1234567890' len=10 after 0.90s   filled n? True
raw socket recv(10)     -> b'12345'         len=5  after 0.30s  filled n? False
```

SSL gives `makefile` no special role: `SSLSocket.recv` in 3.14 has no
Python-level length cap, it just delegates to `read`, and a TLS record limit
surfaces as a short read rather than a rejection.

**Not a bug, despite appearances:** Space-Traveller's `lib/websocket.py` frame
reads (`server.rfile.read(size)`) were correct, because that is a
`BufferedReader` and `read(n)` does block until it has `n` bytes. This is no
longer applicable — `xhttp` no longer carries a port of that file.

**6. Never read past `\r\n\r\n`.**

The one place over-reading matters. A websocket's first frame bytes must still
be in the kernel when the HTTP layer hands the connection over. With explicit
`recv` you control exactly how many bytes leave the socket; with a
`BufferedReader` you do not, and that property is invisible.

This is the same class of bug that `ed66b138` shipped in Space-Traveller —
losing the query string because `self.path` was overwritten with a parsed
value, which broke websocket login with a `KeyError` on every connection.

Implemented: `read_request` returns `leftover`, and `wrap_handler` feeds it
back as the next request's buffer (`xhttp.py:63`).

**7. The websocket is implemented natively, not through the HTTP response
writer.**

This replaces the earlier plan. `Space-Traveller/lib/websocket.py` needed an
*incremental* response writer (`send_code` / `send_header` / `end_headers`),
because it built the 101 handshake in five steps mid-stream. `_/websocket.py`
instead assembles the whole handshake into a dict and sends it in one
`send_response` call, and does its own framing with `read_exact` on the socket.

The two items that were blocking the websocket — the incremental writer and
`read_exact(n)` — are therefore **not needed as originally specified**.
`read_exact` does exist (`xhttp.py:178`) because framing needs it; the
incremental writer does not exist and should not be added without a caller.

## Traps not to re-introduce

- **`do_handshake_on_connect` / `suppress_ragged_eofs`** — both are `True`,
	both are `wrap_socket`'s own defaults, and neither is changed anywhere in
	`dumb_http`. Passing them explicitly is a no-op. They are written out only
	because the code stands in for `SSLSocket.accept()`, which is the thing that
	normally supplies them. **Deleting the `super()` bypass and going back to
	`accept()` would silently serialise every handshake** — the parameters are
	not what is load-bearing, the threading is.
- **`wrap_error` used to be called with an unbound handler plus an args
	tuple**, so it held no handler instance and could not answer through one.
- The exception chain's behaviour: once an `except` clause matches, later
	clauses are never tried. `socket.error` **is** `OSError`, so an `EWOULDBLOCK`
	test inside it silently swallows anything else in that category.

## State as of 2026-10-10

Measured by running the suite, not read off the screen.

| Piece | State |
|-------|-------|
| Listener, TLS, per-connection threading, error containment | done and verified |
| Request parsing | done — method, target, headers, body; enforces Content-Length; rejects chunked, duplicate, capitalized and invalid; returns `filepath`, `payload` and `leftover` |
| Response building | done — status line, headers, body, gzip, auto headers; `send_file` config shape still mismatched (below) |
| Tests | `--core` **103 passed, exit 0**. Full **115 tests, 1 failure, 2 skipped**. The failure is an edge test, `test_two_requests_in_one_segment` (pipelining) |
| dumb_http parity | **8/8** call-site capabilities present |
| Websocket | `_/websocket.py` written, **not yet runnable** — see below |

The one outstanding failure is `ParseEdgeTest.test_two_requests_in_one_segment`:
the second request in a pipelined segment is drained before the test can read
it. It is tagged `@harness.edge`, so it is documented backlog rather than a
blocker.

### The websocket does not currently run

`from xlib_dev import xhttp` **works** — import chain fixed.

The defects that remain in `_/websocket.py`:

- **`sender` thread leak**: `serve_websocket` starts `sender` and `receiver` threads.
	`receiver` breaks on error and calls `on_close`. `sender` loops forever on
	`ctx["_send"].get()` with no shutdown path. If `send()` is called after the
	connection drops, the queue grows unbounded and the thread is never
	recycled. No sentinel, no socket-liveness check, no cleanup.
- `queue` imported but unused (the `queue.Queue` is created in `context()`).
- The websocket has never been exercised end-to-end.

The `key_hash` typo, `_send` arg order, and `on_message` msg pass were fixed 2026-10-10.

## Open

- **`send_file` config shape** — `xhttp.py:249` unpacks three values
	(`folder, mime, compress`); `Space-Traveller/config/files.json` holds four
	per extension (`folder`, `mime`, `compress`, `cache`). Undecided whether
	`xhttp` reads that file directly or takes a mapping. `mime` is unpacked but
	unused.
- **`send_file` traversal guard** — `xhttp.py:253` rejects the literal token
	`".."`, which is weaker than a `realpath`-inside-`realpath(cwd)` check.
	Path traversal is live on `dumb_http` as soon as file serving becomes
	config-driven, so this belongs in `xhttp`.
- **Header dict is lowercase-only.** `read_request` lowercases names
	(`xhttp.py:127`) and xhttp's own call sites use lowercase. The dict is still
	a plain `dict`, so an external caller writing `headers.get("X-Real-IP")`
	gets `None`. Either subclass it case-insensitively or document that callers
	lowercase.
- **`send_not_found` / `serve_files`** — no direct coverage in the suite.
- **Websocket** — the six defects above.
- **The `dev/xhttp/` folder is untracked.** Nothing in it is committed.
