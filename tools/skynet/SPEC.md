<!-- spec-origin: ai -->
> **AI-written spec.** Authored by an AI agent, not by the human.

# Skynet — quota line

> Derived 2026-10-26 from `tools/skynet/DRAFT.md`; the intent is the human's,
> the encoding is an AI interpretation. The ten decisions are recorded at the
> end and in the DRAFT.

## Goal

Skynet's first line is `=== Skynet ===`. It carries no information about the
quota the panel's own usage is spending. The change puts the OpenCode Go quota
and the OpenRouter free-request quota on that line, with the absolute spend,
the percentage used, and two pace figures that say whether the current rate is
sustainable. The tables below it, and their height/width contract, do not
change.

The two pace figures are rates, not percentages of the quota used:

- `pace` is the average rate since the paid period started.
- `today` is the rate since local midnight.

Both are expressed as a percentage of the **sustainable daily rate**, which is
`limit / period_days`. At 100% the current rate exhausts the quota exactly at
the reset; at 200% it exhausts it halfway through. This is the human's wording
encoded as a unit (DRAFT Q4, *What the display would look like*).

## Architecture

The quota code stays in `tools/skynet.py` (DRAFT Q9 A). It is one feature in
one file: credential lookup, two HTTP readers, the pace functions, the state
file, and the header renderer. The HTTP layer is one function so tests can
replace it; the credential and state functions accept a path so tests can use
temporary files.

```
sample_quota(now, state_path, fetch)
  ├─ read_credentials()
  │    ├─ opencode: access, expires, metadata.server
  │    └─ openrouter: key
  ├─ go_quota(credentials, now, fetch)
  ├─ openrouter_quota(credentials, fetch)
  └─ update_day_state(state_path, go, now)
       ↓
quota_line(quota, width) → one line, ≤ width
```

The local database remains read-only. The quota code never writes to
`opencode.db`; its only write is `~/.local/share/skynet/quota.json`
(DRAFT Q1 A, Q3 A).

## Data sources

### Go

`GET {metadata.server}/api/go/status`, with `Authorization: Bearer <access>`.
`metadata.server` is `https://opencode.ai/console` on the measured account.
Response fields used:

| Field | Meaning |
|---|---|
| `product` | `go` or `go-plus`; display `Go` or `Go+` |
| `access.startsAt` | paid period start |
| `access.endsAt` | paid period end, which is the reset |
| `access.meters.month.limitMicroCents` | the period allowance |
| `access.meters.month.usedMicroCents` | the amount used |

`fiveHour` and `week` are present and are **not** shown (DRAFT Q10 A).
Microcents are `1 dollar = 100_000_000`; keep the integers and format only at
render time (DRAFT Q7 A).

The meter is not the local `session_message.data.cost` column. For
`opencode-go/deepseek-v4.1-flash` the meter runs at `0.75×` the local list
cost, and the ratio is model-specific. The local `cost` column is **not** a
quota source (DRAFT Q7 A).

### OpenRouter

`GET https://openrouter.ai/api/v1/key`, with `Authorization: Bearer <key>`.
Response field used: `free_model_daily_requests`, with `used` and `limit`,
nested under `data` in the measured response (the top level is accepted too).
This is the free-model daily counter, not all requests; `usage_daily` is paid
dollars and is not shown on the first line (DRAFT Q5 A, Q6 A).

The counter appears to reset at UTC midnight. Use it as the provider reports it;
do not re-derive a local day (DRAFT Q6 A).

### Credentials

Both credentials live in the SQLite database skynet already opens read-only,
table `credential`:

```
credential(id, integration_id, label, value, connector_id, method_id,
           active, time_created, time_updated)
```

- Go: `integration_id = 'opencode' AND active = 1`. Parse `value` as JSON and
	use `access`, `expires` (milliseconds) and `metadata.server`.
- OpenRouter: `integration_id = 'openrouter'`. Parse `value.key`. If more than
	one row matches, prefer `active = 1`, then the greatest `time_updated`.
- Never log, print or include the access token, refresh token or API key in an
	error message.

### HTTP

`urllib.request` with an explicit `User-Agent: skynet/1.0`, a 3-second timeout,
and `Accept: application/json`. **The default Python User-Agent is rejected by
Cloudflare with `403 error code: 1010`**; the explicit UA is mandatory, not
politeness (DRAFT *One operational gotcha*).

No third-party packages. Catch `HTTPError`, `URLError`, `TimeoutError`,
`OSError`, `json.JSONDecodeError`, `KeyError`, `TypeError` and `ValueError`;
return an unavailable source rather than raising into the renderer.

## Source states

Every source is in one of three states:

