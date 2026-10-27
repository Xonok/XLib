<!-- spec-origin: ai -->
> **AI-written spec.** Authored by an AI agent, not by the human.

# taskboard — the wide all-tasks view

> Written 2026-10-27 from epiq `E5MH4S2` and the human's rulings of 2026-09-27,
> 2026-10-20, 2026-10-21 and 2026-10-27. There is no separate `DRAFT.md`: the
> ticket and its comments carry the intent, and the rulings are quoted in the
> decisions below. Decisions marked **[CONFIRM]** follow the recommendation
> given; overruling one is a spec-and-test change, which is cheapest before
> code exists.

## Goal

The tmux pane is built for focus: one project, one current task, a short queue.
That is the wrong instrument for the question *what should I do next across
everything?* — which needs every open task at once, ordered by when it is due,
with the ability to move one task's due date and watch it resettle. Today that
view exists only as a CSV and a `list` command; Decision 13 in
`tools/taskview/SPEC.md` rules that it deserves its own renderer over the same
selection layer. This spec is that renderer: a local web page, not a terminal
tool (human, 2026-10-27). The pane already owns the terminal, eighty-odd rows
and six columns are a table, and editing a table is the one job a terminal is
worst at.

The store stays the single authority. The board reads the CSV through
`taskview`'s selection functions and writes through `taskupdate`'s append path,
so it introduces neither a fourth source nor a second writer. Ordering is due
date and nothing else (human, 2026-10-21): reprioritising is changing a due
date, so no priority field is added and no schema change is proposed.

## Data model

Unchanged. The CSV keeps its nine columns and its append-only, last-row-wins
fold; `tools/taskview/SPEC.md` R17–R18 and R33 resolve the path, and R36–R37
define how a row is read. This tool adds no column, moves none, and writes only
rows of the existing shape. Its write path is `taskupdate.append_row`, so a row
written from the browser is indistinguishable from one written by an agent.

## Requirements

Each requirement states behaviour, not file layout. Pure functions take the
current time as a parameter so no test depends on the wall clock.

### Reading and selection

- **R1** The store is resolved exactly as `taskview` and `taskupdate` resolve it:
	`--csv`, else `$TASKVIEW_CSV`, else `<data-dir>/tasks.csv`; the data
	directory is `--data-dir`, else `$TASKVIEW_DATA_DIR`, else
	`$XDG_DATA_HOME/taskview`, else `~/.local/share/taskview`. The resolution is
	imported, not reimplemented, so the three tools cannot disagree about which
	file they mean.
- **R2** If the resolved store does not exist, the process exits **1** before
	binding a port, with a message naming the path. It does not create the store:
	a write tool that starts against a missing store would present "you have no
	tasks" as a fact.
- **R3** The board shows `read_csv(store)` folded by `select_tasks(state, None)`,
	restricted to `status == "open"`. That is exactly the set the pane's global,
	unfiltered view considers, minus the statuses the board does not display:
	never-show tags exclude a task, `critical`/`emergency` do not rescue a
	done or cancelled one. No filter file is consulted (R27).
- **R4** The order is: due date ascending by **local calendar date**, undated
	tasks last; ties by importance — `high`, `medium`, `low`, none, then any
	unknown value — then by id ascending. The order is deterministic for equal
	input and is a pure function. Undated tasks never outrank dated ones.
- **R5** The summary counts open tasks by calendar day, relative to `now`:
	`overdue` (due date before today), `today`, `this_week` (1–7 days ahead),
	`later` (more than 7 days ahead) and `undated`. `open` is their sum. A task
	due today is **not** overdue, whatever the time of day; the comparison is
	between dates, not between timestamps.
- **R6** A task in the payload has exactly these keys: `id` (int), `title`
	(string), `due_ts` (int or null), `due_date` (`YYYY-MM-DD` local date, or
	null), `due_label` (string, from `taskupdate.fmt_due`), `importance`
	(string, possibly empty), `category` (string, possibly empty), `tags`
	(sorted list of strings) and `chg_ts` (int). `chg_ts` is the concurrency
	token; the description is deliberately absent, because the wide view does
	not show it and it is the largest field.

### The API

- **R7** `GET /api/tasks` returns **200** with a JSON object:
	`{"now": int, "store": {"path": str}, "summary": {...R5...},
	"tasks": [...R6...]}`. `Content-Type` is `application/json; charset=utf-8`,
	and the body is UTF-8 with non-ASCII text preserved. The route re-reads the
	store on every request; there is no cache. If the store vanished while the
	tool was running, the response is **503** and names the path; the tool does
	not recreate it.
