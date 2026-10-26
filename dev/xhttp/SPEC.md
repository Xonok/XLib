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
(`<project>/lib/dumb_http_funcs.py`, committed 2026-08-07 as `641ecc8`) and was
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
		request.py    request parsing
		response.py   response building and file serving
		server.py     listener, handler loop, HTTPS redirect
		websocket.py  native websocket; frames and handshakes itself
	test/           test suite
	compare/        temporary RFC comparison material
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
mid-handshake blocks a thread for as long as it likes. `_/server.py`'s accept
loop now sets
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
back as the next request's buffer (the handler loop in `_/server.py`).

**7. The websocket is implemented natively, not through the HTTP response
writer.**

This replaces the earlier plan. `Space-Traveller/lib/websocket.py` needed an
*incremental* response writer (`send_code` / `send_header` / `end_headers`),
because it built the 101 handshake in five steps mid-stream. `_/websocket.py`
instead assembles the whole handshake into a dict and sends it in one
`send_response` call, and does its own framing with `read_exact` on the socket.

The two items that were blocking the websocket — the incremental writer and
`read_exact(n)` — are therefore **not needed as originally specified**.
`read_exact` does exist (`_/request.py`) because framing needs it; the
incremental writer does not exist and should not be added without a caller.

**8. The https redirect is a `serve_forever` option, and it trusts the request
target over `filepath`.**

`dumb_http` carried a separate `redirect_to_https` server class. The replacement
is the same listener with `redirect_from=http_port`: the caller names the source
port, and the destination is always the port the server is already listening on.
That is the part that changed with Traveller - the old implementation built the
Location from `Host` and assumed 80/443, which is wrong once the game runs on
9200/9201.

The Location is `"https://" + hostname + req["target"]`. **`target`, not
`filepath`** - `filepath` is percent-decoded and carries no query, so the old
`urlparse(...).path` dropped every query string; a redirect that loses `?v=2`
looks like a working redirect and behaves like a different page. Percent-encoding
therefore reaches the https server as the client wrote it. `Host` supplies the
hostname only; its port is replaced with the listener's own, a bracketed IPv6
address keeps its brackets, 443 is written without a port, and a request without
`Host` gets 400 - there is no hostname to redirect to.

**308, not 301.** A 301 lets a client repeat a POST as a GET with the body
dropped; the game's commands are POSTed JSON, so that is a lost command rather
than a lost page. 308 preserves the method and body. It is also cached
permanently, which is the point of a permanent redirect but worth knowing when
`https_port` is turned back off.

`redirect_from` requires `ssl_keys` and refuses without them
(`err.HTTPRedirectNoSSL`): an https Location pointing at a plain listener sends
every client into a failed handshake. The redirect's own bind is awaited through
the same startup promise as the main listener, so a taken http port reaches
`await_startup` instead of only the thread that tried to bind it.

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

## State as of 2026-10-26

Measured by running the suite, not read off the screen.

| Piece | State |
|-------|-------|
| Listener, TLS, per-connection threading, error containment | done and verified |
| Request parsing | done — method, target, headers, body; enforces Content-Length; rejects chunked, duplicate, capitalized and invalid; returns `filepath`, `payload` and `leftover` |
| Response building | done — status line, headers, body, gzip filtered through `Accept-Encoding`, auto headers; `send_file` resolves root and target through `realpath` and refuses anything outside the root |
| HTTPS redirect | done — `serve_forever(..., redirect_from=http_port)` answers every request with a 308 to the TLS port, requires `ssl_keys`, and reports a failed redirect bind through `await_startup` |
| Tests | **288 tests, 0 failures, 1 skipped** (`python3 dev/xhttp/test/run.py`) |
| dumb_http parity | **8/8** call-site capabilities present, plus the `redirect_to_https` server dumb_http also had |
| Websocket | implemented, exercised end to end, and covered by the suite; two consumer-error faults and the uninterruptible listener remain, tracked on epi `Z70VRAC` |

The websocket's remaining faults: an exception from the caller's `on_message`
still ends the connection, an exception from `on_open` still writes an HTTP 500
into the upgraded stream, and the listener has no timeout so `accept()` cannot
be interrupted. The idle-60s kill and the skipped `on_close` on a close frame
are fixed. None of these is consumer-side.

## Open

- **`send_file` config shape** — resolved 2026-10-13, and the remaining half is
	settled by the leaf rule: `send_file` takes a mapping from extension to a
	**dict** with `folder`, `mime` and `compress` keys; it never takes a tuple and
	it does not read config itself. `Space-Traveller/config/files.json` holds a
	`cache` key the library does not read.
- **`send_file` traversal guard** — resolved 2026-10-23, in `1_0_2`. The guard
	resolves the serving root and the target with `os.path.realpath` and refuses
	anything outside the root, so a symlink cannot escape the served folder. The
	literal-`..` token check is kept as a cheap second gate.
- **Header dict is lowercase-only.** `read_request` lowercases names
	and xhttp's own call sites use lowercase. The dict is still
	a plain `dict`, so an external caller writing `headers.get("X-Real-IP")`
	gets `None`. Either subclass it case-insensitively or document that callers
	lowercase.
- **`send_not_found` / `serve_files`** — covered since 2026-10-23 by
	`test_file_serving.py` (`ServeFilesTest`, `SendNotFoundTest`).
- **Websocket** — the implementation is exercised end to end and covered by the
	suite. Two consumer-error faults and the uninterruptible listener remain,
	tracked on epi `Z70VRAC`: an `on_message` exception is treated as a fatal
	transport error, an `on_open` exception writes an HTTP 500 into an already
	upgraded stream, and the listening socket has no timeout. The idle-60s kill
	and the missing `on_close` on a close frame are fixed. **`send()`
	message-type validation is not on this list**: it validates
	(`_/websocket.py:62-65`), and the two tests that said otherwise had `pass`
	inside their `assertRaises` — they were never written, so the suite read as
	a defect where there was none (epi `7Z7DE78`, closed 2026-10-18).
- **The `dev/xhttp/` folder is tracked** as of `ba84849` and `0a0dcd8`
	(2026-10-13/14). What is untracked is nothing in it.

## The error hierarchy — why twenty classes

Recorded 2026-10-18, from the human, because it is the reasoning behind a shape
that looks like duplication and is not.

**The classes are separate so a caller *can* discriminate.** The point is to
leave the option open: a caller that wants to forward certain errors to its client
— a `HTTPDoubleDotForbidden` as a 403, say — can, and one that does not care can
catch `HTTPError`. That asymmetry is the whole reason there are twenty rather
than one. Throwing a single exception class everywhere would remove it.
`HTTPRedirectNoSSL` is the one that reports a misconfiguration rather than a
request failure; it is separate so a caller can name it, and it is raised
before a listener starts rather than from a handler.

**`HTTPError` is the broad catch on purpose.** It is the base of all of them, so
a caller who wants to silence xhttp without silencing python's errors generally
catches `HTTPError` and nothing else. It is what `wrap_handler`'s blanket
`except` sits beside, and it is what the released `err_HTTPError` is for.

**Consequence for a bundle, which is why the root file carries them.** D28 of the
bundler's spec makes a local module import bind nothing, so a bundle has no `err`
attribute and no module objects at all — `xhttp.err.HTTPError` is an
`AttributeError` against a bundle. **The root file is therefore the only place a
caller of a bundle can reach these**, which is what the twenty
`err_HTTPError = err.HTTPError` lines in `xhttp.py` are for. They are public API,
not duplication, and they exist in the source for the same reason: the root is
what a caller is meant to see.
