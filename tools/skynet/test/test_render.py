"""The display fits the room it is given, and says what it left out.

The caps on the two tables come from the terminal's height, what is left of
the room is split evenly between them, a table that had to drop rows says how
many it dropped — a truncated table must never be mistaken for the whole truth
— and the room a section does not need goes to the section that has more to
show.
"""
import os,sys,time

# xtest and the tool under test are found relative to this file rather than to
# the working directory: a test that passes from one directory and fails from
# another is worse than one that never runs.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, os.path.join(REPO, "tools"))
import xtest
import skynet

NOW = time.time()

def _rows(count):
	"""`count` assistant messages, one per model, each its own model."""
	return [("model-%02d" % i, NOW, 100, 100, 1000 - i, 0, 0, 0, None, None, "stop", "session")
		for i in range(count)]

def _older_rows(count):
	"""`count` models used before today, so the window holds them and Today does not."""
	return [("older-%02d" % i, NOW - 3 * 86400, 100, 100, 1000 - i, 0, 0, 0, None, None, "stop", "session")
		for i in range(count)]

class _NotATerminal:
	"""A stdout that is a file rather than a terminal."""

	def isatty(self):
		return False

def test_the_room_left_is_split_evenly():
	today, window = skynet.section_allowances(26, 100, 100)
	xtest.equal((today, window), (10, 10), "an even budget splits evenly")

def test_an_odd_line_goes_to_today():
	today, window = skynet.section_allowances(25, 100, 100)
	xtest.equal((today, window), (10, 9), "the odd line goes to Today")

def test_a_section_that_has_more_to_show_takes_the_room_the_other_leaves():
	today, window = skynet.section_allowances(30, 1, 100)
	xtest.equal(today, 1, "Today takes the one line it needs, and no more")
	xtest.equal(window, 23, "Window takes the rest: the room goes where there is something to show")

def test_a_section_that_has_more_to_show_keeps_the_even_split_when_both_need_it():
	today, window = skynet.section_allowances(30, 100, 100)
	xtest.equal((today, window), (12, 12), "both sections want the room, so the split stands")

def test_the_note_costs_a_row_of_its_own():
	xtest.equal(skynet.row_cap(5, 4), 3, "four lines of room show three rows and a note")

def test_a_table_that_fits_shows_every_row():
	xtest.equal(skynet.row_cap(3, 4), 3, "no note is needed, so no row is given up")

def test_a_capped_table_says_how_many_rows_it_left_out():
	by_model = skynet.aggregate(_rows(5), NOW)
	out = skynet.render_table(by_model, NOW, max_models=3)
	xtest.contains("… +2 more", out)

def test_a_table_that_shows_everything_has_no_note():
	by_model = skynet.aggregate(_rows(3), NOW)
	out = skynet.render_table(by_model, NOW, max_models=3)
	xtest.not_equal("more" in out, True)

def test_the_display_never_exceeds_the_room_it_is_given():
	rows = _rows(30)
	for height in range(1, 61):
		out = skynet.render(rows, NOW, height=height)
		xtest.true(len(out.splitlines()) <= height,
			f"a display of {height} lines must not run past {height}")

def test_the_display_uses_the_room_it_is_given():
	out = skynet.render(_rows(30), NOW, height=30)
	xtest.equal(len(out.splitlines()), 30, "thirty lines of room, thirty lines of display")

def test_both_sections_say_what_they_left_out():
	out = skynet.render(_rows(30), NOW, height=30)
	xtest.equal(out.count("… +"), 2, "both sections carry a note")
	xtest.contains("… +19 more", out, "each of them leaves nineteen of thirty out")

def test_the_today_section_gets_a_row_limit():
	out = skynet.render(_rows(30), NOW, height=24)
	today = out.split("=== Models (Window) ===")[0]
	rows = [line for line in today.splitlines() if line.startswith("model-")]
	xtest.equal(len(rows), 8, "Today shows eight rows, and a note for the rest")

