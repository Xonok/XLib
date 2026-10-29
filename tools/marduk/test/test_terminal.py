"""Marduk owns the pane: no cursor, no scrollback and no echo while it runs."""
import io,os,sys
from contextlib import redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk._ import panel

def test_the_watch_hides_the_cursor_and_uses_the_alternate_screen():
	out = io.StringIO()
	with redirect_stdout(out):
		with panel._fullscreen():
			print("a frame")
	text = out.getvalue()
	xtest.true(text.startswith("\033[?25l\033[?1049h"), "the screen is taken before the first frame")
	xtest.true(text.endswith("\033[?25h\033[?1049l"), "the cursor and the old screen come back")

def test_the_screen_is_given_back_when_the_body_raises():
	out = io.StringIO()
	raised = False
	try:
		with redirect_stdout(out):
			with panel._fullscreen():
				raise RuntimeError("boom")
	except RuntimeError:
		raised = True
	xtest.true(raised, "the error still reaches the caller")
	xtest.true(out.getvalue().endswith("\033[?25h\033[?1049l"),
		"an exception does not leave the pane taken")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
