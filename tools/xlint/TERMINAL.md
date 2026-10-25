# xlint — terminal contract

Requirements for `--watch`. A change that drops one is a regression even if the
report still prints.

- **No blinking cursor.** Watch mode hides the cursor on entry and shows it on
	every exit path — Ctrl-C, SIGTERM, an exception. One-shot runs leave it
	alone.
- **The scrollback holds the current report only.** Watch stays on the normal
	screen (not the alternate screen) and starts every redraw with `ESC[3J`
	(erase saved lines). Previous iterations are erased; the current report's
	lines above the fold remain in scrollback, where they can be reached.
- **The reader's scroll position survives a redraw.** If the view is scrolled
	up, the same line index is kept when the report changes; if it is at the
	bottom, it stays at the bottom and follows the new end. This is why watch
	mode must not use the alternate screen: the screen there has no history.
- **Fitting is not required.** The error list can be taller than the pane, and
	scrollback is how the earlier errors stay reachable. Lines are not
	truncated to the width either.
- **inotify first, polling only when it is unavailable.** File changes are read
	from inotify through `ctypes`. Polling is the fallback for a kernel that has
	no inotify, not a parallel refresh path.

One-shot runs print directly: no clearing, no cursor sequences, no `ESC[3J`.

Enforced by `test/test_watch.py` (process-level cursor, no alternate screen,
`ESC[3J`, rule reload).
