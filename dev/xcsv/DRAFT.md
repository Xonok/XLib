# xcsv — DRAFT

**A working document, not the spec.** It holds the intent, so a discussion has
something to push against. The spec is derived from this afterwards.

- Everything under **Intent** is the human's: carried from the 2026-10-25
	request and from the existing `SPEC.md`, with wording left as written. Small
	edits only — headings, tables, list markers. Nothing rephrased. Where a
	section is the agent's restatement rather than carried text, it says so.
- Everything under **Open questions** is the agent's. None of it is decided.

**Status:** paused for the human's decisions, deferred 2026-10-25. No code has
been written; `dev/xcsv/xcsv.py` and `dev/xcsv/SPEC.md` are untouched. Each
question is decision-ready: the measured current behaviour, the options, and
the agent's recommendation.

## Decisions at a glance

| # | Decision | Recommendation | Your decision |
|---|----------|----------------|---------------|
| Q1 | Public schema form | A — list-only | |
| Q2 | `read_line` comment/blank lines | A — return `(None, next_offset)`, drop `discard_comments` | |
| Q3 | Writer return values | A — line for single, count for bulk | |
| Q4 | Short-row failure | A — `UnfinishedLineError` | |
| Q5 | `None` vs `""` round-trip | A if the distinction is real, else B — **your call** | |
| Q6 | `parse_all(reschema=True)` | A — keep the flat list and its warning | |
| Q7 | `IOError` name | A — rename to `CSVIOError` | |
| Q8 | Tuple API removal at 2_0_0 | A — remove outright, with a recorded versioning exception — **your call** | |
| Q9 | Tokenizer open questions | Leave for later | |

## If you want the short path

Accept the recommendations for Q1–Q4, Q6, Q7 and Q9. Two still need you:

- **Q5** is the data-model call: does an explicit empty value mean something
	different from an absent field? If yes, A; if no, B.
- **Q8** is a repo-rule exception: removing the tuple API at 2_0_0 is one major
	earlier than `doc/versioning.md` allows. Say "yes, exception" or choose the
	deprecation window (B).

With those answered, the rest is a bounded rewrite: `xcsv.py`, the two `_/`
modules, the tests and the spec. No new features, no release.

## How to pick this up

1. Fill the *Your decision* column above, or edit the `Decision:` line under a
	question below. A one-word answer ("Q5 B") is enough.
2. Tell the agent the decisions are in. It derives `SPEC.md` from this draft,
	with numbered requirements citing the questions, and archives the old spec
	as `SPEC_1_1_0.md` (the default; say if you want it rewritten in place).
3. Tests, implementation, review. Nothing is released until you ask.

## Status

