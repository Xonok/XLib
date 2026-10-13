# xhttp RFC comparison material

**This folder is temporary.** Everything in it exists to compare xhttp's
WebSocket against a known-good RFC 6455 implementation. As xhttp absorbs the
features, each piece is either deleted or promoted into a real test in
`../test/`. Do not treat anything here as library code, and do not import it
from there.

The root of `dev/xhttp/` holds documentation, the entry point `xhttp.py`, the
internals in `_/`, and the suite in `test/`. This folder is the fourth thing,
kept separate on purpose.

## Why it is not inside `test/`

`../test/run.py` discovers with `loader.discover(HERE, pattern = "test_*.py")`,
which walks subdirectories. Seven of the files here match `test_*.py` and are
ad-hoc scripts with a `main()` rather than unittest cases — moving them into
`test/` would enrol them in the suite. `test_server.py` would additionally
clobber the tracked suite file of the same name.

## What is here

| File | What it is |
|------|------------|
| `working_websocket.py` | The reference implementation. A correct RFC 6455 WebSocket, written to fix the bugs in `../_/websocket.py` |
| `example_server.py` | Server built on the reference implementation; serves `web/` over HTTP and upgrades to WS |
| `web/index.html` | Browser test client for `example_server.py` |
| `compare_websockets.py` | The comparison harness — runs the same frames through both implementations and diffs how they answer |
| `test_original_websocket.py` | Exercises the original `../_/websocket.py` directly |
| `test_original_ping.py` | Ping/pong against the original implementation |
| `test_working_comprehensive.py` | Broad pass over the reference implementation |
| `test_websocket_client.py` | Client-side check against the reference implementation |
| `test_server.py` | Checks `example_server.py` end to end |
| `test_selenium.py` | Browser tests against `example_server.py`; needs selenium and a driver |
| `debug_websocket.py` | Step-by-step frame trace against a running server on port 8085 |

## Running them

Each script is standalone and imports through the `xhttp` namespace package,
so run it from anywhere:

```bash
python3 dev/xhttp/compare/test_working_comprehensive.py
```

Most of them start their own server and exit when done. Two do not:

- `test_selenium.py` starts `example_server.py` itself, but needs `selenium`
	and a Chrome or Gecko driver on `PATH`.
- `debug_websocket.py` assumes a server is already listening on port 8085.

## Notes

`compare_websockets.py` replaces a simpler earlier draft that used a
`parse_frame()` helper. The current version reads raw bytes instead, because it
needs to inspect the **masked** bit — a server that sends masked frames to a
client violates RFC 6455, and that is exactly the kind of difference the
comparison exists to surface. If you are looking for the simpler version, it
is gone.

`web/` is resolved relative to each script's own location, so these scripts
find it wherever the folder is moved.