| State | Meaning | First-line rendering |
|---|---|---|
| `ok` | data read | the source's fields |
| `unavailable` | configured, but the read failed | `Go ?` / `G ?` / `OR ?` |
| `absent` | not configured, or no such product | no field |

- Missing credential row → `absent`.
- Go token `expires` in the past → `unavailable`; do not call the endpoint
	(DRAFT Q1 A).
- Go endpoint `404` → `absent` (no Go product for this account).
- Go endpoint `200` with `access` null → `absent`.
- Go endpoint `200` with `access` present but a required meter missing →
	`unavailable`.
- OpenRouter key endpoint `200` without `free_model_daily_requests` →
	`unavailable`.
- Any other HTTP/network/JSON failure → `unavailable`.
- A source that is `absent` contributes no field; `unavailable` contributes
	`?` (DRAFT Q8 A).

## Pace math

All times are timezone-aware; `Z` is parsed as `+00:00`. `now` is the current
time.

```
period_days  = (end - start) / 86400
sustainable  = limit / period_days
used_percent = used / limit * 100
overall_pace = (used / (now - start in days)) / sustainable * 100
today_pace   = ((used - day_start_used) / (now - day_start in days))
               / sustainable * 100
```

- `overall_pace` is `None` when `now <= start`, `period_days <= 0` or
	`limit <= 0`.
- `today_pace` is `None` when `day_start_used` is `None`, `now <= day_start`,
	`used < day_start_used` or either denominator is non-positive.
- `used_percent` is `None` when `limit <= 0`.
- Render round to the nearest integer. The full form says `72%/d`; the
	abbreviated form says `p 72`.
- `100%` is exactly the sustainable rate; `200%` exhausts the quota in half
	the period. Tests pin both.

The period start is `access.startsAt`. If the account renews and the API keeps
the original subscription start instead of advancing it, the overall pace
divides by the wrong elapsed time. The implementation cannot detect that from
one response; the DRAFT records it as a known limit.

## Day baseline

The Go API has no daily history. The day pace needs the meter reading at local
midnight (DRAFT Q2 A, Q3 A).

**File:** `~/.local/share/skynet/quota.json` (JSON, version 1):

```json
{
  "version": 1,
  "go": {
    "day": "2026-10-26",
    "day_start_used": 185668768,
    "last_used": 186774741,
    "last_seen": 1792976224,
    "period_start": "2026-10-24T16:47:40Z"
  }
}
```

**Update rules**, on every successful Go read:

1. `today` is the local date of `now`, formatted `YYYY-MM-DD`.
2. If the stored `day` is missing or differs from `today`:
	- If `last_seen` is within 900 seconds of local midnight (either side),
		set `day_start_used` to `last_used`.
	- Otherwise set `day_start_used` to `None`; the panel shows `today ?`
		until the next midnight.
	- Set `day` to `today`.
3. If `period_start` differs from the stored one, set `day_start_used` to
	`None` (a new paid period).
4. If `used < last_used`, set `day_start_used` to `None` (the meter reset
	downward).
5. If `day_start_used` is already set for `today`, keep it.
6. Update `last_used`, `last_seen` and `period_start`.
7. Write atomically: a temporary file in the same directory, then
	`os.replace`. A write failure is not fatal; the line shows `today ?` and
	the tables still render.

The state file is per-machine and must not be tracked. A missing or corrupt
file is treated as empty state.

## Display

The first line is exactly one line, at most `width` columns, and never wraps
or contains a newline. The tables below it are unchanged.

### Full form

`=== Skynet === ` + fields joined by ` · `, in this order:

| Field | `ok` | `unavailable` |
|---|---|---|
| Go | `Go $1.87/$60 3%` or `Go+ …` | `Go ?` |
| Pace | `pace 72%/d`; omitted when the pace is `None` | omitted |
| Today | `today 94%/d`; `today ?` when the baseline is missing; omitted when today is `None` | omitted |
| OpenRouter | `OR 29/1000` | `OR ?` |

`absent` sources contribute nothing. If both sources are `absent`, the line is
`=== Skynet ===`, the current behavior.

Dollar formatting:

- `used` dollars: two decimals (`$1.87`).
- `limit` dollars: no decimals when integral (`$60`), otherwise two.
- Percentage: nearest integer (`3%`).
- Pace: nearest integer with `%/d`.

### Abbreviated form (DRAFT Q4 B)

When the full form does not fit, use the abbreviated labels and keep every
field:

| Field | `ok` | `unavailable` |
|---|---|---|
| Go | `G $1.87/60 3%` or `G+ …` | `G ?` |
| Pace | `p 72` | omitted when Go is `?` |
| Today | `t 94` | `t ?` |
| OpenRouter | `OR 29/1000` | `OR ?` |

The abbreviated form is the same field order and join. `p` and `t` keep the
meaning of the full form; the `%/d` decoration is dropped for width.

