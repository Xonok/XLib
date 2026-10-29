# marduk — terminal contract

Requirements for the live pane. A change that drops one is a regression even if
the panel still updates.

- **No blinking cursor.** Watch mode hides the cursor on entry and shows it on
	every exit path — Ctrl-C, SIGTERM, an exception. `--once` leaves it alone.
- **No scrollback beyond the current state.** Watch mode draws in the terminal's
	alternate screen, so a replaced frame cannot accumulate in scrollback; the
	normal screen returns on exit. `--once` output is unchanged.
- **Fits the height.** The feeds line and the header stay at the top; the body
	is capped at the pane height, and what it leaves out becomes `… +N more`. A
	full frame does not end in a newline.
- **Fits the width.** Below 46 columns the panel switches to the compact
	layout; long names, ages and details are cut to the pane width rather than
	wrapped.
- **No typed input reaches the screen.** Watch mode disables terminal echo so
	text typed while the watch runs does not appear; control signals such as
	Ctrl-C still work. `--once` leaves the terminal alone.

Enforced by `test/test_terminal.py` (cursor, alternate screen, echo) and
`test/test_panel.py` (height cap, overflow note, compact switch, width sweep).
