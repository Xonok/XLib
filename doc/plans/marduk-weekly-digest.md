# Marduk weekly world-news digest

## Goal

One news item a week — two only when a second is clearly exceptional — that is
the thing worth knowing from the world's news. Noise is the default: if it will
not matter in a week, it is not shown. "Nothing this week" is a valid result and
must be allowed, or the digest manufactures importance.

This is a Marduk source (`kind: "digest"`), not a change to the panel core. It
is Track 1 work: this draft and a spec, with the judgement reviewed before code.

## What exists to build on

- A source returns a complete list of conditions each run; the store turns a
	state change into a news item (`tools/marduk/_/event.py:transition`).
- The models feed already emits events rather than health: a new key in `info`
	is one news item, and a key the source stops returning is dropped silently
	— no "recovered" item (`tools/marduk/_/store.py:apply`).
- No source calls a model yet, and there is no budget or spend mechanism.

## Requirements

- **Weekly schedule.** `interval_seconds` defaults to 604800;
	`stale_after_seconds` defaults to twice the interval plus a day, so a normal
	quiet week is not "stale". R6 in `tools/marduk/SPEC.md` already allows a
	source whose silence is long to declare this.
- **Candidates.** Fetch a configured set of RSS/Atom feeds, keep title,
	summary, link, source and published time, and cap at `max_candidates`
	(default 60) by recency. A feed that fails is a source error, not a quiet
	week.
- **One model call, fixed brief.** At most two items; JSON output validated. A
	malformed answer is a source error — the last conditions stay — never a
	silent "nothing".
- **Quiet week.** Return `[]`. The feed footer still shows the age of the last
	successful run, so a quiet week is distinguishable from a dead digest.
- **No core change.** Everything is expressible with the existing source
	contract; no new store field beyond `memory`.

## News mechanics

One condition per item, key `digest:<ISO-year>-W<week>:<n>`, state `info`. The
title is the one line; the detail is the "why it matters" sentence plus the
link. A re-run in the same ISO week reuses the key, so the same week cannot
double-post; a new week produces a new key, which is first-seen `info` and one
news item. A quiet week returns `[]` and the old key is dropped silently
(`store.apply` deletes keys a source no longer returns). The digest therefore
needs no first-run seed: unlike a catalogue, its first run should announce the
current week rather than the archive.

`memory` holds `last_week` and the month-to-date spend. If the ISO week is the
same as `last_week`, the source returns `[]` before fetching or calling the
model — this covers a restart mid-week.

## Prompt brief

Input is a numbered list of candidates: title, source, published time, summary
(capped). The brief asks for at most two items that will still matter in a
week, and for the second only when it is clearly exceptional. It prefers
structural change — war, election, disaster, economy, law — over routine
politics, sport, celebrity and market noise. It must return no items when
nothing qualifies.

Output shape:

```json
{"items": [{"candidate": 12, "title": "one line", "why": "one sentence"}]}
```

Validation: candidate in range, at most two items, non-empty title and why,
length caps. Any other shape is a source error.

## Cost and transport

The panel must not spend silently, so the source has no default route and no
default budget.

- **Config.** `feeds` (objects with `name` and `url`), `route` (provider/model),
	`api_key_env`, `monthly_budget_usd`, `max_cost_usd_per_run`,
	`max_output_tokens`, `timeout_seconds`.
- **No route, no key, or no budget is a visible source error**, not a zero-cost
	run. The feed line says which is missing.
- **Spend is tracked in `memory`**: month, month-to-date estimate, and the last
	call's tokens. Before a call, the worst-case cost (prompt estimate plus
	`max_output_tokens` at the route's output price) is compared with the
	remaining monthly budget and `max_cost_usd_per_run`; if it would exceed
	either, the run fails visibly and nothing is sent.
- **Transport options.** (a) Direct OpenRouter chat-completions over HTTPS with
	an explicit `api_key_env`; it returns usage and needs no session. (b)
	`opencode run --format json --model <route>`, which reuses the machine's
	provider auth but creates a session and leaves the cost to be estimated from
	token counts. **Recommendation: (a)** for a background panel — one fixed
	request, no session, an explicit key. (b) is the fallback if the human would
	rather not put a key in the panel's environment.
- **Spend row.** The source declares one health row, `digest spend`, showing
	`$spent / $budget this month`; it is `ok` normally and `warn` above 80%. That
	is how the panel shows the cost without a separate UI.

## Test plan

- Fixture weeks with a stub model: quiet, one major story, two exceptional, and
	a noisy week of minor items; assert 0/1/2 conditions and their keys.
- Same-week re-run adds no item; a new week adds exactly one key per item.
- A malformed model answer and a failed feed are source errors, and the last
	conditions stay.
- Budget: a month at the cap refuses the next call before sending; the panel
	records the error and does not spend.
- Live judgement: run over four archived weeks of feed snapshots and compare
	with the human's picks. The human is the judge; a "nothing" week must be
	allowed to pass. The prompt is part of the artefact, so a prompt change gets
	a fixture change.

## Open decisions

- **Feed set.** Proposed live set: BBC World, The Guardian World, Al Jazeera
	(all three returned 200 on 2026-10-29); AP's RSS returned 403, so it is out
	unless a working feed is found.
- **Route, budget and key.** Which model, which monthly cap, and whether the
	key lives in the environment or in an OpenCode route.
- **Transport.** Direct OpenRouter (recommended) or `opencode run`.
- **Two-item rule.** Hard cap of two, or two only when the model marks both as
	exceptional? The brief can enforce either; the first is simpler.
- **Spend row.** Keep the health row, or show spend only in the feed error text
	when a budget blocks a run.

## Out of scope

- Reusing the modelbench harness. This is a Marduk source; a shared route
	helper can come later if a second caller appears.
- Interaction, dismissal and acknowledgement (R11).
- A longer weekly summary; the output is one line and one line of why.