### Drop order

Only when the abbreviated form still does not fit are fields dropped, from the
right:

1. `OR`
2. `t`
3. `p`
4. shorten Go: `G $1.87/60 3%` → `G $1.87 3%` → `G 3%`
5. `=== Skynet ===`

The acceptance table, with the measured example:

| Width | Line |
|------:|------|
| 70+ | `=== Skynet === Go $1.87/$60 3% · pace 72%/d · today 94%/d · OR 29/1000` |
| 56–69 | `=== Skynet === G $1.87/60 3% · p 72 · t 94 · OR 29/1000` |
| 43–55 | `=== Skynet === G $1.87/60 3% · p 72 · t 94` |
| 36–42 | `=== Skynet === G $1.87/60 3% · p 72` |
| 29–35 | `=== Skynet === G $1.87/60 3%` |
| 26–28 | `=== Skynet === G $1.87 3%` |
| 19–25 | `=== Skynet === G 3%` |
| 14–18 | `=== Skynet ===` |

The boundaries are the lengths of those lines; the earlier draft of this table
was one column low in the first seven rows, which would have asked for a line
wider than the pane it was given. Widths below 14 are out of scope; the title
itself is 14 columns. The function must never return more than `width`
characters.

## Watch and one-shot

- **One-shot:** read each configured source once before the first render; use
	the same 3-second timeout. Update the day state on a successful Go read.
- **Watch:** read at start, then at most once every 60 seconds. The loop
	already blocks for up to one second on inotify; after that it must check
	the quota timer and redraw if it expired, even when the database did not
	change. The pace depends on time, so a redraw must not wait for a database
	write.
- A failed read never prevents the tables from rendering; the source's field
	becomes `?` or disappears.
- The fetch is synchronous with a 3-second timeout. A background thread is
	out of scope for this change; if the freeze is noticeable, it is a
	follow-up.

## Requirements

### Credentials

- **R1.1** Read credentials from the existing read-only `DB_PATH`, table
	`credential`.
- **R1.2** The Go credential is the row with `integration_id = 'opencode'` and
	`active = 1`; use `value.access`, `value.expires` and
	`value.metadata.server`.
- **R1.3** The OpenRouter credential is the row with
	`integration_id = 'openrouter'`; use `value.key`. Prefer `active = 1`, then
	the greatest `time_updated`.
- **R1.4** A missing row makes the source `absent`; malformed JSON makes it
	`unavailable`.
- **R1.5** A Go `expires` in the past makes the Go source `unavailable` without
	a network call (DRAFT Q1 A).
- **R1.6** Never write to `opencode.db` and never log a token or key.

### Go

- **R2.1** Request `{server}/api/go/status` with the Bearer access token.
- **R2.2** Every HTTP request sets `User-Agent: skynet/1.0`.
- **R2.3** Parse `product`, `access.startsAt`, `access.endsAt`,
	`meters.month.limitMicroCents` and `meters.month.usedMicroCents`; coerce
	the microcents to `int`.
- **R2.4** Use microcents as integers; `1 dollar = 100_000_000`.
- **R2.5** Display `Go` for `product = "go"` and `Go+` for
	`product = "go-plus"`; take limits from the response, never hardcode.
- **R2.6** A `404` makes Go `absent`; a `200` with `access` null makes it
	`absent`; a required field missing from an otherwise valid response makes it
	`unavailable`.
- **R2.7** 401, 403, network, timeout and JSON errors make Go `unavailable`.
- **R2.8** Do not parse or display `fiveHour` or `week` on the first line
	(DRAFT Q10 A).

### OpenRouter

- **R3.1** Request `https://openrouter.ai/api/v1/key` with the Bearer key.
- **R3.2** Parse `free_model_daily_requests.used` and `.limit`; coerce both
	to `int`.
- **R3.3** A missing key makes OpenRouter `absent`; a missing
	`free_model_daily_requests` makes it `unavailable`; HTTP/network/JSON errors
	make it `unavailable`.
- **R3.4** Do not re-derive a local day (DRAFT Q6 A).
- **R3.5** Do not display `usage_daily` on the first line (DRAFT Q5 A).

### Pace

- **R4.1** `period_days = (end - start) / 86400`.
- **R4.2** `sustainable = limit / period_days`.
- **R4.3** `used_percent = used / limit * 100`.
- **R4.4** `overall_pace = (used / (now - start in days)) / sustainable * 100`.
- **R4.5** `today_pace = ((used - day_start_used) / (now - day_start in days))
	/ sustainable * 100`.
- **R4.6** Return `None` when a denominator is zero or negative, when
	`used < day_start_used`, or when the needed baseline is missing.
- **R4.7** Round to the nearest integer at render time.
- **R4.8** At `used = limit * (now - start) / (end - start)`, the pace is 100%;
	at twice that, 200%.

