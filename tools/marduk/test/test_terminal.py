"""Marduk owns the pane, and watches its files through inotify itself.

The port watcher used a third-party module that is not installed on this
machine, so the fallback was the only path it ever took. The reader in
`_.inotify` asks the kernel directly; these tests hold that reader and the
screen contract in place.
"""
import io,os,sys,tempfile
from contextlib import redirect_stdout
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk import marduk
from tools.marduk._ import inotify as inotify_mod

def test_the_watch_hides_the_cursor_and_uses_the_alternate_screen():
	out = io.StringIO()
	with redirect_stdout(out):
		with marduk._fullscreen():
			print("a frame")
	text = out.getvalue()
	xtest.true(text.startswith("\033[?25l\033[?1049h"), "the screen is taken before the first frame")
	xtest.true(text.endswith("\033[?25h\033[?1049l"), "the cursor and the old screen come back")

def test_the_screen_is_given_back_when_the_body_raises():
	out = io.StringIO()
	raised = False
	try:
		with redirect_stdout(out):
			with marduk._fullscreen():
				raise RuntimeError("boom")
	except RuntimeError:
		raised = True
	xtest.true(raised, "the error still reaches the caller")
	xtest.true(out.getvalue().endswith("\033[?25h\033[?1049l"), "an exception does not leave the pane taken")

def test_inotify_reports_a_file_created_in_a_watched_directory():
	if not inotify_mod.available():
		return "skipped: inotify is not available on this machine"
	with tempfile.TemporaryDirectory() as folder:
		watcher = inotify_mod.Inotify()
		try:
			watcher.add(Path(folder))
			path = Path(folder) / "1234.json"
			path.write_text("{}", encoding="utf-8")
			events = watcher.read(1.0)
		finally:
			watcher.close()
	xtest.true(
		any(watched == path and mask & inotify_mod.IN_CREATE for mask, watched in events),
		f"the creation was reported: {events}")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
