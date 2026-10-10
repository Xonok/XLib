# xhttp test suite

## One-line command

```bash
python3 dev/xhttp/test/run.py
```

Runs all tests from anywhere, as long as the path is reachable from the XLib
root. Exit code 0 = all passed, 1 = failures.

```bash
python3 dev/xhttp/test/run.py --core
```

Runs only the *core* tests — ordinary traffic, framing, lifecycle and the
dumb_http parity surface. Edge cases (hand-crafted hostile requests) are
skipped; they are tracked but not what the library is judged on yet.

---

## Test groups

| File | Scope | Core? |
|------|-------|-------|
| `test_parse.py` | `read_request` contract — what a browser and the game actually send | yes |
| `test_response.py` | `write_response` / `write_response_full` — status line, headers, body, partial writes, gzip, capitalisation | yes |
| `test_server.py` | `serve_forever`, `wrap_handler` — fd leak, close, error containment, bind reporting | yes |
| `test_parity.py` | dumb_http feature parity — the exact call sites in server.py, websocket.py, Chat/api.py | yes |
| `test_parse.py` (ParseEdgeTest) | TE casing, pipelining, path traversal, obs-fold, bare LF | no |
| `test_response.py` (ResponseEdgeTest) | header injection, peer vanishes mid-response | no |
| `test_server.py` (WrapHandlerEdgeTest) | stalling peers, SSL errors, accepted-socket timeout | no |

---

## How to read the failures

The suite is a *specification*, not a gate. Every test asserts correct
behaviour; a failure means that behaviour is missing.

- **Core failures** are regressions or blockers for the ordinary path. They
	correspond to the findings in the advisory notes and are the things to fix
	first.
- **Edge failures** are documented backlog. They are not the current
	priority, but they are not forgotten.
- **Decision-tagged tests** (`@harness.decision`) encode a choice the human
	has not ruled on yet. The test states the assumption in its docstring; a
	failure is a prompt to rule, not a bug.

---

## Running a single file or test

```bash
python3 -m unittest discover -s dev/xhttp/test -p test_parse.py
```

```bash
python3 -m unittest test_parse.ParseCoreTest.test_plain_get
```

Discovery works because `run.py` inserts `dev/xhttp` on `sys.path`, which is
where `xhttp.py` lives and where its `from _ import helper,err` resolves.

---

## What the suite covers that ad-hoc runs do not

- **Real socketpairs and `/proc/self/fd`** — the fd leak test counts open
	descriptors, not mocks. A refcounting close looks like success on a mock
	but leaks under a real handler that keeps a reference.
- **`PartialSendSocket`** — a socket whose `send()` accepts only 16 bytes at
	a time. If the code uses `send()` and ignores the return value, the tail
	drops silently. `sendall()` writes everything; the test asserts the full
	payload arrives.
- **`read_request` over-read** — a websocket upgrade whose first frame shares
	the TCP segment with the request headers. The test asserts the remainder is
	recoverable; `read_request` returns it as `leftover`, and `wrap_handler`
	feeds it back as the next request's buffer.
- **`Content-Length` enforcement** — the payload returned must never exceed
	the declared length; anything past it belongs to the next request.
- **dumb_http parity table** — one test per actual call site in the repo,
	so the replacement gap is measured rather than guessed.
- **Preflight check** — `run.py` reports the state of the response path
	before the first test, so a cascade of `NameError` does not hide the real
	causes.

---

## Conventions

- **Tabs** — the project uses tabs; the tests do too.
- **No external deps** — `unittest` is stdlib.
- **Edge = `@harness.edge`** — tagged, not skipped, so the full run always
	shows the complete backlog. `--core` filters them.
- **Decision = `@harness.decision`** — the docstring states the choice; the
	test assumes one side. Change the assumption when the ruling lands.
- **`HttpErrorAssertions`** — converts a non-HTTPError exception into a clean
	`FAIL` with context, instead of an `ERROR` that looks like a broken test.

---

## Design assumptions the tests pin

- A handler is `func(client, client_addr)` — `serve_forever` already uses
	this, and `test_parity.py` assumes it throughout.
- `read_request` returns a `dict` with `target`, `headers`, `payload`, etc. —
	no object, no attributes. If that changes, the parity tests change with it.
- `write_response` / `write_response_full` are the response API. The
	incremental `send_code`/`send_header`/`end_headers` path from dumb_http
	does not exist yet; `test_parity.py` records that as a missing capability.
- `**headers` cannot express hyphenated names via keyword arguments, but it
	does via `**dict` — `test_response.py` pins the workaround so it is not
	lost.

---

## Adding a test

1. Create `test_<name>.py` in this directory, matching `test_*.py`.
2. Use `harness` for sockets, `assert_http_error` for refusal tests.
3. Tag `@harness.edge` or `@harness.decision` as appropriate.
4. Run `python3 dev/xhttp/test/run.py` to verify it is picked up.