- **R8** `GET /api/tasks` sends an `ETag` derived from the store's modification
	time and size. A request whose `If-None-Match` matches gets **304** with no
	body. Any write changes the file and therefore the tag.
- **R9** `POST /api/due` takes a JSON object with `id` (int), `value` (string)
	and `expected_chg_ts` (int). Unknown keys are ignored. A body over 64 KiB is
	rejected with **413**; a body that is not an object, or lacks or mistypes
	one of the three keys, is **400**.
- **R10** `value` is parsed by `parse_due_edit(value, current_due_ts, now)`:
	- `YYYY-MM-DD` or `YYYY/MM/DD` — that local date at **12:00**.
	- `MM-DD` or `MM/DD` — the same, in the current local year.
	- `+Nd`, `+Nw`, `-Nd`, `-Nw` — N days or weeks from the task's current due
		date, or from today when it has none; the result is again at 12:00. N is a
		positive integer and the unit is case-insensitive.
	- `none` or the empty string — clear the due date.
	- Anything else — **400** with a message naming the accepted forms. Months
		and years are not bump units, because month arithmetic has no single
		answer at month ends.
	Whitespace is trimmed and `none` is case-insensitive. The slash form of a
	date is accepted because the human wrote the interaction as `2026/10/27`,
	and the parser normalises it to the store's dash form. A bump from an
	overdue task is measured from its stored due date, not from today: `+7d` on
	a task three days overdue leaves it four days overdue.
- **R11** A write goes through `set_due(csv_path, task_id, new_due_ts,
	expected_chg_ts, now)`, and the whole read-check-append sequence is one
	critical section:
	1. Take the process-wide write lock.
	2. Re-read the row with `taskupdate.read_task` — not the page's snapshot.
	3. Missing row → **404**. `status != "open"` → **409** with the message that
		only open tasks are editable.
	4. Stored `chg_ts` differs from `expected_chg_ts`, or is not an integer →
		**409** (R12).
	5. Append one full row with `taskupdate.append_row`, copying `status`,
		`title`, `category`, `tags`, `importance` and `description` from the row
		just read, using `new_due_ts` as the due, and setting `chg_ts` to
		`max(now, old_chg_ts + 1)`. The monotonic step means two writes in one
		second still produce two distinct versions, so the token is a version
		rather than a clock reading.
	6. Return the same payload as R7, computed after the append.
	If the store disappeared after startup, the write fails with **409** and no
	file is created.
- **R12** A stale write is refused, never forced. The **409** body is
	`{"error": "conflict", "message": str, "task": {...R6...}}`, carrying the
	current row — normalised to the R6 shape — so the page can show what
	changed. The page keeps the typed value and retries with the fresh `chg_ts`;
	there is no `force` flag, because a forced write is how a concurrent edit is
	silently lost.
- **R13** Every error response is a JSON object carrying `error` and `message`
	strings; a conflict (R12) adds `task`. The codes are **400** (bad JSON, bad
	value, bad types), **401**
	(missing or wrong token), **403** (foreign `Origin`), **404** (unknown route
	or task), **405** (wrong method, with `Allow`), **409** (conflict, not open,
	store gone), **413** (body too large), **415** (POST without a JSON content
	type), **500** (unexpected; the body says only that, and the traceback goes
	to the log) and **503** (the store vanished while the tool was running).
- **R14** The routes are exactly:

	| Route | Method | Result | Content type |
	|---|---|---|---|
	| `/` | GET | the page | `text/html; charset=utf-8` |
	| `/board.js` | GET | the page's script | `text/javascript; charset=utf-8` |
	| `/board.css` | GET | the page's stylesheet | `text/css; charset=utf-8` |
	| `/api/tasks` | GET | R7 | `application/json; charset=utf-8` |
	| `/api/due` | POST | R11 | `application/json; charset=utf-8` |

	Every other path is **404**; every other method on a known path is **405**
	with `Allow`. The tool never answers a write with a redirect, and a `GET`
	never mutates anything (R26).

### The page

- **R15** The page is a semantic table with one row per task and columns
	`#`, due, importance, category, title and tags. The first column renders
	`#<id>`, the same handle the pane prints and `taskupdate show` accepts. The
	title is allowed to wrap; it is the wide column and truncating it is the
	pane's compromise, not this tool's.
