# pybundle — test derivation review (pass 2)

**Date:** 2026-10-16
**Scope:** `tools/pybundle/test/*.py` (working tree), `tools/pybundle/SPEC.md`
**Status:** Tests are derived and syntactically valid; no implementation exists to run against.

---

## Summary

The working tree holds the **pass-3 derivation** (176 tests, described in
`doc/reviews/pybundle-tests-pass1-3.md`) as **uncommitted changes** on top of
commit `6b2a0b5`, which carries the pass-2 derivation (138 tests). The changes are
real and substantial: `test_bundler.py` grows from 82 to 120 test functions across
19 classes, and the three other files carry docstring updates that close open
questions the pass-2 review left flagged.

All five files compile. All 203 fixture bodies embedded in them compile as Python.
xlint is clean over all five. The six cases the spec says the tests must pin
(SPEC.md:987-997) are each covered by at least one test.

**The tests are ready for sign-off.** One thing remains undone: the seven open
spec flaws the pass-3 review named (F25–F31) were resolved by the human's rulings
and by the tests' chosen readings, but `SPEC.md` itself has not been updated to
close them. The tests answer the questions; the spec still carries the old wording.

---

## What the working tree changed

| File | Before (HEAD) | After (working tree) | Nature |
|------|---------------|---------------------|--------|
| `test_bundler.py` | 82 tests, 9 classes | 120 tests, 19 classes | 4 classes deleted, 7 new, 3 rewritten |
| `test_bundler_names.py` | 16 tests | 16 tests | Docstring only |
| `test_bundler_source.py` | 19 tests | 19 tests | Docstring only |
| `test_bundler_cli.py` | 18 tests | 18 tests | Docstring only |
| `test_bundler_structure.py` | 3 tests | 3 tests | Unchanged |

The `test_bundler.py` diff is 514 lines. The four classes that were deleted or
replaced: `TestNameImportsD9` (11 tests, asserted the withdrawn D9 mechanism),
`TestNameCollisionsD19` (4 tests, asserted unprefixed non-local names). The seven
that are new or rewritten: `TestNameImportsD20` (15), `TestStarImportsD20` (9),
`TestNonLocalModuleImportsD20` (8), `TestNameCollisionsD24` (4),
`TestBlocksTrackedByTokensD21` (2), `TestIndentationWarningD23` (13), and three
rewritten classes in `TestImportStatementsRemovedD8`.

The docstring changes in the other three files each close an open question the
pass-2 review left: F14 (cli takes argv, not a program name), F16 (the two field
names of `statements`), and F18 (an indented local import leaves a `pass`).

---

## Addendum, 2026-10-17 — the sign-off above did not hold

**A conformance audit found three tests in this suite that cannot pass against a
conforming bundler.** All three are fixed; nothing above is edited.

| Test | Defect |
|---|---|
| `test_out_dash_writes_the_bundle_to_stdout` (`test_bundler_cli.py`) | asserted `helper__count` in the tree `TestStdoutSink.setUp` builds, which imports `first`/`shared` — nothing imports `helper.py`, so the string cannot appear |
| `test_a_file_whose_indentation_type_differs_from_a_space_root_is_reported` | the root carried no indentation, so D23's fallback anchor became the file under test, which then agreed with itself |
| `test_a_file_whose_indentation_type_differs_from_a_tab_root_is_reported` | the same, mirrored |

The two indentation tests also contradicted their own sibling
`test_a_root_without_indentation_reports_nothing_when_the_files_agree`, which has the
same input shape and asserts the opposite — so no implementation satisfied both, and
establishing that needed no ruling at all.

**Why two review passes missed them:** the checks run were *compiles*, *xlint clean*,
and *every fixture body compiles as python*. None of them asks whether a fixture
produces what its assertion expects. That gap is visible in this document's own
*Checks run* section, and closing it is worth more than re-running the same three.

The pass-3 deriver's *"ready for sign-off"* was accurate about compilation and
nothing else.
