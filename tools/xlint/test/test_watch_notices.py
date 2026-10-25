"""The watch says when inotify is not doing the watching.

`inotify_init` and `inotify_add_watch` can fail — the instance limit, the watch
limit — and watch mode used to fall back to polling without a word. Polling is
slower and invisible, so the reader had no way to know the watch was degraded
or that a sysctl needed raising.

The notice belongs in the report rather than on stderr: every redraw clears the
screen *and* the saved lines, so anything printed once is gone before a reader
looks. These tests pin the failing call, the errno, the knobs and their
commands, and the notice's place under the report header.
"""
import contextlib,ctypes,errno,io,os,sys,tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "dev" / "xtest"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import xtest
from tools.xlint import xlint

class _FakeLibc:
	"""An inotify that fails where the test says it does, and needs no kernel limit."""

	def __init__(self, fd, add_result, code):
		self.fd = fd
		self.add_result = add_result
		self.code = code
		self.added = []

	def inotify_init(self):
		if self.fd == -1:
			ctypes.set_errno(self.code)
		return self.fd

	def inotify_add_watch(self, fd, path, mask):
		self.added.append(os.fsdecode(path))
		if self.add_result == -1:
			ctypes.set_errno(self.code)
		return self.add_result

@contextlib.contextmanager
def _libc(fake):
	"""Use `fake` as the libc for the duration, and put the real one back."""
	saved = xlint._libc
	xlint._libc = fake
	try:
		yield fake
	finally:
		xlint._libc = saved

def _repo(folder):
	"""A checkout holding one directory to watch."""
	root = Path(folder) / "repo"
	root.mkdir()
	(root / ".git").mkdir()
	return root

def _watcher(root):
	"""An inotify watcher over `root`, through the libc the test installed."""
	return xlint._InotifyWatcher(xlint._IgnoreRules([root]))

def _notices(watcher):
	"""The notice block the report would print, as one string."""
	return "\n".join(watcher.notices())

def test_a_failed_inotify_add_watch_names_the_directory():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		fd = os.open(os.devnull, os.O_RDONLY)
		try:
			with _libc(_FakeLibc(fd, -1, errno.ENOSPC)):
				notices = _notices(_watcher(root))
		finally:
			os.close(fd)
		xtest.contains(str(root), notices, "the directory that is not watched is named")

def test_a_failed_inotify_add_watch_names_the_errno():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		fd = os.open(os.devnull, os.O_RDONLY)
		try:
			with _libc(_FakeLibc(fd, -1, errno.ENOSPC)):
				notices = _notices(_watcher(root))
		finally:
			os.close(fd)
		xtest.contains("ENOSPC", notices, "the errno name is in the notice")

def test_the_notice_says_what_failed_and_what_the_kernel_said():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		fd = os.open(os.devnull, os.O_RDONLY)
		try:
			with _libc(_FakeLibc(fd, -1, errno.ENOSPC)):
				notices = _notices(_watcher(root))
		finally:
			os.close(fd)
		xtest.contains("inotify_add_watch failed", notices, "the failing syscall is named")
		xtest.contains("No space left on device", notices, "the kernel's message is carried")

def test_the_advice_names_the_check_and_set_commands():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		fd = os.open(os.devnull, os.O_RDONLY)
		try:
			with _libc(_FakeLibc(fd, -1, errno.ENOSPC)):
				notices = _notices(_watcher(root))
		finally:
			os.close(fd)
		xtest.contains("cat /proc/sys/fs/inotify/max_user_instances", notices,
			"the check command is there")
		xtest.contains("sudo sysctl -w fs.inotify.max_user_instances=1024", notices,
			"the instance limit is raised in the advice")
		xtest.contains("sudo sysctl -w fs.inotify.max_user_watches=524288", notices,
			"the watch limit is raised in the advice")

def test_a_healthy_inotify_watch_has_no_notice():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		fd = os.open(os.devnull, os.O_RDONLY)
		try:
			with _libc(_FakeLibc(fd, 1, 0)):
				watcher = _watcher(root)
		finally:
			os.close(fd)
		xtest.equal(watcher.notices(), [], "a watch the kernel accepted has nothing to say")

def test_a_failed_inotify_init_falls_back_to_polling():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		with _libc(_FakeLibc(-1, -1, errno.EMFILE)):
			watcher = xlint.make_watcher(xlint._IgnoreRules([root]))
		xtest.kind(watcher, xlint._PollWatcher, "the poll watcher takes over")

def test_a_failed_inotify_init_is_named_in_the_notice():
	with tempfile.TemporaryDirectory() as folder:
		root = _repo(folder)
		with _libc(_FakeLibc(-1, -1, errno.EMFILE)):
			watcher = xlint.make_watcher(xlint._IgnoreRules([root]))
		notices = _notices(watcher)
		xtest.contains("inotify_init failed", notices, "the failing syscall is named")
		xtest.contains("EMFILE", notices, "the errno name is in the notice")
		xtest.contains("polling instead", notices, "the fallback is stated")

def test_the_report_prints_the_notices_under_its_header():
	out = io.StringIO()
	with contextlib.redirect_stdout(out):
		xlint.draw({}, notices=["warning: inotify_init failed: EMFILE (Too many open files)"])
	text = out.getvalue()
	xtest.true(text.index("=== xlint ===") < text.index("warning:") < text.index("clean"),
		"the notice comes after the header and before the verdict")

def test_the_report_is_unchanged_when_the_backend_is_healthy():
	out = io.StringIO()
	with contextlib.redirect_stdout(out):
		xlint.draw({})
	xtest.equal([line for line in out.getvalue().splitlines() if line][1:], ["clean"],
		"a healthy run prints the header and the verdict and nothing else")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
