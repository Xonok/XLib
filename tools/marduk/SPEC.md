<!-- spec-origin: ai -->
> **AI-written spec.** Authored by an AI agent, not by the human.

# Marduk — Rare-Events Panel

## Goal

Marduk is a terminal panel that tells its user what they need to know without
being checked. It has a **health** section — a fixed list, always evaluated —
and a **news** section of rare events that happened once and are worth knowing.
It replaces the agent-status monitor; that purpose is retired (epiq `4V9DAKB`,
human, 2026-10-29).

The core knows nothing about any particular kind of check. A user gets a panel
by writing a config that names the sources they want and their options; the
repository carries no one's sites, feeds or paths.

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

**R4 — Sources.** A source kind is a class under `_/sources/` with `id`,
`interval()`, `stale_after()`, `keys()` and `check(now, memory=None)`,
constructed from its config entry. `memory` is a small dict the source owns,
round-tripped with the state and empty on the source's first run, so a source
that must remember what it saw last time has somewhere to put it; a failed run
leaves it unchanged. `check` returns a complete list of conditions for the keys
it owns; `keys` returns the `(key, name)` health rows to show before the first
check. A key it no longer returns is dropped. An exception is a failed run: the
last conditions are kept and the source is marked failed. A kind is registered
in `_/sources/__init__.py`; the config chooses and parameterizes the instances.
(ticket: *The shape*, *Candidate sources*)

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

**R7 — The site source.** It checks each configured target over HTTPS with a
timeout. Any HTTP response means the server answered: `ok` for 2xx/3xx, `warn`
for 4xx, `alert` for 5xx. DNS, connection, TLS and timeout failures are `alert`,
and the detail names the failure and the elapsed time. Options: `targets` (a
host string, or an object with `name` and `url`), `interval_seconds` (default
60), `timeout_seconds` (default 10) and `stale_after_seconds` (default
`max(3 × interval, 180)`). The key is `<id>:<name>`, where `id` defaults to
`site`; the name is the configured label. The detail carries the status code or
the failure and the elapsed time. (ticket: *Initial health list*, *Examples*)

**R8 — Configuration.** The default is `~/.config/marduk/config.json`,
overridable with `--config`. Its only source-independent keys are
`news_retention_days` and `state_path`; `sources` is a list of source instances,
each with a `kind`, an optional `id` (default: the kind) and that kind's own
options. An unknown top-level key is a visible error, so an old or misspelled
config is not silently empty. A missing or malformed config file is a visible
error. An unknown kind or a malformed source entry is a visible notice, and the
other sources still run. The real config is outside the repository. A complete
example:

```json
{
	"sources": [
		{
			"kind": "site",
			"interval_seconds": 60,
			"timeout_seconds": 10,
			"targets": [{"name": "example.com", "url": "https://example.com/"}]
		}
	],
	"news_retention_days": 7
}
```

(ticket: *Initial health list*, *Shape*)

**R9 — State.** The default is `~/.local/share/marduk/state.json`, overridable
with `--state` or the config's `state_path`. It is written atomically (a temp
file and a rename) after each check cycle and on exit. A corrupt state file is
reported and replaced, not crashed on. (ticket: *The shape*)

**R10 — Display.** Two sections, health then news, plus a feeds footer. The
health section shows every key the configured sources declare, in source then
config order, even before the first check; a key with no condition yet shows
`?`. A stored health condition whose key is not declared is shown after them, so
a source that discovers keys is not hidden. The renderer knows no source by
name. The age column is how long the key has been known in its current state
(`since`), so a down target carries its downtime rather than its last check; a
row from a stale or failed source is `?` with its last known state, and the
feeds footer carries the age of each source's last successful check. When two
sources declare a row with the same name, the row shows `<source-id>/<name>` so
the two instances stay distinguishable. The news
section shows the newest transitions first, or `nothing yet`; it caps to the
room and shows `… +N more`. The frame obeys `TERMINAL.md`. (ticket: *The shape*)

**R11 — No interaction in v1.** No key handling, no dismissal, no
acknowledgement. News ages out. The panel is read-only. (ticket: *Why*)

**R12 — The old purpose is removed.** The agent registry, the shared event
stream, the session and port watchers, the process helpers and the instance
join are deleted with their tests. The `oc-agent` registry and the
`instance-report` plugin are left in place; their cleanup is a separate ticket,
because removing them widens the blast radius. (ticket: *Old purpose retired*)

**R13 — Tests.** New tests in `tools/marduk/test/` in xtest's idiom cover the
config's source entries and their visible failures, the transition rules, the
store roundtrip and corruption, the site and apt outcomes, the scheduler and
staleness, the generic health view, the render fitting and its empty states, and
the terminal contract.