- **R16** A summary line above the table shows `open`, `overdue`, `today`,
	`this_week`, `later` and `undated` counts from R5, the store path, and the
	age of the last successful refresh. With no open tasks the table is replaced
	by a plain "No open tasks" message.
- **R17** The due cell is the only editable cell. Clicking it, or focusing it
	and pressing Enter, opens a text input prefilled with `due_date` (empty when
	undated). Enter submits; Escape cancels and restores the label. At most one
	editor is open at a time; opening another cancels the first without
	submitting.
- **R18** A rejected value leaves the editor open with the input unchanged and
	shows the server's message next to the row. A conflict shows the current
	due date and the fact that someone else changed the row; the input keeps the
	value the human typed so Enter retries against the fresh token.
- **R19** No request outside the page's own origin is made: no fonts, no CDN,
	no analytics, no favicon fetched from elsewhere. The page is served as three
	static files and needs no build step. It works with JavaScript enabled; a
	`<noscript>` message says the page needs it.
- **R20** While the tab is visible the page re-reads `GET /api/tasks` every two
	seconds, and immediately when the tab becomes visible again. Polling pauses
	while the tab is hidden. A failed poll shows a "connection lost — retrying"
	banner and is retried on the next tick; a successful poll clears it. A poll
	never closes or overwrites an open editor. After a successful write the page
	renders from the write's response, so the row's new position and label are
	correct before the next poll.
- **R21** Every task-derived string is inserted as text, never as HTML: a title
	containing `<script>` is displayed as those characters. The page uses no
	`innerHTML` for data, and its JavaScript is not inline (R23).

### Serving and safety

- **R22** Every response carries `X-Content-Type-Options: nosniff`,
	`Referrer-Policy: no-referrer` and a
	`Content-Security-Policy` of `default-src 'none'; script-src 'self';
	style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none';
	form-action 'none'; frame-ancestors 'none'`. API and page responses carry
	`Cache-Control: no-store`; the two assets may be revalidated.
- **R23** The page's script and stylesheet are separate files, so the policy
	above needs no `'unsafe-inline'`. No response contains inline script or
	style, and none contains an external URL.
- **R24** The default bind is `127.0.0.1`, and on a loopback bind no token is
	required; a loopback host is `localhost`, `127.0.0.0/8` or `::1`. A
	non-loopback bind requires a token of at least 16 characters, supplied by
	`--token` or `$TASKBOARD_TOKEN`, and refuses to start without one. When a
	token is configured it is enforced on any bind, loopback included. With a
	token, the startup line prints one URL carrying it; `GET /?token=<token>`
	compares it with `hmac.compare_digest`, sets an `HttpOnly`,
	`SameSite=Strict`, `Path=/` cookie and answers **303** to `/`. Every other
	request requires that cookie; missing or wrong is **401**. When no token is
	configured, a `token` query parameter is ignored. The token appears in no
	response body, no error message and no log line other than the startup URL.
- **R25** A `POST` is accepted only with a `Content-Type` of
	`application/json` (**415** otherwise), and, when an `Origin` header is
	present, only when it equals `http://` plus the request's `Host` (**403**
	otherwise). The cookie is `SameSite=Strict`; the origin check is the second
	lock on the same door.
- **R26** Starting the tool and serving any `GET` create and modify nothing:
	no store, no cache, no lock file, no log file. Only a successful `POST`
	writes, and only through `taskupdate.append_row`.
- **R27** The board is unfiltered by definition and never reads a
	`.taskview.yaml`. A task with no category is shown like any other; the
	uncategorised bucket is the reason the wide view exists.
- **R28** Two requests may be in flight at once; every write holds a
	process-wide lock from the re-read through the append, so two `POST`s for
	the same row are serialised and the second sees the first. The server does
	not claim atomicity against a *different* process writing the store —
	`taskupdate` does not take this lock, and the store's model is last write
	wins. The `chg_ts` guard narrows that window to the microseconds between
	the re-read and the append; it does not close it, and the spec does not
	pretend otherwise.
- **R29** The only dependencies are the Python standard library and this
	repository's own modules (`taskview`, `taskupdate`, optionally `xhttp`). No
	third-party package, and no network access beyond the local socket.

### Operations

- **R30** The command is `taskboard.py` with `--csv`, `--data-dir`, `--host`,
	`--port` and `--token`. The port defaults to **8780** and `--port 0` is
	allowed, binding an ephemeral port and printing the real one. A bind
	failure exits **1** with a message; the tool does not try the next port,
	because an auto-incremented port hides which instance is live.
