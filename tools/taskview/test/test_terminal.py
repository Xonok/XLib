"""The watch owns the pane: hidden cursor, alternate screen, inotify first.

The cursor and the alternate screen are one context manager because they are
one decision — a live view must not draw a cursor into its own output, and the
frames it replaces must not pile up in scrollback. inotify is the file source;
polling is what remains when the kernel has nothing to offer.
"""
import io,os,sys,tempfile
from contextlib import redirect_stdout
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.taskview import taskview

def test_the_watch_hides_the_cursor_and_uses_the_alternate_screen():
	out = io.StringIO()
	with redirect_stdout(out):
		with taskview._fullscreen():
			print("a frame")
	text = out.getvalue()
	xtest.true(text.startswith("\033[?25l\033[?1049h"), "the screen is taken before the first frame")
	xtest.true(text.endswith("\033[?25h\033[?1049l"), "the cursor and the old screen come back")
	xtest.contains("a frame", text)

def test_the_screen_is_given_back_when_the_body_raises():
	out = io.StringIO()
	raised = False
	try:
		with redirect_stdout(out):
			with taskview._fullscreen():
				raise RuntimeError("boom")
	except RuntimeError:
		raised = True
	xtest.true(raised, "the error still reaches the caller")
	xtest.true(out.getvalue().endswith("\033[?25h\033[?1049l"), "an exception does not leave the pane taken")

def test_inotify_reports_a_write_to_a_watched_file():
	if not taskview.HAS_INOTIFY:
		return "skipped: inotify is not available on this machine"
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "tasks.csv"
		path.write_text("", encoding="utf-8")
		watcher = taskview._Inotify()
		try:
			watcher.add(Path(folder))
			path.write_text("id\n", encoding="utf-8")
			events = watcher.read(1.0)
		finally:
			watcher.close()
	xtest.true(
		any(watched == path and mask & (taskview._IN_CLOSE_WRITE | taskview._IN_MODIFY) for mask, watched in events),
		f"the write was reported: {events}")

def test_polling_is_the_fallback_when_inotify_is_missing():
	saved = taskview._libc
	taskview._libc = None
	try:
		raised = False
		try:
			taskview._Inotify()
		except OSError:
			raised = True
		xtest.true(raised, "no inotify means the caller is told to poll")
	finally:
		taskview._libc = saved

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