def test_the_window_section_takes_the_room_that_today_leaves():
	rows = _rows(1) + _older_rows(30)
	out = skynet.render(rows, NOW, height=30)
	window = out.split("=== Models (Window) ===")[1]
	shown = [line for line in window.splitlines()
		if line.startswith("model-") or line.startswith("older-")]
	xtest.equal(len(shown), 22, "Window shows every row the room allows, not the half it was given")
	xtest.equal(len(out.splitlines()), 30, "and the display fills the room it was given")

def test_the_display_never_exceeds_the_room_when_one_section_is_small():
	rows = _rows(1) + _older_rows(30)
	for height in range(1, 61):
		out = skynet.render(rows, NOW, height=height)
		xtest.true(len(out.splitlines()) <= height,
			f"a display of {height} lines must not run past {height}")

def test_the_title_carries_the_column_labels():
	out = skynet.render(_rows(3), NOW, height=24)
	title = out.splitlines()[1]
	xtest.contains("=== Models (Today) ===", title, "the title is the model column's header")
	xtest.contains("Msgs", title, "the column labels ride along on the title's line")
	xtest.not_equal(title.startswith("Model"), True, "the 'Model' label is gone")

def test_the_today_section_comes_first():
	out = skynet.render(_rows(30), NOW, height=30)
	xtest.true(out.index("=== Models (Today) ===") < out.index("=== Models (Window) ==="),
		"Today is the view about now, so it comes first")

def test_a_short_pane_still_says_what_it_left_out():
	out = skynet.render(_rows(30), NOW, height=12)
	xtest.true(len(out.splitlines()) <= 12, "twelve lines of room")
	xtest.contains("more", out, "a pane too short for the rows still says how many it left out")

def test_a_pane_with_no_room_for_a_row_still_tells_the_truth():
	out = skynet.render(_rows(30), NOW, height=9)
	xtest.true(len(out.splitlines()) <= 9, "nine lines of room")
	xtest.contains("… +30 more", out, "the note is all that fits, and it names the whole truth")

def test_a_pane_too_short_for_the_sections_gets_the_counts():
	out = skynet.render(_rows(30), NOW, height=5)
	xtest.equal(len(out.splitlines()), 1, "one line is all a five-line pane can hold")
	xtest.contains("30 models today", out, "the counts are what the two sections would have said")
	xtest.contains("30 models in window", out)

def test_the_display_fits_the_terminal_it_runs_in():
	out = skynet.render(_rows(30), NOW)
	xtest.true(len(out.splitlines()) <= skynet.terminal_size().lines,
		"the display must fit the terminal it runs in")

def test_the_display_never_exceeds_the_width_it_is_given():
	rows = _rows(30)
	for width in range(20, 121):
		out = skynet.render(rows, NOW, height=24, width=width)
		xtest.true(all(len(line) <= width for line in out.splitlines()),
			f"a display of {width} columns must not run past {width}")

def test_a_long_model_name_is_cut_to_the_model_column():
	rows = [("a-model-name-that-is-far-too-long-for-a-pane", NOW, 100, 100, 1000, 0, 0, 0, None, None, "stop", "s")]
	out = skynet.render(rows, NOW, height=24, width=60)
	xtest.true(all(len(line) <= 60 for line in out.splitlines()), "the table fits sixty columns")
	xtest.contains("…", out, "the cut name says it was cut")

def test_a_narrow_pane_drops_columns_it_cannot_fit():
	out = skynet.render(_rows(3), NOW, height=24, width=40)
	header = out.splitlines()[1]
	xtest.contains("Msgs", header, "the message count stays")
	xtest.not_equal("Tot" in header, True, "Tot is the first column to go")

def test_the_fallback_size_is_used_when_stdout_is_not_a_terminal():
	saved = sys.stdout
	sys.stdout = _NotATerminal()
	try:
		size = skynet.terminal_size()
	finally:
		sys.stdout = saved
	xtest.equal((size.columns, size.lines), (80, 24))

def test_the_display_says_so_when_nothing_happened():
	out = skynet.render([], NOW, height=24)
	xtest.contains("no agents active in window", out)

def test_a_pane_too_short_for_the_sections_says_so_when_nothing_happened():
	out = skynet.render([], NOW, height=5)
	xtest.equal(len(out.splitlines()), 1)
	xtest.contains("no agents active", out)

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
