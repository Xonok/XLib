# Skynet — quota in the first line — DRAFT

**A working document, not the spec.** It holds the intent and the measured
limits, so a discussion has something to push against. The spec is derived from
this afterwards.

- Everything under **Intent** is the human's, carried from the 2026-10-26
	request. Wording is left as written; only headings and list markers changed.
- Everything under **Open questions** is the agent's. The human's decisions are
	recorded at the end of each question and in the table above.
- The measurements below were taken on 2026-10-26 between 00:52 and 02:57
	Europe/Helsinki, against the live account and database on this machine.

**Status:** decisions recorded 2026-10-26; `tools/skynet/SPEC.md` is derived
from this draft. Docs merged as `317345f` (PR #102); ticket `ENXZ4WY` is in
Todo. No code has been written; neither `tools/skynet.py` nor its tests are
touched.

## Decisions at a glance

| # | Decision | Recommendation | Your decision |
|---|----------|----------------|---------------|
| Q1 | Auth token handling | Read-only. Show `Go ?` when the token is rejected; do not refresh or write credentials. | **A** |
| Q2 | "Today" baseline | Persist the meter reading at midnight (UTC, per the 2026-10-26 follow-up); show `today ?` when no baseline exists. | **A** |
| Q3 | State location | `~/.local/share/skynet/quota.json`. | **A** |
| Q4 | Width fallback | Drop whole fields right-to-left: `OR`, `today`, `pace`, then shorten the Go field. | **B — abbreviate first, then drop** |
| Q5 | Free usage | Keep it internal; do not add a free counter to the first line. | **A** |
| Q6 | OpenRouter day | Use the API's UTC-day counter as-is; do not re-derive a local day. | **A** |
| Q7 | Quota source | Provider counters only. The local database is used for the day baseline, never for quota dollars. | **A** |
| Q8 | API failure | `?` for a source that exists but cannot be read; omit a source that is not configured. | **A** |
| Q9 | Code layout | Keep `skynet.py` a single file. | **A** |
| Q10 | 5-hour and week meters | Do not show them on the first line. They are available in the response if wanted later. | **A** |

## Intent

(verbatim, 2026-10-26)

> I want the panel to contain extra information in the very first line. A couple things:
>
> - Opencode go quota used in dollars and percentage
> - Overall pace so far, in percentage per day since last reset. 200% means I'm spending it twice as fast as it regenerates, so will run out when the month is half done.
> - Current day's pace, in percentage per day until last reset. 200% means the same, except it's about the current day instead of the average since the last reset. Essentially, if I keep this at 100% I'll run out exactly when the limit resets.
>
> A similar feature would make sense for openrouter, but easier since it's daily: requests/1000 spent.
>
> Logically both the Go and openrouter trackers should keep track of when some usage is free, for example due to a promotion.
>
> What's unclear is the limitations of it all and what needs to be put in place so these features could be implemented.

## What the display would look like

The first line today is `=== Skynet ===`. With all sources available and enough
room, it uses the full form:

```
=== Skynet === Go $1.87/$60 3% · pace 72%/d · today 94%/d · OR 29/1000
```

That is 70 columns, and it is right-aligned against the pane width: the space
after the title absorbs the spare columns, so the quota block reads as
separate from the `=== Skynet ===` title. The sample shows the minimum width,
where the gap is one space. When it does not fit, the line first switches to
the abbreviated form, which keeps every field:

```
=== Skynet === G $1.87/60 3% · p 72 · t 94 · OR 29/1000
```

That is 56 columns. `G` is Go, `p` is pace and `t` is today; `OR` is already
short. Only when the abbreviated form does not fit are fields dropped, from the
right:

| Width | Line |
|------:|------|
| 70+ | full form |
| 56–69 | abbreviated form |
| 43–55 | `=== Skynet === G $1.87/60 3% · p 72 · t 94` |
| 36–42 | `=== Skynet === G $1.87/60 3% · p 72` |
| 29–35 | `=== Skynet === G $1.87/60 3%` |
| 26–28 | `=== Skynet === G $1.87 3%` |
| 19–25 | `=== Skynet === G 3%` |
| 14–18 | `=== Skynet ===` |

The boundaries are those lines' lengths; the first version of this table
counted `=== Skynet ===` as 13 columns and was one low in seven rows. Widths
below 14 are out of scope; the title itself is 14 columns.

The `%/d` in the full form means "percent of the sustainable daily rate", not
"percent of the quota used today". At 100% the current rate exhausts the quota
exactly at the reset; at 200% it exhausts it halfway through. The abbreviated
`p` and `t` keep the same meaning without the `%/d` decoration.

When the Go meter is known but the day baseline is not, `today` becomes `?`
(full form) or `t ?` (abbreviated form):

```
=== Skynet === Go $1.87/$60 3% · pace 72%/d · today ? · OR 29/1000
=== Skynet === G $1.87/60 3% · p 72 · t ? · OR 29/1000
```

## What I measured

### Go quota

- **Endpoint:** `GET https://opencode.ai/console/api/go/status`
- **Auth:** `Authorization: Bearer <access>` where `<access>` is the `access`
	field of the active `opencode` row in the local `credential` table.
- **Response:** the status object includes `product` (`go` or `go-plus`),
	`access.startsAt`, `access.endsAt`, and `access.meters` with `fiveHour`,
	`week` and `month`. Each meter has `resetsAt`, `limitMicroCents` and
	`usedMicroCents`; `fiveHour` and `week` also have `startsAt`.
- **Units:** microcents. One dollar is `100_000_000` microcents.
- **Measured values at 2026-10-26 02:56 EET:**
	- `product`: `go`
	- `access.startsAt`: `2026-10-24T16:47:40.000Z`
	- `access.endsAt`: `2026-11-24T16:47:40.000Z`
	- `month.limitMicroCents`: `6000000000` ($60)
	- `month.usedMicroCents`: `186774741` ($1.86774741)
	- `week.limitMicroCents`: `3000000000` ($30), `fiveHour.limitMicroCents`:
		`1200000000` ($12)
- **Go Plus** is the same shape with larger limits: from the console bundle,
	`go-plus` is $40/month with a `paidPeriodMicroCents` of `24000000000`
	($240), a week limit of $120 and a 5-hour limit of $48. The limits must be
	read from the response, not hardcoded.
- **The meter is not Zen list price.** For `opencode-go/deepseek-v4.1-flash`,
	two samples 63 seconds apart moved the month meter by `1_105_973`
	microcents while the local `cost` column moved by `0.01475` dollars; the
	ratio is `0.750`. Over the whole period the ratio is also `0.749`. The
	marketing page's "$80 monthly usage" for DeepSeek is `$60 / 0.75`, which is
	consistent with the meter being the discounted Go price. **Do not convert
	between the local `cost` column and the Go meter without a per-model
	calibration; use the meter.**
- **No history.** The response has the current meter values only. It ignores
	`?at=`, `?range=`, and there is no `/go/usage`, `/go/history` or
	`/go/last-hour` on the user-facing API.
- **Auth lifetime:** the active token's `expires` is `1795452425738` ms
	(2026-11-23T16:47:05Z). The credential row also carries a `refresh` token;
	the console's OAuth metadata advertises
	`https://opencode.ai/console/auth/oauth/token` with the `refresh_token`
	grant. Refresh was **not tested**, because a refresh may rotate the token
	and invalidate the copy opencode is using.

### OpenRouter

- **Endpoint:** `GET https://openrouter.ai/api/v1/key`
- **Auth:** `Authorization: Bearer <key>` where `<key>` is the `key` field of
	the active `openrouter` row in the same `credential` table.
- **Response fields used:** `free_model_daily_requests` (inside the response's
	`data` object) with `used`, `limit` and `remaining`; also `usage_daily`,
	`usage_monthly`, `usage` and `is_free_tier`.
- **Measured values at 2026-10-26 00:55Z:** `free_model_daily_requests`:
	`{"used": 29, "limit": 1000, "remaining": 971}`; `usage_daily`: `0`;
	`usage`: `1.028122676`; `is_free_tier`: `false`.
- **The counter is per key and free-models-only.** It is not "all requests".
	A paid request does not move it; `usage_daily` covers paid dollars. The
	measurement is consistent with a UTC-midnight reset: the local database held
	29 openrouter messages after UTC midnight and the API reported 29.
- **The 1000 is a daily limit, not a monthly one.** `OR 29/1000` is the
	requested "requests/1000 spent".

### Credentials

The source is the same SQLite database skynet already opens read-only:
`~/.local/share/opencode/opencode.db`, table `credential`:

```
credential(id, integration_id, label, value, connector_id, method_id,
           active, time_created, time_updated)
```

- The active Go credential is the row with `integration_id = 'opencode'` and
	`active = 1`. Its `value` is JSON with `access`, `refresh`, `expires` and
	`metadata.server` (`https://opencode.ai/console`). There are three
	`opencode` rows on this machine; exactly one has `active = 1`.
- The OpenRouter key is the row with `integration_id = 'openrouter'`. It has
	`active = NULL`, but it is the only OpenRouter row.
- Reading these values is local and read-only. The tool must never print the
	access token, refresh token or API key, including in error messages.

### One operational gotcha

Python's default `urllib` User-Agent is rejected by Cloudflare in front of the
console API:

```
Python-urllib/3.14 -> HTTP 403, body: error code: 1010
curl/8.5.0         -> HTTP 200
skynet/1.0         -> HTTP 200
```

The fetcher must set an explicit `User-Agent` (for example `skynet/1.0`). This
is not about politeness; without it every Go request fails.

## The math

Let `L` be `month.limitMicroCents`, `U` the current `month.usedMicroCents`,
`S` the period start (`access.startsAt`), `R` the period end
(`access.endsAt`), and `T` now, all in days where needed.

```
period_days   = (R - S) / 86400
sustainable   = L / period_days
used_percent  = U / L * 100
overall_pace  = (U / (T - S)) / sustainable * 100
today_pace    = ((U - U_day_start) / (T - day_start)) / sustainable * 100
```

- `overall_pace` is the average rate since the paid period started.
- `today_pace` is the rate since UTC midnight. It needs `U_day_start`, the
	meter value at UTC midnight.
- At `100%`, the rate is exactly `sustainable`; the quota reaches `L` at `R`.
- At `200%`, it reaches `L` at `S + period_days / 2`.

Measured example (2026-10-26 02:56 EET):

```
L = 6_000_000_000 microcents ($60)
U = 186_774_741 microcents ($1.86774741)
used_percent = 3.11%
S = 2026-10-24T16:47:40Z
R = 2026-11-24T16:47:40Z
period_days = 31
T - S = 1.3397 days
sustainable = $1.93548/day
overall_pace = 72.0%
```

The `today` number in the example line, `94%`, is an estimate from the local
database: the local `cost` since local midnight was `$0.2964`, and the observed
Go-to-list ratio for this model is `0.75`, giving `$0.2223` of Go spend over
`2.92` hours, or `$1.827/day` against `$1.935/day`. The exact value needs the
meter's reading at local midnight; the estimate is shown only to demonstrate
the shape of the number.

## Limitations and things that are still unclear

- **The Go endpoint is an internal console API.** It is what the console web
	app calls, not a documented public API. Its path, field names and units can
	change without notice. The design must degrade to `Go ?` rather than break
	the tables.
- **The token is an OAuth access token with an expiry.** Reading it from the
	database works until `expires`. The refresh flow exists but is untested and
	may rotate the refresh token; writing a refreshed token back to opencode's
	database is a write to another application's live DB and is not recommended.
	If skynet runs for a month without opencode refreshing the token, the Go
	field will disappear until opencode runs again.
- **The Go meter has no daily history.** "Current day's pace" needs a baseline
	from UTC midnight. The API cannot supply it retroactively. A state file
	written by skynet is the only exact source when the panel has been running;
	otherwise the day number is unavailable.
- **The period start is `access.startsAt`.** On the measured account this is
	the first paid period (2026-10-24 to 2026-11-24), so it is also the last
	reset. If the API keeps the original subscription start after a renewal
	instead of advancing it, the overall pace would divide by the wrong elapsed
	time. The fallback is to derive the start from `month.resetsAt` minus one
	month; that is untested, because the account has not renewed yet.
- **The Go meter may lag.** It moved within seconds in the measurement, but
	there is no guarantee. A pace computed from two samples a minute apart can
	be noisy; the overall pace uses a multi-day window and is stable.
- **Go dollars are not Zen dollars.** The meter is the plan's own unit, at
	`0.75×` the local list cost for DeepSeek. The ratio is model-specific; a
	model switch can change it. The first-line dollars must be the meter.
- **OpenRouter's day appears to be UTC, not local.** The counter is consistent
	with a UTC-midnight reset, which is 02:00 or 03:00 local depending on the
	season. Re-deriving a local day from the database would produce a number
	that does not correspond to the limit the provider enforces.
- **OpenRouter's counter is free-models-only.** `OR 29/1000` is not "all
	requests today"; it is the free-model request budget. Paid usage is in
	`usage_daily` and is a separate number.
- **Free usage has no nominal value in either API.** Go's `usedMicroCents`
	excludes free models; OpenRouter reports free requests separately from paid
	dollars. Neither reports what the free usage *would* have cost. If a
	"dollars saved by promotions" figure is wanted, it requires model prices
	and token arithmetic, and it is a separate feature.
- **A promotion that makes a paid model free may or may not move the free
	request counter.** The APIs are authoritative for their own counters; the
	tool should not infer the free/paid split from the local `cost` column.
- **The panel is a single file.** `install.sh` links `tools/skynet.py` into
	`~/.local/bin/skynet`. A sibling module also works through that link:
	measured in Python 3.14, `sys.path[0]` resolves to the real directory
	(`/tmp/.../real`), not the symlink's directory, and a sibling import
	succeeds. So the choice between one file and a sibling module is style, not
	an install constraint.
- **Network calls in a panel can block.** A fetch with a long timeout in the
	watch loop freezes the pane. Either use a short timeout (2–3 s) or fetch in
	a background thread and render the last good snapshot. The tool currently
	has no threads; this is a design choice, not a requirement.
- **The first line must never wrap.** A wrapped header costs a table row and
	breaks the height contract in `TERMINAL.md`. The header needs its own
	width-aware field dropping, separate from the table's column dropping.

## What needs to be put in place

1. **A quota reader in `skynet.py`.** A small data object (or dict) for a
	 source's state: `used`, `limit`, `period_start`, `period_end`,
	 `day_start_used`, `day_start`, `free_used`, `free_limit`, `error`. Two
	 readers: `read_go_quota()` and `read_openrouter_quota()`.
2. **Credential lookup.** One query against `credential` in the existing
	 read-only connection: `integration_id = 'opencode' AND active = 1`, and
	 `integration_id = 'openrouter'`. Parse the JSON `value`. Return `None` when
	 the row is missing. Do not log the values.
3. **HTTP fetch.** `urllib.request` with an explicit `User-Agent`, a timeout
	 of 2–3 s, and a catch for `HTTPError`, `URLError`, `TimeoutError`,
	 `JSONDecodeError` and `KeyError`. A failed fetch returns `None`, not an
	 exception that reaches the renderer.
4. **Go parser.** Map `access.startsAt`, `access.endsAt`,
	 `meters.month.limitMicroCents`, `meters.month.usedMicroCents`, and
	 `product`. Convert microcents with integer arithmetic
	 (`dollars = microcents / 100_000_000`). Keep the raw integers for the pace
	 math; format only at render time.
5. **OpenRouter parser.** Map `free_model_daily_requests.used` and `.limit`.
	 Keep `usage_daily` for a future field; do not put it on the first line yet.
6. **Pace functions.** Pure functions:
	 `used_percent(used, limit)`, `overall_pace(used, limit, start, end, now)`,
	 `day_pace(used, day_start_used, limit, start, end, now, day_start)`.
	 Return `None` when a denominator is zero or negative. Test them with a
	 fixed clock; no network.
7. **Day baseline state.** `~/.local/share/skynet/quota.json`, storing the
	 last meter value and the UTC date. On the first sample of a new UTC day,
	 set `day_start_used` from the previous reading if that reading is close to
	 midnight; otherwise `None`. Write atomically (write a temp file, then
	 `os.replace`). Ignore a corrupt file. Handle the meter resetting downward
	 as a new period.
8. **Header renderer.** A `quota_line(quota, width)` function that starts from
	 `=== Skynet ===`. It tries the full form first, then the abbreviated form
	 (Q4 B), then drops fields right-to-left. It must never return a line
	 longer than `width`. The table renderer gets a new optional `quota`
	 argument; `render(rows, now, height, width, quota=None)` keeps the
	 existing tests unchanged.
9. **Watch tick.** The watch loop currently redraws only when the database
	 changes or the terminal resizes. Add a `last_quota_fetch` timestamp and
	 redraw when `now - last_quota_fetch >= 60`, even if the database did not
	 change. Fetch the quota on that tick, not on every database event.
10. **One-shot mode.** Fetch once before rendering, with the same short
	 timeout. If the fetch fails, render the tables without the quota.
11. **Tests.** The tool's tests use `xtest` (`dev/xtest`). Add tests for:
	 the pace formulas at fixed times, the day rollover, the `today ?` case,
	 the missing-credential case, the 401/403 case, the Cloudflare 403 with the
	 default User-Agent (a fake fetcher), the full-to-abbreviated switch, the
	 width drop order, and the line never exceeding its width. No test should
	 touch the network or the real database.
12. **Docs.** Update `tools/skynet/TERMINAL.md` with a "Quota line" contract:
	 one line, fits the width, never wraps, fields drop right-to-left, and a
	 failed source does not remove the tables. Add a short "Data sources"
	 section to `tools/skynet/SPEC.md` if a spec is written; `CHANGES.md` is
	 not the place for it.
13. **State and permissions.** The state file is per-machine and must not be
	 tracked. If `~/.local/share/skynet/` cannot be created, the day pace is
	 `?` and the rest still works.

## Open questions

### Q1 — Auth token handling

The access token expires; the refresh token is present.

- **A (recommended).** Read-only. When the API returns 401, show `Go ?`. Let
	opencode refresh the token the next time it runs. No write to opencode's
	database, no risk of rotating a token out from under a running session.
- **B.** Refresh in-process with the `refresh_token` grant and keep the new
	token in memory only. The old refresh token may still be valid or may be
	rotated; untested.
- **C.** Refresh and write the new token back to the `credential` table. This
	keeps the panel alive indefinitely but writes to another application's live
	database and can race opencode's own refresh.

**Decision: A.** Read-only; `Go ?` on 401. Decided 2026-10-26.

### Q2 — "Today" baseline

The API has no daily history.

- **A (recommended).** Persist the meter reading across runs; on the first
	sample after local midnight, use the previous reading as `day_start_used`
	only if it is close to midnight (for example within 15 minutes). Otherwise
	show `today ?`.
- **B.** Keep it in memory only. Works while the watch runs continuously;
	every restart loses the day number until the next midnight.
- **C.** Estimate from the local database cost and a per-model calibration.
	This can show a number on a cold start but is approximate and changes when
	the model mix changes.

**Decision: A.** Persist a midnight baseline; `today ?` without one. Decided
2026-10-26.

**Follow-up 2026-10-26:** the boundary is **UTC midnight**, not local — the
human's ruling, since OpenRouter's counter and the Go `week` meter reset at
00:00Z. It supersedes "local midnight" in the options above. The Go `month`
meter resets at `access.endsAt` (16:47:40Z on 2026-11-24), so the month itself
is not a UTC-day reset; UTC is the common day boundary for the line, not the
month's reset.

### Q3 — State location

- **A (recommended).** `~/.local/share/skynet/quota.json`, beside the other
	per-machine stores (opencode, taskview).
- **B.** `~/.cache/skynet/quota.json`; disposable, but the day baseline is
	exactly the thing a cache clear destroys.
- **C.** In-memory only; then Q2 B.

**Decision: A.** `~/.local/share/skynet/quota.json`. Decided 2026-10-26.

### Q4 — Width fallback

- **A (recommended).** Drop whole fields right-to-left: `OR`, `today`, `pace`,
	then shorten the Go field from `Go $1.87/$60 3%` to `Go $1.87 3%` to
	`Go 3%`. At the narrowest, only `=== Skynet ===`.
- **B.** Abbreviate rather than drop: `G $1.87/60 3% · p 72 · t 94`. Denser,
	but harder to read and still needs a fallback.
- **C.** A second line. Does not satisfy "the very first line", and costs a
	table row.

**Decision: B.** Abbreviate first, then drop. The exact two-tier scheme and
the drop table are in *What the display would look like*. Decided 2026-10-26.

### Q5 — Free usage

- **A (recommended).** Keep it internal. The quota math already excludes free
	usage because it reads the provider counters. Do not add a free counter to
	the first line; it would crowd out the numbers the human asked for.
- **B.** Add a spelled-out free field: `· free 29` for OpenRouter or
	`· free 1.2M` tokens for Go. Requires deciding which unit.
- **C.** Put free usage in a future detail view, not the panel.

**Decision: A.** Internal only; no free counter on the first line. Decided
2026-10-26.

### Q6 — OpenRouter day boundary

- **A (recommended).** Use the API's counter as-is. It appears to reset at UTC
	midnight; the limit the provider enforces is on that day, so the panel
	should show the same day.
- **B.** Re-derive a local-day counter from the database. It will not match
	the provider's limit and can show 0/1000 while the provider still counts
	requests.
- **C.** Show both: `OR 29/1000` (API day) and a local-day count. More
	numbers than requested.

**Decision: A.** Use the API's UTC-day counter. Decided 2026-10-26.

### Q7 — Quota source

- **A (recommended).** Use the provider counters for quota dollars and
	requests. Use the local database only for the day baseline, and only because
	the API has no history.
- **B.** Compute the quota from the local `cost` column and the model prices.
	This disagrees with the Go meter by a model-specific factor (0.75 for
	DeepSeek) and would be wrong for other models.
- **C.** Show both the meter and the local-cost estimate. Two numbers that
	disagree invite the wrong one to be believed.

**Decision: A.** Provider counters only; local DB only for the day baseline.
Decided 2026-10-26.

### Q8 — API failure display

- **A (recommended).** A configured source that cannot be read shows `?`:
	`Go ?`, `OR ?`. A source that is not configured is omitted. The tables
	always render.
- **B.** Omit the field on any failure. Simpler, but looks the same as "not
	subscribed".
- **C.** Show the last known value with its age: `Go $1.87 (2m)`. More
	information, more width, and a stale value can be mistaken for current.

**Decision: A.** `?` for a configured-but-unreadable source; omit an
unconfigured one. Decided 2026-10-26.

### Q9 — Code layout

- **A (recommended).** Keep the quota code in `skynet.py`. It is one feature,
	about 150 lines, and the tool is already a single file with a single entry
	point.
- **B.** Put it in a sibling `tools/skynet_quota.py`. Measured: a sibling
	import works through the installed symlink, because Python 3.14 resolves
	`sys.path[0]` to the real directory. This is the better shape if the quota
	code grows or gets its own tests and state file.
- **C.** Convert skynet to a package like `tools/marduk/`, with a launcher that
	sets `PYTHONPATH` and an `install.sh` change. Cleaner for a large feature,
	but a larger change than this feature needs.

**Decision: A.** Keep the quota code in `skynet.py`. Decided 2026-10-26.

### Q10 — The 5-hour and week meters

The response carries both, and the Go page describes the plan as 20% of the
monthly allowance per 5 hours and 50% per week.

- **A (recommended).** Do not show them on the first line. The human asked for
	the month and the day. They remain available for a later detail view.
- **B.** Add `5h 2% · wk 3%` to the line. More quota detail, less room for the
	requested numbers.
- **C.** Replace the day pace with the 5-hour pace. Not what was asked.

**Decision: A.** Do not show the 5-hour and week meters on the first line.
Decided 2026-10-26.

## How to pick this up

1. The decisions are recorded above. `tools/skynet/SPEC.md` is derived from
	this draft, with numbered requirements citing the questions.
2. Tests first, then the implementation in `tools/skynet.py`, then a review.
	The quota line is a display feature; the tables and the terminal contract
	must not regress.
3. Re-run `xlint` on the Markdown and the tool's tests after the change.

## Status

- `tools/skynet/DRAFT.md` — this document; decisions recorded 2026-10-26.
- `tools/skynet/SPEC.md` — derived from this draft.
- `tools/skynet.py` — implements the quota line, the credential and HTTP
	readers, the pace math and the day state.
- `tools/skynet/test/` — `test_render.py`, `test_render_table.py`,
	`test_terminal.py` unchanged; `test_quota.py` covers this work.
- Ticket `ENXZ4WY` — this work; docs merged as `317345f` (PR #102),
	implementation on `feature/ENXZ4WY-quota`.
