# taskview — terminal contract

Requirements for the pane. A change that drops one is a regression even if the
display still renders.

- **No blinking cursor.** `--watch` hides the cursor on entry and shows it on
	every exit path — Ctrl-C, SIGTERM, an exception. One-shot runs leave it
	alone.
- **No scrollback beyond the current state.** `--watch` draws in the terminal's
	alternate screen, so a replaced frame cannot accumulate in scrollback; the
	normal screen returns on exit. One-shot output is unchanged.
- **inotify first, polling only when it is unavailable.** CSV and filter changes
	are read from inotify through `ctypes`. Polling is the fallback for a kernel
	that has no inotify, not a parallel refresh path.
- **Fits the height.** The number of full-detail tasks comes from the height,
	then the view drops PACE, then QUEUE, then UPCOMING rows, then the header
	last (R50). Descriptions truncate with `...` when space is short.
- **Fits the width.** Every rendered line is cut to the terminal width; a
	narrow pane must not wrap a line into a second row. The QUEUE summary was
	the case that used to wrap.

- **No typed input reaches the screen.** Watch mode disables terminal echo so
	text typed while the watch runs does not appear; control signals such as
	Ctrl-C still work. One-shot runs leave the terminal alone.

Enforced by `test/test_terminal.py` (cursor, alternate screen, inotify) and
`test/test_taskview.py` (the height and width sweeps).
