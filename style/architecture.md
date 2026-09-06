# Architecture

Cross-language rules for how the system is put together (maintainability).
Legibility-only rules live in `style/common.md`; this file is about the shape
of the system, not the look of the code.

## Goal

Compress as much code as possible into verifiable leaves, and keep the wiring
between them small — the wiring is where the difficult bugs condense. The
system should read as pipes connecting mostly self-sufficient modules: close
to a microservice composition, except the "services" are libraries.

## Four kinds of code

- **A — control/connection**: decides what happens, when, in what order, and
  connects subsystems. Lives near the top (main, init, schedule, tick) and
  stays small. A connects pipes with bounded fan-out; it doesn't drain them.
- **B — IO leaf**: moves data in and out (files, network, external systems),
  has no domain decisions, and is generic enough to reuse.
- **C — generic leaf**: purely functional computation with no domain meaning —
  reusable across projects.
- **D — bespoke domain leaf**: purely functional computation with domain
  meaning, but for one project's world. Still a library, but it lives in the
  project that uses it, not in shared tooling like XLib.

## R1 — Leaves are leaves

A library is a leaf node. It never drives the system: no orchestration, no
decisions about order or timing, no reaching for what it wasn't handed, and no
domain decisions — unless the decision is the leaf's actual point. D's entire
point is one project's domain decisions; C makes none. Check (review): a leaf
calling a non-leaf, or a library deciding system order/timing, is a violation.

## R2 — Classify, don't loophole

New code is classified A, B, C, or D. If a function can't be labeled cleanly,
that is a signal to refactor it, not a loophole in the system. The C/D split
must be honest: code that is really one project's domain logic is D, not a
generic C that happens to live in shared tooling.

## R3 — Data flows down, nothing reaches in

Call direction: control may call anything; leaves call only leaves. A module's
boundary is data in, data out, structured errors. No reach into another
module's internals; no shared mutable globals across modules. Check (linter):
call-graph edges leaf→non-leaf; cross-module mutable state.

## R4 — Few big pipes, bounded fan-out

A connects pipes; the transport owns its machinery (queues, drains
internally). The number of pipes A touches in one place stays small — "too
many pipes" is the smell that A has grown past its role. Prefer few, large,
self-sufficient modules over many small ones: complexity doesn't vanish at
boundaries, it moves there, so keep the boundary count small.

## R5 — No second implementation without arguing the fork

When a new context needs something similar, the change goes into the existing
system — parameter, config, backend, hook. A second implementation is legal
only with an argued case, filed in the module's SPEC.md decisions (or plans/*
for cross-cutting). The case must firmly establish that the existing system
can't and won't support the use case. Absent that, the second implementation
is a defect.

## R6 — Same-intent test

If all copies of some logic can be described by one spec plus context
parameters, it is one system, and the copies are a bookkeeping defect — not
separate systems. The differences between near-copies are usually context and
usage drift, not limits of the intent. POST vs websocket is one request
semantic with a transport choice: plumbing, not two codepaths.

## R7 — Meet the catalog before writing

Before generating new code, find what already exists (SPEC.md in each library,
plans/* for cross-cutting): reusing or generalizing beats writing. A
near-parallel of existing logic is a violation unless R5's argued fork applies.
This matters doubly for AI: a model doesn't carry the codebase in memory, so
it naturally forks when given one pattern in a new context.

## Handed-in IO

Domain code may do IO, but it doesn't go looking for it. Control code passes
in the ways of doing it, per the domain code's own API; within what it was
given, the domain code governs itself. Example: a D library for command
handling knows nothing about IO or networking — it accepts a single command
with its arguments, or a stream in the context of a session. The
POST/websocket difference then shrinks to plumbing routed through whatever
handles HTTP generally. The HTTP handling is itself a toolkit (B/C) that
control code uses to build the actual server; where it makes sense to combine
transport parts, that module is a D, built from the same parts and living in
the project.

## Checking

Review checklist items first; linter support where it is cheap today:
call-graph leaf→non-leaf edges, cross-module mutable state, near-duplicate
pattern scan.

Open item: the repo-level index of modules/patterns for R7 is not yet decided.