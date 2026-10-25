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
| The spec | its own file, derived from the human's draft | the ticket description |
| Shape | goal → requirements → decisions, as below | same three parts, in the description |
| Tests | derived by the reviewer before code exists | written by the implementing agent, if the ticket calls for them |
| Review | pass 2, by the reviewer | the pull request |

**The boundary rule:** if the human would write the intent down himself, it is
track 1. If the goal, scope and acceptance fit in a ticket description, it is
track 2.

Track 2 is the default because track 1 costs a human-confirmed draft and a
second agent per ticket, and that is not worth paying for a fix whose whole
scope fits in a paragraph. What track 2 gives up is the forcing function — the
human thinking a design through by writing it down — so the human still
approves the description before the agent starts, which is the same thinking at
a smaller size.

Neither track is exempt from the rules below. The conflict rule, the silence
rule and the style/architecture rules apply to both; track 2 changes where the
spec lives, not what an agent may decide alone.

## Draft and spec

Work that needs a spec starts from a **draft**, and the spec is derived from it.
The draft is the human's intent; the spec is the encoding.

- **`DRAFT.md`** — a working document, not the spec. Everything under *Intent*
	is the human's: the agent carries their wording from the request and from
	earlier documents, marks what is carried but unconfirmed, and edits only
	structure. Everything under *Open questions* is the agent's; none of it is
	decided. A settled question stays in the draft with its answer and what it
	supersedes, so the disagreement remains visible.
- **`SPEC.md`** — AI-written unless the human writes it. Numbered requirements,
	each citing the draft section it comes from. Where the draft contradicts
	itself or an earlier answer, the spec follows the later answer and lists the
	superseded text.
- **Order** — draft → human confirms → spec → tests → implementation. Code
	follows the approved spec, not the draft.
- **Where** — next to the library or tool: `dev/<library>/DRAFT.md` or
	`tools/<tool>/DRAFT.md`, beside its `SPEC.md`.
- **Track 2** — when the ticket description already carries the whole intent and
	no discussion is needed, the ticket is the draft and no `DRAFT.md` is
	written. The split is for work whose intent has to be settled before it can
	be specified; it is not a reason to write two documents for a one-line fix.

The pattern comes from `tools/pybundle/DRAFT.md` → `tools/pybundle/SPEC.md`;
`dev/xcsv/DRAFT.md` is the first library use.

## The board

Both tracks are tracked on the epiq board, one ticket per independent piece of
work, on its own feature branch — see *Working on a ticket* in `AGENTS.md` for
the lanes and the commit rules. A track-1 piece is usually several tickets,
one per stage, because a stage that takes days and a stage that takes twenty
minutes are not the same thing to review.

A track-1 draft and spec may be written by hand as before; an agent moves and
tags the ticket as the stage progresses. When the agent derives them, the human
confirms the draft and approves the spec.

## Pipeline

Seven stages, each entered on the human's call (agents never advance on their own):

| # | Stage | Who | Input | Output |
|---|-------|-----|-------|--------|
| 1 | Plan | planner (+ human) | intent | plan: reference for the draft |
| 2 | Draft | agent, from the plan and the request; human confirms | plan + intent | draft: the human's intent, open questions |
| 3 | Spec | agent, from the confirmed draft | draft | spec: goal + requirements + decisions |
| 4 | Tests | reviewer, pass 1 | spec | tests built from the spec; spec flaws reported |
| — | Spec fixes | human | reviewer's flaw list | spec v+n; iterate 4 → 3 until tests build clean |
| 5 | Implementation | programmer | spec + tests | implementation |
| 6 | Implementation review | reviewer, pass 2 | implementation + spec + tests | verdict — required before release/merge |

## Plan

Written by the planner with the human, **before** the draft. Its purpose is to
organize intent into a reference the human can use while writing or confirming
the draft: goal, options considered, open questions. The planner does **not**
write the draft or the spec.

## Spec

**Derived from the confirmed draft**, unless the human writes it by hand. The
draft is where the thinking is forced through; the spec is its encoding, and
the encoding is the conflict authority once approved. Structure:

1. **Goal** — one prose paragraph: why this exists.
2. **Requirements** — the technical encoding: behaviors, formulas, interfaces,
	constraints. What tests trace to. Each cites the draft section it comes from.
3. **Decisions** — numbered: choice, why, what was rejected. The choices on the
	way to the goal.

The spec is iterated: the reviewer's pass 1 surfaces flaws, the human fixes the
draft or the spec, and the loop repeats until tests derive cleanly. The finished
spec must let a fresh implementer do a good job from files alone, without
further guidance.

### Spec authorship — who may rewrite a spec

**The human owns the intent and approves the spec; authorship is what the
marker states.** The consequence is that an agent must be able to tell, from
the file alone, whether it is allowed to rewrite one. So:

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
- **A `DRAFT.md` is not a spec and carries no marker.** It is a working
	document; the human's intent in it is not a licence to rewrite the human's
	words beyond the structural edits described above.

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

**How they are run: one command.**

```
python3 tools/run_tests.py
```