- **R31** The tool runs in the foreground and stops cleanly on `SIGINT` with
	exit **0**. On startup it prints one line with the URL, the resolved store
	path and the open count (and, off loopback, the tokenised URL). It logs one
	line per successful write — id, old due, new due, and the input — and one
	per rejected write with the reason. It does not log successful reads or
	per-request access lines: a tool polled every two seconds would otherwise
	write more log than store. *Verification:* this is the one requirement
	covered by inspection rather than a test; the log is operator output, and
	asserting its exact wording would freeze a line nobody parses. The writer it
	calls may echo its own line; that echo is not part of the contract.
- **R32** Tests live in `tools/taskboard/test/`, are written with `xtest`,
	run standalone (`python3 dev/xtest/xtest.py <file>`), and the suite is
	registered in `tools/run_tests.py`. The pure functions of R4, R5 and R10,
	and the write path of R11, take `now` as an argument, so no test depends on
	the clock. The page's requirements R15–R21 are checked by fetching the three
	assets and asserting their content markers, plus inspection for the editing
	interaction; this repo has no DOM test harness, and this spec does not add
	one. The API carries the behaviour that must not regress.

## Decisions

1. **A local web page, not a terminal TUI** (human, 2026-10-27). The pane
	already owns the terminal and a second renderer would inherit its width
	limit; every terminal tool in the repo is a read-only render loop, so an
	editing one would invent an input layer this codebase does not have; and
	the operation — select a row, type a date — is a table. *Rejected:* a
	`curses`/`--wide` mode, which costs about what the page costs and is worse
	at the job.
2. **No priority column; the order is due date** (human, 2026-10-21). "The
	wide tool always orders by due date — changing the order is simply a result
	of changing a due date." *Rejected:* a `priority` column, a widened
	`importance`, and a separate ordering file; the first would collide with
	the append-only last-write-wins model, and none is needed once order is a
	consequence of the dates.
