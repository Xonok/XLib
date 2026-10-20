<!-- spec-origin: ai -->
> **AI-written spec.** Authored by an AI agent, not by the human.

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

- **Zero dependencies**: Uses only stdlib (`importlib`, `inspect`, `os`, `sys`, `traceback`, `unittest`). No external test framework.
- **Assertion helpers are thin**: Each raises `AssertionError` with a readable message. No rich diffing, no matchers.
- **Decorator registers, doesn't wrap**: `@test` appends to `_registry` and returns the function unchanged. No fixture injection, no setup/teardown.
- **Discovery is explicit**: `run(target)` takes a directory or file path; no auto-discovery from cwd.
- **Load isolation**: Each test file is loaded as a fresh module; `sys.modules["xtest"]` is bound so tests can `import xtest` and get the same module.
- **Exit code**: `run()` returns `0` on all passed, `1` on any failure (suitable for `sys.exit(run(...))`).
- **Output format**: One line per test: `pass module.name` or `FAIL module.name: error`. Final summary: `N passed, M failed`.

## API Surface

| Symbol | Role |
|--------|------|
| `equal(a, b, message=None)` | Assert `a == b`; raises `AssertionError` with `repr` on failure |
| `not_equal(a, b, message=None)` | Assert `a != b` |
| `same(a, b, message=None)` | Assert `a is b` (identity) |
| `true(x, message=None)` | Assert `x` is truthy |
| `raises(exc, fn, message=None)` | Assert `fn()` raises `exc` (or subclass); catches wrong type / no raise |
| `contains(item, container, message=None)` | Assert `item in container` |
| `kind(value, kind_, message=None)` | Assert `isinstance(value, kind_)` |
| `test(fn)` | Decorator: register `fn` in global `_registry`; returns `fn` unchanged |
| `TestCase` | A test case with `setUp`, `tearDown` and the assertions as methods |
| `run(target=None, verbose=False)` | Run tests: no arg → registry; a file → **that file alone**; a directory → every `test_*.py` in it; a list of either. Returns exit code (0/1). |
| `main(argv=None)` | The command line entry point: `python3 dev/xtest/xtest.py <target>...` |

*Internal (not public): `_registry`, `_groups_for`, `_load_file`.*

**The message argument** (2026-10-20). Every assertion takes an optional
`message`, appended to its own. A suite of nine hundred tests cannot be read
one failure at a time, so a failure has to say what was being checked.

**`TestCase`** (2026-10-20). Each test method gets a fresh instance, so one
test's state cannot reach another's. `setUp` and `tearDown` are optional.

**Four ways to write a test** (2026-10-20). A plain function named `test_*`; a
function decorated with `@xtest.test`, whose name need not start with `test_`;
a method of an `xtest.TestCase`; and a method of a `unittest.TestCase`, which
xtest runs through unittest's own machinery so `addCleanup`, `subTest` and the
skip decorators keep working. **The last one is why the runner could be
adopted without rewriting 852 tests**: reimplementing unittest's fixture
machinery would have been a worse version of it.

**A file runs that file alone** (2026-10-20). `run("path/to/file.py")` used to
run the file's whole directory, so a question about one file was answered by
running its neighbours.

**A module's fixtures wrap that module's tests** (2026-10-20). The loader
registers the module in `sys.modules`, because unittest finds `setUpModule`
there and a module that is not registered silently loses it — and the tests
that depend on it then fail for a reason that has nothing to do with them.

**`import xtest` works wherever the suite runs from** (2026-10-20). The loader
puts xtest's own directory on `sys.path` and keeps it there, so a test file
does not have to know where xtest lives — the test files that reached for a
path relative to the *working directory* worked from the repository root and
failed from anywhere else.

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

**Released 1_0_0** carries the six assertions, `test` and a `run` that took a
directory. **Everything above marked 2026-10-20 is not in a release yet** —
`TestCase`, the `unittest.TestCase` support, the message arguments, running a
single file, and the `main` entry point. They are additive, so the next
release is a minor one, and **a release is the human's call**.

**The standardisation decision, 2026-10-20** (human): standardising on xtest
means eventually using only xtest, so the suites still in unittest's idiom are
a migration and not a second standard. Two rules carry it: **rewrite to xtest
if it gets in the way** — when a test needs something xtest cannot do, xtest
grows — and **always write new tests with xtest**. This release is the first
step: it taught the runner to carry the unittest suites rather than the suites
being rewritten first.

Parametrization, async and parallel runs are still out: they would be a
separate library or a major version.

One residue from `doc/plans/testing.md` (deleted 2026-09-30) is still open: **xlint integration is not wired**. `run()` returns a nonzero code rather than exiting, so a caller has to `sys.exit` on it; the reviewer pipeline and `tmux-xlib.sh` do that by hand rather than through xtest. Fixtures and setup/teardown are deliberately deferred — v1 is plain test functions.