**R14 — The apt source.** It watches configured packages and reports when the
candidate version reaches the version that fixes a known issue. Options:
`packages` (a list of `{name, fixed}`; the user sets the threshold),
`interval_seconds` (default 3600), `timeout_seconds` (default 30) and
`stale_after_seconds` (default `max(3 × interval, 180)`). The candidate is read
from `apt-cache policy <name>`; versions are compared with
`dpkg --compare-versions`, so Debian ordering is the system's, not a
reimplementation. The record is `news`, keyed `<id>:<name>`: `info` with "X can
be fixed by apt upgrade" when the candidate is at or above the fix, `ok` below
it. A missing candidate or a failed command is a source error. It checks the
panel's host; a remote host is not in this increment. (ticket: *apt package
versions*)

**R15 — The model-catalogue source.** It reads the opencode console's catalogue
(`opencode models`) and OpenRouter's `/api/v1/models`, and joins the console's
entries to the model database's costs (`models.dev`) so a free model is a price
of zero in either catalogue. A model is identified by its id with a leading
`openrouter/` removed, so the same model seen through the console's OpenRouter
route and directly from OpenRouter is one entry. **The first run is a seed**:
it records the catalogue in the source's memory and announces nothing. After
that, a model id not in memory is one `info` news item, and a model that was
paid and is now free is one if it matches the `powerful` list; free→paid is
silent but updates the memory, and an unchanged catalogue adds nothing. A model
that disappears is not news and leaves the memory, so its return is not "new".
`powerful` is a list of id substrings (the user's judgement; the tool does not
pretend metadata is a ranking). Options: `powerful`, `interval_seconds`
(default 3600), `timeout_seconds` (default 30), `stale_after_seconds` (default
`max(3 × interval, 180)`) and `prices_refresh_seconds` (default 21600).
(ticket: *The model-catalogue feed*)

**R16 — The Traveller player source.** It reads the game's `users.json` and each
`users/<name>.json` under the configured `data_path`; `props.created` is the
join time and `props.last_active` the last-seen time. The first run seeds the
last-active times and announces nothing. After that, a player not in memory is
one `info` news item, and a player whose last-active time advanced by more than
`absence_days` is one that says how long they were away. A player idle for a
day is not news; a player missing from the list stays in memory; a broken
player file is skipped rather than failing the feed. Options: `data_path`
(required — the game's data directory, which is outside this repository),
`absence_days` (default 14), `interval_seconds` (default 300) and
`stale_after_seconds` (default `max(3 × interval, 180)`).
(ticket: *The Traveller player feed*)

## Decisions

**D1 — A JSON store, not SQLite or xcsv.** The data is small, inspection
matters, and xcsv is being rewritten by hand. Rejected: SQLite (more machinery
than the data needs); CSV (a schema change would be painful).

**D2 — In-process sources, not external commands.** A source is a small Python
class; the scheduler runs it in a thread, so a slow check cannot block the
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
public and the paths are machine-specific. The configured checks are the user's,
not the repository's.

**D10 — The panel renders from the store, never from a live check.** A check
that hangs changes nothing on screen except the source's age; the last known
state is always available.

**D11 — Sources are configured instances, not a fixed list.** The config names
the kind and carries that kind's options, so a user selects the checks they want
without editing code, two instances of one kind can run side by side, and a new
kind is a new class plus one registry entry. Rejected: a hardcoded source list
(the first increment had one source wired into the config schema); a declarative
protocol for arbitrary HTTP feeds (it cannot express the classification and the
editorial judgement a feed needs).

**D12 — A bad source entry is a notice, not a fatal error.** An unknown kind or
a malformed option is shown on the panel, and the other sources keep running;
one typo should not blank the whole panel. A missing or unparseable config file
is still fatal, because there is no source list at all.

**D13 — A source may keep memory in the store.** A catalogue feed's news is an
*event*, not a state: the transition rules cannot express "this id appeared"
without turning the next run into a recovery, and the rule that drops a key the
source no longer returns cannot remember a model that has left the catalogue.
So a source owns a small dict that the store round-trips with the rest of its
state, empty on the first run; the source decides what goes in it. Rejected: a
sidecar file per feed (a second store, written behind the panel's back), and
using the conditions as the memory (they are the current state, not the history
of what was seen).

## What is removed

Files: `_/service.py`, `_/sse_client.py`, `_/session_watcher.py`,
`_/port_watcher.py`, `_/instance.py`, `_/process.py`, `_/state.py`,
`_/inotify.py`, and the tests `test_service.py`, `test_sse_client.py`,
`test_session_watcher.py`, `test_instance.py`, `test_state.py`. `TERMINAL.md`
loses the inotify requirement. The new tests cover what replaces them.

## Out of scope

The remaining feeds (the weekly world-news digest), the digest's model call,
interaction, and the `oc-agent`/plugin cleanup. Each is its own ticket.
