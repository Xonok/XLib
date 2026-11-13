"""
INTENT
This will be turned into a standalone xlib library once stable and useful.
Release before watcher
"""

import ctypes,os,select,struct

EVENT_HEADER = struct.Struct("=iIII")
MODIFY = 0x00000002
CLOSE_WRITE = 0x00000008
MOVED_FROM = 0x00000040
MOVED_TO = 0x00000080
CREATE = 0x00000100
DELETE = 0x00000200
DELETE_SELF = 0x00000400
MOVE_SELF = 0x00000800
Q_OVERFLOW = 0x00004000
IS_IGNORED = 0x00008000
IS_DIR = 0x40000000
IO = MODIFY | CLOSE_WRITE | MOVED_FROM | MOVED_TO | CREATE | DELETE | DELETE_SELF | MOVE_SELF
INFO = Q_OVERFLOW | IS_IGNORED | IS_DIR
WATCH_MASK = IO
try:
	_libc = ctypes.CDLL(None, use_errno=True)
	_libc.inotify_init.restype = ctypes.c_int
	_libc.inotify_init.argtypes = []
	_libc.inotify_add_watch.restype = ctypes.c_int
	_libc.inotify_add_watch.argtypes = [ctypes.c_int,ctypes.c_char_p,ctypes.c_uint32]
	_libc.inotify_rm_watch.restype = ctypes.c_int
	_libc.inotify_rm_watch.argtypes = [ctypes.c_int,ctypes.c_int]
	HAS_INOTIFY = True
except AttributeError:
	HAS_INOTIFY = False

def create():
	if not HAS_INOTIFY:
		 raise OSError("inotify is not available")
	fd = _libc.inotify_init()
	if fd == -1:
		raise OSError(ctypes.get_errno(), "inotify_init failed")
	return fd
def add_watch(fd,path):
	wd = _libc.inotify_add_watch(fd,os.fsencode(path),WATCH_MASK)
	if wd == -1:
		raise OSError(ctypes.get_errno(), "inotify_add_watch failed")
	return wd
def remove_watch(fd,wd):
	_libc.inotify_rm_watch(fd,wd)
def read_events(fd,timeout):
	ready,_,_ = select.select([fd],[],[],timeout)
	if not ready:
		return []
	raw = os.read(fd,65536)
	events = []
	offset = 0
	while offset < len(raw):
		wd,mask,_,namelen = EVENT_HEADER.unpack_from(raw,offset)
		offset += EVENT_HEADER.size
		name = raw[offset:offset+namelen].split(b"\0",1)[0]
		offset += (namelen+3) & ~3
		path = os.fsdecode(name) if name else ""
		events.append((wd,mask,path))
	return events
def destroy(fd):
	if fd != -1:
		os.close(fd)
class notifier:
	def __init__(self):
		self.fd = create()
		self.paths = {}
	def add_watch(self,path):
		wd = add_watch(self.fd,path)
		self.paths[wd] = path
	def read(self,timeout):
		events = read_events(self.fd,timeout)
		"""
		Want to process events to a form that's useful to outsiders.
		Cases:
		*File modified: True
		*Nothing meaningful happened: False(gets dropped in watcher)
		*File no longer in scope: None(deleted or moved away, remove from watch list)

		Also, maybe the ctypes library should be more boring and
		just do any special-casing done in watcher?
		That sounds better.
		"""
		return [(self.paths[wd],evt) for wd,evt in events]
	def destroy(self):
		destroy(self.fd)