3. **Ties break by importance, then id** — **[CONFIRM]**. Two tasks due the
	same day need some order, and `importance` is already in the store and
	already means "how much this matters". It never outranks a date; it only
	breaks a tie. *Rejected:* id alone (arbitrary in the human's face) and
	`chg_ts` (recency is not priority).
4. **The board is unfiltered and ignores filter files** — **[CONFIRM]**. It is
	the view with no category restriction; that is what distinguishes it from
	the pane. *Rejected:* reusing the global `.taskview.yaml`, which is pane
	configuration and whose category list has been under correction; the board
	should not inherit that drift.
5. **A due date is a local calendar day, stored at 12:00.** The store already
	does this (`taskupdate.parse_due` stores noon), and it is what makes
	"today is not overdue" true at 09:00. *Rejected:* midnight (an off-by-one
	on every day count) and storing a time of day (a due date has no time).
6. **Calendar-day arithmetic for every count and label.** `overdue` is a date
	comparison, not `due_ts < now`. *Rejected:* timestamp comparison, which
	calls today's noon due overdue in the morning and makes the summary depend
	on the hour it was read.
7. **Single-row edits only.** No bulk edit, no drag-and-drop, no undo in this
	version. *Rejected:* bulk editing (the operation this tool replaces is a
	handful of rows at a time; bulk can come later) and drag-to-reorder (which
	would have to invent what a drag *means* when order is a due date).
8. **Writes are full-row appends through `taskupdate.append_row`, guarded by
	`chg_ts`.** One writer shape, one fold, no second source of truth.
	*Rejected:* a second writer in the server (two implementations of the row
	format) and a cross-process file lock (`taskupdate` would have to take it
	too; the residual race is the store's documented last-write-wins model, and
	the guard narrows it, R28).
9. **The server computes labels and owns the grammar; the page is thin.**
	`due_label` comes from `fmt_due`, so the board and the pane word dates
	identically, and the edit grammar is one tested function rather than two
	implementations. *Rejected:* formatting in JavaScript, which would give the
	repo a second date formatter with its own edge cases.
10. **A strict content policy with separate asset files.** The page needs no
	inline code, so the policy can forbid it. *Rejected:* inline script and
	style, which would require `'unsafe-inline'` and weaken the one header that
	stops a scripting mistake.
11. **A threaded server with a process-wide write lock.** Two tabs, or a poll
	overlapping a write, must not block on a keep-alive connection. *Rejected:*
	a single-threaded server, which deadlocks the second tab behind the first
	one's idle connection.
12. **A token only off loopback, carried by a cookie after one bootstrap URL.**
	Local use stays frictionless; a LAN bind must not be a writable task store
	with no password. *Rejected:* a token on every request (it lands in history
	and referrers) and no auth at all (the LAN case is exactly when it
	matters).
13. **No TLS in this version.** *Rejected:* a self-signed certificate (every
	browser warns, and the tool would carry key management). The consequence —
	the token is in cleartext on the LAN — is stated under *What the human will
	notice* rather than hidden.
14. **The tool lives in `tools/taskboard/` and imports the taskview modules.**
	It is a tool beside `taskview`, not a mode of it: R44 of that spec says
	`list` must not grow into the wide view. *Rejected:* a `--wide` flag on
	`taskview` (one renderer pretending to be two) and a `dev/` library (this is
	not a library).
15. **Port 8780, no fallback.** *Rejected:* trying the next free port, which
	makes "which instance am I looking at" unanswerable.
16. **The summary is `summarise`, not `compute_metrics`.** The selection is
	reused; the buckets are not, because `compute_metrics` is pane-shaped —
	rolling 7/30-day windows, done counts, and no overdue or undated count.
	*Rejected:* reusing `compute_metrics` and relabelling its windows, which
	would put two definitions of "this week" in one tool.
17. **The name is `taskboard`** — **[CONFIRM]**. It is the board of all tasks;
	`taskview` stays the pane. *Rejected:* `taskwide` (describes the shape, not
	the thing).
18. **Done and cancelled tasks are neither shown nor editable.** The wide view
	is about work that is still open. *Rejected:* a show-done toggle, which adds
	a state, a filter and a class of accidental edits for no part of the stated
	job.

## What the human will notice

- **It does not start itself.** Run it, open the printed URL; a tmux panel is
	the natural home, beside the pane it complements.
- **Edits are live everywhere.** The board re-reads the CSV on every poll, so
	an agent's write appears within two seconds; the pane picks the same change
	up on its next watch redraw, and `TASKS.md` follows when the secretary next
	updates the state files.
- **On a LAN it is plain HTTP.** Anyone who can watch the network can see the
	token and therefore edit the store. Use it on a network you trust, or leave
	it on loopback.
- **It shows the bucket.** Uncategorised tasks are in this list and in no
	project pane; that is the point of the view, and it will look larger than a
	project pane does.
- **A due date is a day.** It is stored at noon local time; crossing a time
	zone or a DST boundary moves the instant, not the day.

## Open for the human

- Whether to build it, and when. This spec is the deliverable of `E5MH4S2`;
	implementation is a separate ticket once the spec is approved.
- The three **[CONFIRM]** decisions above (the tie-break, the unfiltered
	view and the name).

## Interfaces

Names and signatures are part of the contract; behaviour is in the
requirements. The functions are importable without side effects, and every one
that needs the time takes `now` (epoch seconds) or `today` (a `date`).

The store is resolved with `taskview.resolve_data_dir` and
`taskview.resolve_csv` (that spec's R17–R18) and read with
`taskview.read_csv` and `taskview.select_tasks` (R36–R37, R14–R16). Those four
names are imported, never reimplemented.

```python
def parse_due_edit(value: str, current_due_ts: int | None, now: int) -> int | None
	# R10. Returns the new due_ts, or None to clear it. Raises InvalidDue
	# (message for the page) on anything else.

def order_tasks(tasks: list[dict]) -> list[dict]
	# R4. Pure; returns a new list in board order.

def summarise(tasks: list[dict], now: int) -> dict
	# R5. Keys: open, overdue, today, this_week, later, undated.

def task_payload(task: dict, now: int) -> dict
	# R6. One task as the page receives it.

def read_board(csv_path: Path, now: int) -> dict
	# R3, R7. The full payload. Raises StoreMissing.

def set_due(csv_path: Path, task_id: int, new_due_ts: int | None,
		expected_chg_ts: int, now: int) -> dict
	# R11, R12. Returns the full payload after the append. Raises TaskNotFound,
	# TaskNotOpen, TaskChanged(current=dict) and StoreMissing.
```

`taskupdate.fmt_due` gains an optional `today: date | None` argument so R6 and
its tests can pin the wording; with the argument omitted its output is
unchanged. That is the only change this spec makes to an existing module.
