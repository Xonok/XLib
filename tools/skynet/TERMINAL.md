# skynet — terminal contract

Requirements for the pane. A change that drops one is a regression even if the
numbers still add up.

- **No blinking cursor.** `--watch` hides the cursor on entry and shows it on
	every exit path — Ctrl-C, SIGTERM, an exception. One-shot runs leave it
	alone.
- **No scrollback beyond the current state.** `--watch` draws in the terminal's
	alternate screen, so a replaced frame cannot accumulate in scrollback; the
	normal screen returns on exit. One-shot output is unchanged.
- **inotify first, polling only when it is unavailable.** Database changes are
	read from inotify on the database's directory, through `ctypes`. The wakeup
	is only a hint: it redraws when `db_stamp()` changed, so the WAL and
	shared-memory files that SQLite opens and closes for a read cannot wake the
	tool into redrawing itself. Polling is the fallback for a kernel that has no
	inotify, not a parallel refresh path.
- **Fits the height.** The two tables split the rows the pane has; a section
	that leaves rows out says `… +N more`; below six lines the display falls
	back to the one-line counts. A full frame never scrolls its header away.
- **Fits the width.** Model names are truncated and columns are dropped as the
	pane narrows — `Tot` first, then `In`, `Out`, `Ref`, `Msgs` — and the title
	becomes `Today` / `Window` when the full one no longer fits. Every line is
	at most the pane width.

- **The quota section is one line per source, right-aligned.** The first
	source shares the `=== Skynet ===` title line; each further configured
	source gets its own line, in the order Go, Cursor, Cursor/other,
	OpenRouter. Every line's block sits against the pane's right edge, with the
	space after the title absorbing the spare columns, so the first block does
	not read as part of the title. A line never wraps: its labels abbreviate
	(`G`, `C`, `C/o`, `p`, `t`) and then that source's fields drop from the
	right, so one source narrowing never removes another. `today` is the
	source's spend as a percentage of its sustainable daily allowance; Go takes
	it from the first reading after UTC midnight, while Cursor counts it from
	its message log. `pace` is the average rate with `%/d`. The subscription
	reset is rounded to the nearest UTC midnight for the pace, and `(Nd left)`
	is shown where the source has a known end. A configured source that cannot
	be read shows `?`; one that is not configured is omitted. The read is
	synchronous with a three-second timeout and a failure never removes a
	table.

- **No typed input reaches the screen.** Watch mode disables terminal echo so
	text typed while the watch runs does not appear; control signals such as
	Ctrl-C still work. One-shot runs leave the terminal alone.

Enforced by `test/test_render.py` (height and width sweeps),
`test/test_terminal.py` (cursor, alternate screen, inotify),
`test/test_render_table.py` and `test/test_quota.py` (the quota line).
