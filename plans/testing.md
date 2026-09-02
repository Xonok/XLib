# xtest

Makes creating tests for a project easier. Used both by the libraries in this repo and by external projects that consume xlib. Versioned like any library (external projects depend on it), which also makes it a good end-to-end test of the release pipeline — it was the first library released through it (`xlib/xtest_1_0_1.py`).

## What exists

Small, dependency-free test runner with assert helpers. Complements xlint (style) with behaviour checks. Implemented at `xtest/xtest.py`.

## API

- Assert helpers raising `AssertionError` with a useful message: `equal`, `not_equal`, `same` (identity), `true`, `raises`, `contains`, `kind` (isinstance).
- `@xtest.test` decorator registers a test function into the module-level registry.
- `run(target=None)` runs tests and returns a nonzero exit code when any fail:
  - no target → the registered tests
  - a directory → discovers `test_*.py` files, running their `test_*` functions
  - a file path → discovers in that file's directory

## Discovery and dev-vs-released import modes

Test modules do `import xtest`. Discovery aliases the running library into `sys.modules["xtest"]` while loading each test module, so tests resolve the same library whether run against the dev version (`from xtest import xtest`) or a released version (`from xlib import xtest`). This resolves the plan's open question about discovery without fighting import modes.

## Open questions

- Fixtures/setup-teardown: deferred; v1 is plain test functions. The plan's open question stands if needed later.
- Exit-code / `--watch`-style integration with xlint: not wired yet; `run()` returns the code so a caller can `sys.exit` on it.

## Consumers

- Every xlib library during development (dev folders), replacing any ad-hoc manual verification.
- External projects via the released library.

## Order

Phase 1 item 7 (`xtest`, formerly "testing"). Built and released; later libraries are developed against it.