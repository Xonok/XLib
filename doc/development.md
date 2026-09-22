# Development Process

How code gets written and verified in this workspace, end to end. The planner,
reviewer, and programmer agents follow this; the human drives every stage
boundary. This is the canonical home of the process — it does not live in
AGENTS.md (which carries rules for all agents, not just coding ones).

## Pipeline

Six stages, each entered on the human's call (agents never advance on their own):

| # | Stage | Who | Input | Output |
|---|-------|-----|-------|--------|
| 1 | Plan | planner (+ human) | intent | plan: reference for the spec |
| 2 | Spec | human, from the plan | plan + intent | spec: goal + requirements + decisions |
| 3 | Tests | reviewer, pass 1 | spec | tests built from the spec; spec flaws reported |
| — | Spec fixes | human | reviewer's flaw list | spec v+n; iterate 3 → 2 until tests build clean |
| 4 | Implementation | programmer | spec + tests | implementation |
| 5 | Implementation review | reviewer, pass 2 | implementation + spec + tests | verdict — required before release/merge |

## Plan

Written by the planner with the human, **before** the spec. Its purpose is to
organize intent into a reference the human can use while writing the spec:
goal, options considered, open questions. The planner does **not** write the
spec.

## Spec

**Written by the human** — writing it forces the thinking through, and keeps the
spec a documentation of the human's intent rather than an AI interpretation of
it. Single source of truth for intent and the conflict authority. Structure:

1. **Goal** — one prose paragraph: why this exists.
2. **Requirements** — the technical encoding: behaviors, formulas, interfaces,
   constraints. What tests trace to.
3. **Decisions** — numbered: choice, why, what was rejected. The choices on the
   way to the goal.

The spec is iterated: the reviewer's pass 1 surfaces flaws, the human fixes the
spec, and the loop repeats until tests derive cleanly. The finished spec must
let a fresh implementer do a good job from files alone, without further
guidance.

## Tests

Built by the reviewer (pass 1) from the spec. Tests are **load-bearing**: the
implementation is written on them.

- Edges and error cases explicit.
- Deterministic — no timing-dependent behavior, no flaky tests.
- Independent — no test depends on another's state.
- Test the contract, not the implementation.
- One assertion per test.
- Descriptive names (scenario + expected outcome).
- **Never invent**: where the spec cannot support a test, that is a spec flaw —
  reported to the human to fix, never papered over with an assumption.

Traceability, both directions:

- every test maps to a spec requirement;
- every requirement has at least one test.

Example of the gap discipline in practice: `test-design-2d-space-game.md` in the
Agents workspace (`plans/done/`).

## Review passes

**Pass 1 — test derivation and spec validation** (before any code exists):

- Build the tests from the spec.
- Every place test derivation fails is a spec flaw: report it to the human (the
  flaw list is the deliverable — not invented test assumptions).
- Traceability, both directions.
- The loop repeats until the tests build clean and the human signs off.

**Pass 2 — implementation review** (release gate). The existing review process
(see `doc/plans/reviewer-agent.md`): correctness vs spec, style compliance,
tests still pass, and the implementation matches what the tests specify.

## Rules

- **Conflict rule**: a test that disagrees with the spec is wrong — the spec is
  intent (the human's), the test is its encoding. Back to the reviewer. The
  programmer never silently changes a test to fit code; it flags the conflict.
- **Silence rule**: where tests are silent, the spec decides. Where the spec is
  also silent, that is a flaw — back to the human, not invented by the
  implementer.
- **Separation**: the reviewer writes tests and the programmer writes
  implementation — never the same agent doing both, never one combined session.

## Handoff (the implementer's contract)

The programmer works from these two files, nothing else:

1. spec (iterated until it survived test derivation)
2. tests (edges explicit)

The spec has already absorbed all found flaws as the human's fixes, so it is
the complete resolution — no third file needed.