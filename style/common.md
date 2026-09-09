# Common style

Language-independent legibility rules for this repo. How the system is put
together (placement, modules, fork control) is `style/architecture.md`;
language-specific rules live in `style/<language>.md` (currently
`style/python.md`).

## Maps

- Every library keeps a short map — `SPEC.md`, in the library's dev folder —
  covering module structure, data flow, key invariants, and design decisions,
  in the style of `plans/bundler.md`'s pipeline map. Aim for well under 100
  lines. It describes how things work, not what each line does.
- The map describes current intent only. Future changes go in the spec's
  "Planned changes" section, or in `plans/*.md` for cross-cutting/roadmap
  work; never in the map.
- The spec stays current with the code: a change to module structure or a key
  invariant updates the spec in the same pass (see the legibility pass).
- A file that is not trivially readable at a glance opens with either an
  orchestrator function that calls well-named helpers, or a short header map of
  its own structure.
- The orchestrator is the first function in the file; everything after it is
  ordered by first encounter/reference. Per-file only, never a global check.
- Endless tiny helpers are clutter: if the map reads as a table of contents of
  one-line functions, consolidate.

## Failures are part of the contract

- Guard clauses come first; an `if` without an `else` is usually an early
  return.
- The null check belongs to the function that accepts the argument, not to its
  callers. Don't pass values a function must reject.
- Prefer visible outcomes over silent ones: `(result, error)` tuples or clear
  raises. Code that receives untrusted input starts with sanity checks and
  returns or raises when they fail.

## Document non-obvious returns

- Say what a function returns when that isn't obvious from the code: `None`
  semantics, tuple shapes, the `(result, error)` convention. One line.
- Deliberately chosen `None`/empty results are stated, not left implied.
- Obvious functions get nothing.

## Structure prefers one direct pass

- Prefer a single direct pass over parallel machinery; a design that needs
  several parallel representations of the same data is a smell to reduce, not
  a given.
- Don't wrap procedural code in a class purely to group functions; state flows
  through arguments, not through attributes set before a call.
- A file that does "too many things" is split into parts (see the API/internal
  split in `AGENTS.md`) or into a separate library.

## Compatibility is the default

- Code works on both Linux and Windows. Read files with newline handling (text
  mode / universal newlines); never split text on `\n` alone.
- Where a library parses lines or strings, the tests include a CRLF-garbled
  fixture.

## Factor out repetitive or hard-to-read patterns

- When the same logic appears multiple times, or when a block of code requires
  mental parsing to understand its intent, extract it into a well-named function
  or variable. The name should express *what* it does, not *how*.
- Example: if a tokenizer repeatedly checks `i < line_len and line[i] == ","`,
  factor that into `peek_char()` or `at_comma()`. The calling code becomes
  self-documenting: `if at_comma(): ...` vs. the raw condition.
- This applies to conditions, loop bodies, token/character inspection, and
  error-message construction. A pattern repeated ≥2 times is a candidate; a
  pattern that takes >5 seconds to read is a candidate even once.

## Legibility pass

- Non-trivial code isn't done until a legibility pass: the map is current,
  names follow the naming rules, non-obvious returns are documented.
- Unreadable code is a defect in the code: rewrite it, don't add a summary on
  top. AI-written code needs human review; finding a file hard to follow is a
  symptom to fix in the code, not a reason to shrink the review.