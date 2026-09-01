# Testing library

Makes creating tests for a project easier. Used both by the libraries in this repo and by external projects that consume xlib.

## Goal

Small, dependency-free test runner with assertive helpers. Complements xlint (style) with behaviour checks.

## Design direction

- Register tests (name + function), run them, report pass/fail with the failing assertion's message.
- Assert helpers over plain `assert` for useful failure output (equal, is, raises, in, type check...).
- Should integrate with typechecking for schema-based assertions if useful later.
- Discovery: how tests are located (convention per folder) without fighting dev-vs-released import modes.

## Consumers

- Every xlib library during development (dev folders), replacing any ad-hoc manual verification.
- External projects via the released library.

## Order

Phase 1 item 7. Early enough to test later libraries; not blocking phase-1 leaves.

## Open questions

- Fixtures/setup-teardown in v1, or just test functions?
- Exit code / integration with xlint's --watch style use.