- `dev/xcsv/DRAFT.md` — this document; complete and awaiting decisions.
- `dev/xcsv/SPEC.md` — the old AI-written 1_1_0 spec; untouched.
- `dev/xcsv/xcsv.py` — the 1_1_0-shaped dev API; untouched.
- Ticket `TSKP7D0` (Todo, `human-input-needed`); this draft and the convention
	merged as `ba34aad` (PR #98). No branch or worktree is open; the next work
	starts from master.
- Released `xlib/xcsv_1_1_0.py` — untouched.

## Intent

### What xcsv is

(carried from `SPEC.md` — confirm or reword)

**xcsv** is a CSV library with `//` comment support, quoting, and a simple
tokenizer/serializer. Header-ignoring is the default; header-aware reads and
writes are a layer on top.

**Schema representation**: a list of header names, where position in the list is
the column index. The dict form `{name: index}` is internal only, for fast
lookup.

It is being built for append-only log databases (logdb), where the file is a
log: each line is a row, comments are skipped, and a schema change is written as
a `__reschema__` row.

### Why this change

(verbatim from the 2026-10-25 request)

- Errors-as-values puts undue burden on ordinary usage. Switch to ordinary
	exceptions.
- API file(xcsv.py) should be focused on what it takes to use the API, not
	explain internal details that aren't immediately needed.
- Having some documentation in the API file is good, if it directly helps with
	using it, by for example mentioning a crucial "why".
- No comments inside the rebind wrappers in API file.
- No functions defined in API file, except if they are the rebind wrappers.

### What the API file becomes

(agent's restatement of the five points — confirm or replace)

`xcsv.py` is the public surface and nothing else:

- a module docstring about using the library, not about how it is implemented;
- the exception names the library publishes;
- one thin rebind wrapper per public function, forwarding to its definition in
	`_/`.

It defines no other functions. It has no comments inside the wrappers. A
docstring on a wrapper is allowed where it tells the caller something the name
does not — the comment rules and the `parse_all` reschema warning are the
examples.

### Scope

(carried from the request and the 2026-10-25 reshape — confirm or reword)

In scope: the 2_0_0 API cleanup; errors raised instead of returned; the API file
facade; the tests updated to the new contract; a `SPEC.md` derived from this
draft.

Out of scope: new features; Stage 3 (`file_reader`, `file_writer`,
`file_writer_open`); KV mode; multiline quoted fields; encoding detection;
concurrent writers; a release. `xlib/xcsv_1_1_0.py` stays untouched.

### Compatibility

(carried from the discussion — the ruling is Q8)

`1_1_0` is the released API. `2_0_0` removes the `(result, error)` tuple and the
`raise_errors` parameter, so it is a breaking release. Nothing in the tree
consumes xcsv outside `dev/xcsv` and `xlib_dev`; the released file remains as
the 1_1_0 contract.

`doc/versioning.md` now says deprecations are dropped at the next major
release, so removing both at 2_0_0 is no longer early — it is the policy.

## Open questions

Facts below are measured against `dev/xcsv` after the 2026-10-25 reshape. None
of the options is chosen.

### Q1 — Is the public schema a list only, or does the dict form stay?

Current: `schema_parse(header, as_list=False)` returns `{col: index}` by
default; `as_list=True` returns the list. `parse_line`, `parse_all`,
`write_entry` and `write_entries` accept either form through
`normalize_schema`. The SPEC says the list is preferred and the dict is internal
only; the dual support was a 1_1_0 migration step, with dict removal planned for
2_0_0.

Options:

A. List-only in 2_0_0. `schema_parse` returns `list[str]`; `as_list`
	disappears; the four schema functions accept only `list[str]`;
	`normalize_schema` can still build a dict internally. Smallest surface, and
	it matches the stated representation. Breaks callers that pass a dict or
	index a parsed schema by name.
B. Keep both for 2_0_0. Every schema parameter stays
	`list[str] | dict[str, int]`, and `as_list` stays. Smaller break, more
	surface, and the dict remains a second public form.
C. Make the dict the only form. Contradicts the stated representation; listed
	for completeness.

Agent recommendation: A. It removes `as_list` and the union from five
signatures, and the dict was only ever a lookup shape.

**Decision:** _open — deferred 2026-10-25._

### Q2 — What does `read_line` do with a comment or blank line?

Current: `read_line(path, offset=0, discard_comments=True)` returns
`(None, next_offset)` for a comment, a blank line, and EOF. The
`discard_comments` flag has no effect: both values take the same branch. The
docstring says "Comments return (None, next_offset) if not discarded", which
suggests the flag was meant to skip them.

Options:

A. Always return `(None, next_offset)`; drop `discard_comments` from
	`read_line`. The caller sees a `None` row and decides. `read_all` keeps its
	flag, which does work.
B. `discard_comments=True` skips forward to the next data line, returning it and
	its offset; `False` returns `(None, next_offset)`. Useful for streaming;
	changes the offset contract and makes EOF distinguishable only by the
	unchanged offset.
C. Keep the no-op parameter for signature compatibility.

Agent recommendation: A. A flag that changes nothing is worse than no flag, and
`read_all` covers the "skip comments" reading for whole files.

**Decision:** _open — deferred 2026-10-25._

### Q3 — What do the writers return?

Current: `write_line` returns the line; `write_line_tokens` returns `None`
although it calls the same internal function; `write_entry` returns the line;
`write_all` and `write_entries` return the count.

Options:

A. Single-row writers return the line written; bulk writers return the count.
	`write_line_tokens` is aligned with `write_line`.
B. All writers return `None`; callers that need the line serialize first.
C. All writers return a count (`1` for a single row).

Agent recommendation: A. It is the existing contract except for the one
inconsistency, and the values are already computed.

**Decision:** _open — deferred 2026-10-25._

### Q4 — Is a short row a distinct failure?

Current: `UnfinishedLineError` is declared and never raised. A row with fewer
fields than the schema raises `SchemaError("field count mismatch...")`; so does
a row with more fields, unless `allow_unfinished` is set (which suppresses
both).

Options:

A. Raise `UnfinishedLineError` when there are fewer tokens than schema fields
	and `allow_unfinished` is false; keep `SchemaError` for too many fields.
	Matches the class name and the old SPEC's definition.
B. Delete `UnfinishedLineError`; every count mismatch is `SchemaError`.
C. Keep the class as a future alias.

Agent recommendation: A. The class exists for this distinction; either use it
or remove it.

**Decision:** _open — deferred 2026-10-25._

### Q5 — Is `None` vs `""` meant to survive a round-trip?

Current: the tokenizer distinguishes an unquoted empty field (`None`) from a
quoted empty string (`""`). The serializer writes both as an unquoted empty
field, so the distinction is lost on a round-trip: a written `""` reads back as
`None`.

Options:

A. Keep the distinction and preserve it: serialize `""` as `""` (quoted) and
	`None` as empty, so a round-trip is lossless.
B. Treat them as the same value: tokenize `""` as `None` too; document that an
	empty field has one representation.
C. Keep the current asymmetry; document it as a known limitation.

Agent recommendation: A if the distinction is real for logdb (an explicit empty
value is different from an absent one); otherwise B. This is the human's call
about the data model, not a coding preference.

**Decision:** _open — deferred 2026-10-25._

### Q6 — What is `parse_all(reschema=True)` meant to return?

Current: it accepts `__reschema__` rows, updates the schema from that point on,
and returns one flat list; entries before and after a reschema row have
different schemas. `reschema=False` raises `ReschemaError` on the row.

Options:

A. Keep the flat list and document the mixed schemas (the current SPEC has a
	WARNING). Least change.
B. Return `(entries, final_schema)` or a list of `(schema, entry)` pairs, so
	the schema travels with the row.
C. Reject reschema rows in `parse_all` always; reschema belongs to the Stage 3
	`file_reader`, which tracks the schema across a tail.
D. Return the entries plus the reschema positions.

Agent recommendation: A for this pass (no feature change; the warning is
honest), with C as the Stage 3 direction. If the mixed list is a footgun the
human wants gone now, B is the smallest replacement.

**Decision:** _open — deferred 2026-10-25._

### Q7 — Does `IOError` keep its name?

Current: `xcsv.IOError` is a `CSVError` subclass and shadows the builtin in any
module that imports it. The internal modules catch `OSError` explicitly, so the
shadowing is a caller-facing papercut, not an internal bug.

Options:

A. Rename to `CSVIOError` (consistent with `CSVError`) while the API is
	breaking anyway.
B. Keep `IOError`; callers import it explicitly and the docstring says so.
C. Use a builtin (`OSError`) instead of a library class; loses the common
	`CSVError` catch.

Agent recommendation: A if the break is cheap (no known consumers), otherwise
B. Not part of the five rules; raised because the major is the cheap moment.

**Decision:** _open — deferred 2026-10-25._

### Q8 — Does 2_0_0 remove the tuple API outright, or keep a deprecation window?

Options:

A. Remove `raise_errors` and the tuple return at 2_0_0. One clean break; one
	major earlier than `doc/versioning.md`'s two-major rule.
B. 2_0_0 makes exceptions the default and keeps `raise_errors=False` as the
	deprecated opt-out; 3_0_0 removes it. Follows the rule; leaves the tuple
	path in every signature for two more majors.
C. Keep tuples forever.

Agent recommendation: A, as an explicit, recorded exception to the versioning
rule, because the tuple path is the burden being removed and there are no known
consumers. The human has to rule the exception; the agent cannot.

**Decision:** _open — deferred 2026-10-25._

### Q9 — Tokenizer semantics still open from the old SPEC

These were carried in the old SPEC and are still unsettled:

1. **Multiline quoted fields, or strictly line-based?** Line-based keeps the
	"a log is human-readable" property; that is the leaning, not a ruling.
2. **A comment line inside a quoted row** must be data, not a comment. The
	semantics of that case are undecided.

Agent recommendation: leave both out of 2_0_0; they are tokenizer behaviour,
not API shape. Record them as future work in the derived SPEC.

**Decision:** _open — deferred 2026-10-25._

## What this draft has to settle before the spec

- Q1–Q8: the public contract and the versioning ruling.
- Q9: whether the tokenizer questions stay future work.
- The old `SPEC.md` is archived as `SPEC_1_1_0.md` by default; say if you want
	it rewritten in place.
