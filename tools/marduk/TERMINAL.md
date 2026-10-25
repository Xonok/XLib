# marduk — terminal contract

Requirements for the live pane. A change that drops one is a regression even if
the panel still updates.

- **No blinking cursor.** Watch mode hides the cursor on entry and shows it on
	every exit path — Ctrl-C, SIGTERM, an exception. `--once` leaves it alone.
- **No scrollback beyond the current state.** Watch mode draws in the terminal's
	alternate screen, so a replaced frame cannot accumulate in scrollback; the
	normal screen returns on exit. `--once` output is unchanged.
- **inotify first, polling only when it is unavailable.** Port files, the
	registry and the instance reports are read from inotify through
	`_.inotify`; polling is the fallback for a kernel that has no inotify. The
	service API is still asked on the poll interval — it is not a file.
- **Fits the height.** The body is capped at the pane height and what it leaves
	out becomes `… +N more`; the header never scrolls off. A full frame does not
	end in a newline.
- **Fits the width.** Below 46 columns the panel switches to the compact
	layout; long workspace names, roles and details are cut to the pane width
	rather than wrapped.

- **No typed input reaches the screen.** Watch mode disables terminal echo so
	text typed while the watch runs does not appear; control signals such as
	Ctrl-C still work. `--once` leaves the terminal alone.

Enforced by `test/test_terminal.py` (cursor, alternate screen, inotify) and
`test/test_panel.py` (height cap, overflow note, compact switch, width sweep).
