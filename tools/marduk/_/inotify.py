"""A minimal inotify reader: the syscall is the interface, nothing to install.

The monitoring tools used to import a third-party package and fall back to
polling when it was missing. On this machine it was missing, so the fallback
was the only path ever taken. This module asks the kernel directly, and
`available()` is the one question the callers ask before deciding to poll.
"""

import ctypes,os,select,struct
from pathlib import Path

_EVENT_HEADER = struct.Struct("=iIII")
IN_MODIFY = 0x00000002
IN_CLOSE_WRITE = 0x00000008
IN_MOVED_FROM = 0x00000040
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100
IN_DELETE = 0x00000200
IN_DELETE_SELF = 0x00000400
IN_MOVE_SELF = 0x00000800
WATCH_MASK = (IN_MODIFY | IN_CLOSE_WRITE | IN_MOVED_FROM | IN_MOVED_TO |
	IN_CREATE | IN_DELETE | IN_DELETE_SELF | IN_MOVE_SELF)
try:
	_libc = ctypes.CDLL(None, use_errno=True)
	_libc.inotify_init.restype = ctypes.c_int
	_libc.inotify_init.argtypes = []
	_libc.inotify_add_watch.restype = ctypes.c_int
	_libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
except AttributeError:
	_libc = None

def available():
	"""Whether this kernel has inotify to offer."""
	return _libc is not None

class Inotify:
	"""A watch on one or more directories, read one timeout at a time."""

	def __init__(self):
		if _libc is None:
			raise OSError("inotify is not available")
		self.fd = _libc.inotify_init()
		if self.fd == -1:
			raise OSError(ctypes.get_errno(), "inotify_init failed")
		self.dirs = {}

	def add(self, path):
		"""Watch one directory; a failure is the caller's cue to poll."""
		wd = _libc.inotify_add_watch(self.fd, os.fsencode(path), WATCH_MASK)
		if wd == -1:
			raise OSError(ctypes.get_errno(), "inotify_add_watch failed")
		self.dirs[wd] = Path(path)

	def read(self, timeout):
		"""The (mask, path) changes in the next `timeout` seconds, if any."""
		ready, _, _ = select.select([self.fd], [], [], timeout)
		if not ready:
			return []
		raw = os.read(self.fd, 65536)
		events = []
		offset = 0
		while offset < len(raw):
			wd, mask, _, namelen = _EVENT_HEADER.unpack_from(raw, offset)
			offset += _EVENT_HEADER.size
			name = raw[offset:offset + namelen].split(b"\0", 1)[0]
			offset += (namelen + 3) & ~3
			base = self.dirs.get(wd)
			if base is not None:
				events.append((mask, base / os.fsdecode(name) if name else base))
		return events

	def close(self):
		"""Release the descriptor and every watch on it."""
		if self.fd != -1:
			os.close(self.fd)
			self.fd = -1
