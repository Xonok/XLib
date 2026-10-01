# Development Process

How code gets written and verified in this workspace, end to end. The planner,
reviewer, and programmer agents follow this; the human drives every stage
boundary. This is the canonical home of the **development** process — it does
not live in AGENTS.md (which carries rules for all agents, not just coding
ones).

The board mechanics live in AGENTS.md instead, under *Working on a ticket*:
which lane a ticket is in, and what an agent may do with git. The split is
deliberate in both directions — this file describes how a piece of work is
decided and built, AGENTS.md describes how it gets recorded and lands.

## Two tracks

Work reaches the board by one of two routes, and the choice is about size of
intent, not about importance.

| | Track 1 — the spec pipeline | Track 2 — the ticket is the spec |
|---|---|---|
| For | feature work, anything intent-heavy | everything else; **the default** |
| The spec | its own file, written by the human | the ticket description |
| Shape | goal → requirements → decisions, as below | same three parts, in the description |
| Tests | derived by the reviewer before code exists | written by the implementing agent, if the ticket calls for them |
| Review | pass 2, by the reviewer | the pull request |

**The boundary rule:** if the human would write the spec himself, it is track 1.
If the goal, scope and acceptance fit in a ticket description, it is track 2.

Track 2 is the default because track 1 costs a human-authored document and a
second agent per ticket, and that is not worth paying for a fix whose whole
scope fits in a paragraph. What track 2 gives up is the forcing function — the
human thinking a design through by writing it down — so the human still
approves the description before the agent starts, which is the same thinking at
a smaller size.

Neither track is exempt from the rules below. The conflict rule, the silence
rule and the style/architecture rules apply to both; track 2 changes where the
spec lives, not what an agent may decide alone.

## The board

Both tracks are tracked on the epiq board, one ticket per independent piece of
work, on its own feature branch — see *Working on a ticket* in `AGENTS.md` for
the lanes and the commit rules. A track-1 piece is usually several tickets,
one per stage, because a stage that takes days and a stage that takes twenty
minutes are not the same thing to review.

A track-1 spec may be written by hand as before; an agent moves and tags the
ticket as the stage progresses. The agent does not write it.

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

### Spec authorship — who may rewrite a spec

**Specs are owned by the human.** The consequence is that an agent must be able
to tell, from the file alone, whether it is allowed to rewrite one. So:

- **An AI-written spec must say so, at the top, in this exact form:**

	```
	<!-- spec-origin: ai -->
	> **AI-written spec.** Authored by an AI agent, not by the human.
	```

	The HTML comment is the machine-readable marker (grep it); the blockquote is
	what a human reads. Both are required, so a tool can check authorship without
	parsing prose and a human cannot miss it.

- **A spec with no marker is assumed human-written.** Absence of the marker is
	the claim, not absence of authorship information.
- **An AI-written spec may be rewritten by AI** — the human has already accepted
	that it is an AI interpretation of their intent, so improving it is in scope.
	Rewriting is not a licence to change the intent: the decisions section still
	records the human's choices.
- **A human-written spec may not be edited by an AI at all** without the human
	asking for that specific edit. Not "while I'm here", not "it's only a typo".

As of 2026-09-27 all eight specs in this repo are AI-written and labelled, and
the human has **no** spec committed here. Do not read git authorship as evidence:
the human commits everything, so a file carries their name whatever wrote it.
Only the `spec-origin` marker means anything. The human's own hand-written pybundle
spec was moved out of the repo during the tool folder move and is deliberately
absent — if it reappears unlabelled, leave it alone.

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

Where they live: a library's tests go in a `test/` folder in its dev folder, not
`tests/` — the human's ruling, 2026-09-30. `dev/xprod/` already complies; the
other four dev libraries still use `tests/` and are being renamed (epiq `2VD2XZC`).

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
(see the reviewer's agent file): correctness vs spec, style compliance,
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
- **Spec ownership**: see *Spec authorship* above. An agent about to edit a spec
	must check the marker first; an unmarked spec is the human's and is off
	limits unless the human asked for that edit.

## Handoff (the implementer's contract)

The programmer works from these inputs, and no others:

1. spec (iterated until it survived test derivation)
2. tests (edges explicit)
3. the project guidelines in `doc/style/` — always `architecture.md` and
	`common.md`, plus the language-specific file for the language in hand
	(`python.md`, `js.md`, `markdown.md`)

The spec has already absorbed all flaws found during test derivation as the
human's fixes, so it is the complete resolution *of those* — no third file is
needed to settle an intent or an edge question.

Style and architecture are not derivation findings and are never absorbed into
the spec, so they are read directly. `architecture.md` in particular carries
the rules that decide where code goes (A/B/C/D placement, leaf-module
boundaries): a spec states what a module does, not how it must be shaped, so
that cannot be restated per change. This is the same set the pass-2 reviewer
checks, so the implementer's inputs and the release gate name the same rules.