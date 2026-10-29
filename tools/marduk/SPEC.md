<!-- spec-origin: ai -->
> **AI-written spec.** Authored by an AI agent, not by the human.

# Marduk — Rare-Events Panel

## Goal

Marduk is a terminal panel that tells the human what they need to know without
being checked. It has a **health** section — a fixed list, always evaluated —
and a **news** section of rare events that happened once and are worth knowing.
It replaces the agent-status monitor; that purpose is retired (epiq `4V9DAKB`,
human, 2026-10-29).

## Requirements

**R1 — One store, two projections.** The store holds a *condition* per
`(source, key)` and a log of *transitions*. The health section projects the
current condition of every configured key; the news section projects the
transitions. A transition is appended when a key is first seen in a non-ok
state or when its state changes; an unchanged check appends nothing.
(ticket: *The shape*)

**R2 — The condition record.** It carries `source`, `key`, `kind` (`health` or
`news`), `name` (the stable display name), `state` (`ok`, `warn`, `alert`,
`info`), `title` (the one-line headline for a non-ok state), `detail`, `since`
(when this state began) and `checked` (the last check that observed it). The key
is stable across runs. (ticket: *The shape*)

**R3 — The transition record.** It carries `id`, `source`, `key`, `state`,
`title`, `detail`, `at` and `recovered`. It is append-only and newest-first in
the view, retained for `news_retention_days` (default 7) and capped by the pane,
not by the store. (ticket: *The shape*)

**R4 — Sources.** A source is a Python module under `_/sources/` with `NAME`,
`interval(config)`, `stale_after(config)` and `check(config, now)`, returning a
complete list of conditions for the keys it owns. A key it no longer returns is
dropped. An exception is a failed run: the last conditions are kept and the
source is marked failed. (ticket: *The shape*, *Candidate sources*)

**R5 — Scheduling.** Each source runs on its own interval in a background
thread. The panel renders on its own timer and never waits for a source. A
source still running when its next run is due is skipped, not queued.
(ticket: *The shape*)

**R6 — Liveness is first-class.** The store records `last_run`, `last_ok` and
`last_error` per source. The panel shows each source as `ok`, `stale`
(`now - last_ok > stale_after`) or `error` (the last run failed), with its age.
A health condition from a stale or failed source is marked `?`: it is the last
known state, not a current one. A source whose normal silence is long (the
weekly digest) declares a `stale_after` longer than its interval, so a normal
week is not stale. (ticket: *The requirement that decides whether it works*)

**R7 — The site source.** It checks each configured site over HTTPS with a
timeout. Any HTTP response means the server answered: `ok` for 2xx/3xx, `warn`
for 4xx, `alert` for 5xx. DNS, connection, TLS and timeout failures are `alert`,
and the detail names the failure and the elapsed time. The key is
`site:<name>`; the name is the configured label. The detail carries the status
code or the failure and the elapsed time. (ticket: *Initial health list*,
*Examples*)

**R8 — Configuration.** The default is `~/.config/marduk/config.json`,
overridable with `--config`. It holds the site list, the site interval and
timeout, the news retention and the state path. A missing or malformed config is
a visible error, not a silent empty list. The real config is outside the
repository. (ticket: *Initial health list*)

**R9 — State.** The default is `~/.local/share/marduk/state.json`, overridable
with `--state` or the config's `state_path`. It is written atomically (a temp
file and a rename) after each check cycle and on exit. A corrupt state file is
reported and replaced, not crashed on. (ticket: *The shape*)

**R10 — Display.** Two sections, health then news, plus a feeds footer. The
health section always shows every configured key in config order, even before
the first check; a key with no condition yet shows `?`. The age column is how
long the key has been known in its current state (`since`), so a down site
carries its downtime rather than its last check; the feeds footer carries the
age of the last successful check. The news section shows the newest transitions
first, or `nothing yet`; it caps to the room and shows `… +N more`. The frame
obeys `TERMINAL.md`. (ticket: *The shape*)

**R11 — No interaction in v1.** No key handling, no dismissal, no
acknowledgement. News ages out. The panel is read-only. (ticket: *Why*)

**R12 — The old purpose is removed.** The agent registry, the shared event
stream, the session and port watchers, the process helpers and the instance
join are deleted with their tests. The `oc-agent` registry and the
`instance-report` plugin are left in place; their cleanup is a separate ticket,
because removing them widens the blast radius. (ticket: *Old purpose retired*)

**R13 — Tests.** New tests in `tools/marduk/test/` in xtest's idiom cover the
transition rules, the store roundtrip and corruption, the site outcomes, the
scheduler and staleness, the render fitting and its empty states, and the
terminal contract.

## Decisions

**D1 — A JSON store, not SQLite or xcsv.** The data is small, inspection
matters, and xcsv is being rewritten by hand. Rejected: SQLite (more machinery
than the data needs); CSV (a schema change would be painful).

**D2 — In-process sources, not external commands.** A source is a small Python
function; the scheduler runs it in a thread, so a slow check cannot block the
render. Rejected: a subprocess/JSON protocol (more moving parts for a handful of
sources).

**D3 — Conditions and transitions in one file, written together.** The health
view needs current state and the news view needs changes, and both derive from
the same check result, so they are written in one transaction.

**D4 — Any HTTP response is up.** The question is whether the server answers,
not whether the page is correct. A 503 is an alert, a 404 is a warning, and both
mean the server is reachable. Rejected: treating every non-2xx as down (it would
report a reachable server as unreachable).

**D5 — Staleness is per source and visible.** `stale_after` is declared by the
source, not fixed globally, because the weekly digest is legitimately silent for
a week. The health section marks a condition from a stale source with `?`.
Rejected: one global timeout (it either nags about the weekly digest or misses a
dead site check).

**D6 — News is retained for 7 days and capped by the pane.** The panel is not a
log; a rare event a week old is no longer news. Rejected: acknowledgement (it
needs input and persistence); permanent history (it defeats "rare").

**D7 — The old modules are deleted, not flagged.** Keeping the agent path behind
a flag would keep the code and its tests alive for a purpose the human retired.
The `oc-agent` side is left alone.

**D8 — No interaction in v1.** The value is the aggregation and the filtering;
input handling, dismissal and scrolling are a later ticket.

**D9 — Config and state are XDG paths outside the repo.** The repository is
public and the paths are machine-specific. The site list is the human's, not the
repository's.

**D10 — The panel renders from the store, never from a live check.** A check
that hangs changes nothing on screen except the source's age; the last known
state is always available.

## What is removed

Files: `_/service.py`, `_/sse_client.py`, `_/session_watcher.py`,
`_/port_watcher.py`, `_/instance.py`, `_/process.py`, `_/state.py`,
`_/inotify.py`, and the tests `test_service.py`, `test_sse_client.py`,
`test_session_watcher.py`, `test_instance.py`, `test_state.py`. `TERMINAL.md`
loses the inotify requirement. The new tests cover what replaces them.

## Out of scope

The other feeds (free models, Traveller players, the weekly world-news digest),
the digest's model call, interaction, and the `oc-agent`/plugin cleanup. Each is
its own ticket.
