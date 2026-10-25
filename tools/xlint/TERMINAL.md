# xlint — terminal contract

Requirements for `--watch`. A change that drops one is a regression even if the
report still prints.

- **No blinking cursor.** Watch mode hides the cursor on entry and shows it on
	every exit path — Ctrl-C, SIGTERM, an exception. One-shot runs leave it
	alone.
- **The scrollback holds the current report only.** Watch stays on the normal
	screen (not the alternate screen) and starts every redraw with
	`ESC[H ESC[2J ESC[3J` — home, clear the screen, then erase the saved lines.
	The order is part of the contract: tmux moves the cleared screen into
	history on `2J`, so erasing the saved lines first leaves one screenful of
	the previous report behind. Previous iterations are erased; the current
	report's lines above the fold remain in scrollback, where they can be
	reached.
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
- **A degraded watch says so in the report.** When `inotify_init` or
	`inotify_add_watch` fails, the report carries the syscall, the errno and the
	sysctl knobs that fix it — for as long as the degradation lasts, because a
	notice printed once would be erased by the next redraw, which clears the
	saved lines. A directory that could not be watched is named.

One-shot runs print directly: no clearing, no cursor sequences, no `ESC[3J`.

- **No typed input reaches the screen.** Watch mode disables terminal echo so
	text typed while the watch runs does not appear; control signals such as
	Ctrl-C still work. One-shot runs leave the terminal alone.

Enforced by `test/test_watch.py` (process-level cursor, no alternate screen,
`ESC[H ESC[2J ESC[3J]` in that order, rule reload) and
`test/test_watch_notices.py` (the failure, its errno, the knobs, and the
notice in the report).
