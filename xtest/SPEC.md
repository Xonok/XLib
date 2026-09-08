# xtest Spec

## Overview

**xtest** is a lightweight test runner with assertion helpers. It provides a minimal set of assertion functions, a `@test` decorator for registering tests, and a `run()` function that discovers and executes test functions from a directory, module, or the global registry. Designed for zero-dependency testing in XLib libraries.

## Data Flow

```
Test definition:
    @test                          def test_foo(): ...
         │                                 │
         ▼                                 ▼
    _registry.append(fn)            assertions (equal, raises, etc.)
         │                                 │
         │                +----------------+------------------+
         │                |                |                  |
         ▼                ▼                ▼                  ▼
    run() ─────────► _run_funcs()    AssertionError     AssertionError
         │                │             (fail)             (pass)
         │                ▼
         │         print "pass/FAIL"
         │                │
         ▼                ▼
    returns (0|1)    passed, failed counts
```

**Discovery modes:**
- `run()` → runs all `@test` functions registered in `_registry`
- `run("path/to/dir")` → loads `test_*.py` files, collects `test_*` functions
- `run("path/to/file.py")` → loads that file's directory, runs all tests there

## Key Invariants / Design Decisions

- **Zero dependencies**: Uses only stdlib (`importlib`, `os`, `sys`). No external test framework.
- **Assertion helpers are thin**: Each raises `AssertionError` with a readable message. No rich diffing, no matchers.
- **Decorator registers, doesn't wrap**: `@test` appends to `_registry` and returns the function unchanged. No fixture injection, no setup/teardown.
- **Discovery is explicit**: `run(target)` takes a directory or file path; no auto-discovery from cwd.
- **Load isolation**: Each test file is loaded as a fresh module; `sys.modules["xtest"]` is bound so tests can `import xtest` and get the same module.
- **Exit code**: `run()` returns `0` on all passed, `1` on any failure (suitable for `sys.exit(run(...))`).
- **Output format**: One line per test: `pass module.name` or `FAIL module.name: error`. Final summary: `N passed, M failed`.

## API Surface

| Symbol | Role |
|--------|------|
| `equal(a, b)` | Assert `a == b`; raises `AssertionError` with `repr` on failure |
| `not_equal(a, b)` | Assert `a != b` |
| `same(a, b)` | Assert `a is b` (identity) |
| `true(x)` | Assert `x` is truthy |
| `raises(exc, fn)` | Assert `fn()` raises `exc` (or subclass); catches wrong type / no raise |
| `contains(item, container)` | Assert `item in container` |
| `kind(value, kind_)` | Assert `isinstance(value, kind_)` |
| `test(fn)` | Decorator: register `fn` in global `_registry`; returns `fn` unchanged |
| `run(target=None)` | Run tests: no arg → registry; dir → discover `test_*.py`; file → its directory. Returns exit code (0/1). |

*Internal (not public): `_registry`, `_run_funcs`, `_load_dir`.*

## Data Structures

- **`_registry: list[Callable]`** — Global list of registered test functions (no args, no return expected).
- **Test function** — Any callable `fn()` taking no arguments. Expected to call assertion helpers; uncaught exceptions = failure.

## Error Messages

Each helper formats a readable message:

- `equal`: `not equal: {a!r} != {b!r}`
- `not_equal`: `unexpectedly equal: {a!r}`
- `same`: `not identical: {a!r} is not {b!r}`
- `true`: `expected truthy, got {x!r}`
- `raises`: 
  - Wrong type: `expected {exc.__name__}, got {type(e).__name__}: {e}`
  - None raised: `expected {exc.__name__}, but nothing raised`
- `contains`: `{item!r} not in {container!r}`
- `kind`: `expected {kind_.__name__}, got {type(value).__name__}`

## Planned Changes

None currently. The library is intentionally minimal. If richer features are needed (fixtures, parametrization, async, parallel), they would be a separate library or a major version with breaking changes.