Every suite in the repository, run by `xtest` — the repository's own testing
library, in `dev/xtest/`. A suite can also be run on its own:

```
python3 dev/xtest/xtest.py tools/xlint/test     # a folder
python3 dev/xtest/xtest.py tools/xlint/test/test_xlint.py   # one file
```

**A test file that cannot be run is a test file that does not exist**, and one
that cannot be run by the obvious command is worse than one that fails loudly:
it reports success over content it never examined. Five suites were in that
state on 2026-10-20 — `tools/test/test_epiq_pending.py`, `dev/xconf`,
`dev/xschema` and xtest's own two — and every one of them exited 0 having run
nothing. `tools/test/test_suites.py` now pins the shape that keeps it from
happening again: every test file is in a suite the runner knows about, and
every test file can be run on its own.

**A test's style is not a reason for it not to run.** The suites are written in
two styles — plain functions and `unittest.TestCase` classes — and xtest runs
both.

### The xtest decision

**Standardising on xtest means eventually using only xtest.** The suites that
are still in unittest's idiom are a migration, not a second standard. Two
rules carry that, and they are the rules to quote when the question comes up:

- **Rewrite to xtest if it gets in the way.** A suite written in unittest's
	idiom is not a reason to keep it there: when a test needs something xtest
	cannot do, **xtest grows**. That is what happened once already — xtest
	learned to run `unittest.TestCase` classes rather than the suites being
	rewritten first, and the runner grew for it. The end state is one testing
	solution, not two.
- **Always write new tests with xtest.** Never start a new `unittest` suite in
	this repository. A plain function, or a method of an `xtest.TestCase` when
	there is setup to do.

The human's ruling, 2026-10-20: *"Standardize on xtest means eventually using
only xtest. Avoiding a full rewrite is reasonable, but the decision should be
tagged as 'rewrite to xtest if it gets in the way' and 'always write new tests
with xtest'. This way the dogfooding works and won't turn into two parallel
systems."*

Example of the gap discipline in practice: a design note for a game in the
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

- **Conflict rule**: a test that disagrees with the spec is wrong — the spec
	encodes the human's intent (through the draft), the test encodes the spec.
	Back to the reviewer. The programmer never silently changes a test to fit
	code; it flags the conflict.
- **Silence rule**: where tests are silent, the spec decides. Where the spec is
	also silent, that is a flaw — back to the human, not invented by the
	implementer.
- **Separation**: the reviewer writes tests and the programmer writes
	implementation — never the same agent doing both, never one combined session.
- **Spec ownership**: see *Spec authorship* above. An agent about to edit a spec
	must check the marker first; an unmarked spec is the human's and is off
	limits unless the human asked for that edit.

## Hooks

**The hooks are symlinked, not copied.** `tools/hooks/install.sh` puts a link in
the shared git directory — where git looks, from the main checkout and from
every worktree alike — pointing at `tools/hooks/`. **A change to a hook is live
at once**: there is no install step, and the running hook cannot be older than
the source.

`pre-commit` is the exception, and it is a regular file: it is **the guard**. A
link whose source is missing is a gate that does not run, and git says nothing
at all about it — not even the hint it gives for a hook that is not executable.
That is the failure mode this repository has been bitten by twice (`2X3PZT3`: the
hook does not run and nothing says so), so the guard checks that every link in
the hooks directory resolves, fails loudly with the fix if one does not, and
then runs the style gate itself.

The style gate does not assume `xlint` lives in the checkout it is guarding. It
takes `$XLIB/tools/xlint/xlint.py` when `XLIB` is set, then this repository's
`tools/xlint/xlint.py`, then the installed `xlint` on `PATH` (XLib's `install.sh`
links it into `~/.local/bin`). If none exists it refuses the commit and says how
to install the tools, rather than passing an unchecked commit as clean.

So a hook change needs no step to become live. What it needs is for its link to
resolve — and the guard is what says so when it does not:

```
ERROR: commit-msg is a dangling symlink, so that hook will not run.
       Re-install the hooks: sh tools/hooks/install.sh
```

The install is per machine and untracked, so it is a step an agent performs
rather than something a merge can do — but it is needed only to **create** the
links, not to refresh them. The link is relative, so it survives the repository
being moved.

## Handoff (the implementer's contract)

The programmer works from these inputs, and no others:

1. spec (derived from the confirmed draft, iterated until it survived test derivation)
2. tests (edges explicit)
3. the project guidelines in `doc/style/` — always `architecture.md` and
	`common.md`, plus the language-specific file for the language in hand
	(`python.md`, `js.md`, `html.md`, `markdown.md`)

The spec has already absorbed all flaws found during test derivation as the
human's fixes, so it is the complete resolution *of those* — no third file is
needed to settle an intent or an edge question.

Style and architecture are not derivation findings and are never absorbed into
the spec, so they are read directly. `architecture.md` in particular carries
the rules that decide where code goes (A/B/C/D placement, leaf-module
boundaries): a spec states what a module does, not how it must be shaped, so
that cannot be restated per change. This is the same set the pass-2 reviewer
checks, so the implementer's inputs and the release gate name the same rules.
