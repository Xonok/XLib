"""The watch owns the pane, and the database wakes it through inotify.

Skynet used to stat the database once a second. That is polling even when the
kernel could have said exactly when it changed, so the watch now listens on
the database's directory and only falls back to the stamp when inotify is
not there.
"""
import io,os,sys,tempfile
from contextlib import redirect_stdout
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, os.path.join(REPO, "tools"))

import xtest
import skynet

def test_the_watch_hides_the_cursor_and_uses_the_alternate_screen():
	out = io.StringIO()
	with redirect_stdout(out):
		with skynet._fullscreen():
			print("a frame")
	text = out.getvalue()
	xtest.true(text.startswith("\033[?25l\033[?1049h"), "the screen is taken before the first frame")
	xtest.true(text.endswith("\033[?25h\033[?1049l"), "the cursor and the old screen come back")

def test_the_screen_is_given_back_when_the_body_raises():
	out = io.StringIO()
	raised = False
	try:
		with redirect_stdout(out):
			with skynet._fullscreen():
				raise RuntimeError("boom")
	except RuntimeError:
		raised = True
	xtest.true(raised, "the error still reaches the caller")
	xtest.true(out.getvalue().endswith("\033[?25h\033[?1049l"), "an exception does not leave the pane taken")

def test_inotify_reports_a_write_to_a_watched_file():
	if not skynet.HAS_INOTIFY:
		return "skipped: inotify is not available on this machine"
	with tempfile.TemporaryDirectory() as folder:
		path = Path(folder) / "opencode.db"
		path.write_text("", encoding="utf-8")
		watcher = skynet._Inotify()
		try:
			watcher.add(Path(folder))
			path.write_text("data", encoding="utf-8")
			events = watcher.read(1.0)
		finally:
			watcher.close()
	xtest.true(
		any(watched == path and mask & (skynet._IN_CLOSE_WRITE | skynet._IN_MODIFY) for mask, watched in events),
		f"the write was reported: {events}")

def test_there_is_no_database_watch_when_inotify_is_missing():
	saved = skynet.HAS_INOTIFY
	skynet.HAS_INOTIFY = False
	try:
		xtest.equal(skynet._db_watcher(), None, "the caller is told to use the stamp")
	finally:
		skynet.HAS_INOTIFY = saved

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
