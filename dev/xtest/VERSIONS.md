# Xtest version history

> **Convention:** each entry cites the epiq ref of the release's ticket (e.g. `[ABC1234]`). Entries without a ref were released before this convention.

## 1_1_0 [48GH7NW]

The runner grows, so that the repository's own suites can run under it.

**Public API, added:** `TestCase` — a test case with `setUp`, `tearDown` and
the assertions as methods. `main(argv=None)` — the command line entry point.
**Public API, changed:** every assertion takes an optional `message`, appended
to its own. `run(target)` accepts a list of targets, and a **file now runs
that file alone** where it used to run the file's whole directory.

**The runner runs more kinds of test.** A `unittest.TestCase` class now runs,
through unittest's own machinery, so `addCleanup`, `subTest` and the skip
decorators keep working. A module's fixtures — `setUpModule` — wrap that
module's tests, which needs the module to be in `sys.modules` where unittest
looks for them.

**Why it grew.** The repository's suites are mostly `unittest.TestCase`
classes, and reimplementing unittest's fixture machinery would have been a
worse version of it. So the runner was made to carry them, rather than the
suites being rewritten — and the decision is tagged: *rewrite to xtest if it
gets in the way*, and *always write new tests with xtest*. The work is
`A7DGZYZ`; the release is `48GH7NW`.

Five suites in this repository could not be run at all before this: each exited
0 having run nothing.

## 1_0_0

Initial release of the xtest library.

Public API: equal, not_equal, same, true, raises, contains, kind, test, run.
A lightweight test runner: assertion helpers, a test decorator, and a runner
that discovers and executes test functions in a directory or module.