### Day state

- **R5.1** The state path is `~/.local/share/skynet/quota.json` (DRAFT Q3 A);
	create the directory when missing.
- **R5.2** A missing or corrupt file is empty state.
- **R5.3** On the first successful read of a new local day, use `last_used` as
	`day_start_used` only when `last_seen` is within 900 seconds of local
	midnight; otherwise `None` (DRAFT Q2 A).
- **R5.4** A changed `period_start` or a decreasing `used` resets the day
	baseline.
- **R5.5** Keep an existing `day_start_used` for the same day.
- **R5.6** Write atomically; a write failure leaves the line at `today ?` and
	does not break the tables.
- **R5.7** The state file is per-machine and untracked.

### Display

- **R6.1** For `width >= 14`, the first line is one line, at most `width`
	characters, with no newline. Widths below 14 are out of scope.
- **R6.2** Try the full form first, then the abbreviated form, then the drop
	order; the acceptance table in *Display* is normative.
- **R6.3** `absent` sources contribute no field; `unavailable` sources show
	`?` (or `G ?` / `OR ?`).
- **R6.4** When Go is `?`, omit `pace` and `today`; `Go ?` alone is the Go
	contribution.
- **R6.5** The tables and the terminal contract are unchanged; a quota failure
	never removes a table (DRAFT Q8 A).
- **R6.6** `render(rows, now, height=None, width=None, quota=None)` keeps the
	existing signature's behavior when `quota` is `None`.

### Watch

- **R7.1** One-shot reads once before rendering; watch reads at start and at
	most once per 60 seconds.
- **R7.2** Watch redraws when the database changes, the terminal resizes, or
	the quota timer expires.
- **R7.3** The fetch is synchronous with a 3-second timeout; a failed fetch
	does not prevent the render.
- **R7.4** A successful Go read updates the day state in both modes.

### Tests and docs

- **R8.1** Tests use `xtest`; no test touches the network or the real
	database. Use a temporary SQLite DB, a temporary state path, and a fake
	`fetch`.
- **R8.2** Test the explicit `User-Agent` on the request.
- **R8.3** Test the pace math at fixed times, including 100% and 200%.
- **R8.4** Test day rollover, a stale `last_seen`, a corrupt state file, a
	changed period and a decreasing meter.
- **R8.5** Test the full-to-abbreviated switch, the drop order, and the width
	sweep 14–120.
- **R8.6** Test credential selection, missing rows, expired tokens, 401/403,
	404 and malformed JSON.
- **R8.7** Add the quota-line contract to `tools/skynet/TERMINAL.md`.
- **R8.8** `xlint` the Markdown and add the suite to `tools/run_tests.py` if it
	is not already covered.

## Decisions

| # | Decision | Answer |
|---|----------|--------|
| Q1 | Auth token handling | A — read-only; `Go ?` on 401; no refresh |
| Q2 | "Today" baseline | A — persist a midnight baseline; `today ?` without one |
| Q3 | State location | A — `~/.local/share/skynet/quota.json` |
| Q4 | Width fallback | B — abbreviate first, then drop |
| Q5 | Free usage | A — internal only; no free field |
| Q6 | OpenRouter day | A — use the API's UTC-day counter |
| Q7 | Quota source | A — provider counters only |
| Q8 | API failure | A — `?` for configured-but-unreadable; omit unconfigured |
| Q9 | Code layout | A — keep the quota code in `skynet.py` |
| Q10 | 5-hour and week meters | A — do not show them on the first line |

## Out of scope

- Token refresh and any write to `opencode.db` (Q1 A).
- Free-usage display; the provider counters already exclude free usage (Q5 A).
- A local-day OpenRouter counter (Q6 A).
- Quota dollars from the local `cost` column (Q7 A).
- The 5-hour and week meters on the first line (Q10 A).
- A background fetch thread.
- Per-model quota history; the API has no daily history.
- Cursor-agent support; that is the separate ticket `4P4VD3A`.

## Known limits

- The Go endpoint is an internal console API, not a documented public one; a
	path or schema change makes Go `?`, not a crash.
- The access token expires; read-only means the Go field disappears until
	opencode refreshes the token.
- The Go meter has no daily history; a cold start mid-day shows `today ?`
	until the next midnight.
- The Go meter may lag; the overall pace is stable, the day pace is noisier.
- The Go meter is not Zen list price; quota dollars are the meter's unit.
- OpenRouter's counter is a UTC-day, free-models-only counter.
- Free usage has no nominal value in either API; "dollars saved by a
	promotion" is not derivable from these responses.
- The paid period start is `access.startsAt`; a renewal that does not advance
	it would make the overall pace divide by the wrong elapsed time.
