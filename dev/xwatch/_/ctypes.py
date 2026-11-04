import ctypes,os,pathlib,select,struct

_EVENT_HEADER = struct.Struct("=iIII")
_IN_MODIFY = 0x00000002
_IN_CLOSE_WRITE = 0x00000008
_IN_MOVED_TO = 0x00000080
_IN_CREATE = 0x00000100
_IN_DELETE = 0x00000200
_IN_DELETE_SELF = 0x00000400
_IN_MOVE_SELF = 0x00000800
_WATCH_MASK = _IN_MODIFY | _IN_CLOSE_WRITE | _IN_MOVED_TO | _IN_CREATE | _IN_DELETE | _IN_DELETE_SELF | _IN_MOVE_SELF
try:
	_libc = ctypes.CDLL(None, use_errno=True)
	_libc.inotify_init.restype = ctypes.c_int
	_libc.inotify_init.argtypes = []
	_libc.inotify_add_watch.restype = ctypes.c_int
	_libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
	HAS_INOTIFY = True
except AttributeError:
	_libc = None
	HAS_INOTIFY = False

obj_inotify = dict

def inotify_init() -> obj_inotify:
	if _libc is None:
		 raise OSError("inotify is not available")
	fd = _libc.inotify_init()
	if fd == -1:
		raise OSError(ctypes.get_errno(), "inotify_init failed")
	return {
		"fd": fd,
		"dir": {}
	}
def inotify_add_watch(obj_inotify,path):
	wd = _libc.inotify_add_watch(obj_inotify["fd"],os.fsencode(path),_WATCH_MASK)
	if wd == -1:
		raise OSError(ctypes.get_errno(), "inotify_add_watch failed")
	#explain: give examples of the path before and after
	blahpath = pathlib.Path(path)
	obj_inotify["dir"][wd] = blahpath
def inotify_read(obj_inotify,timeout):
	fd = obj_inotify["fd"]
	ready,_,_ = select.select([fd],[],[],timeout)
	if not ready:
		return []
	raw = os.read(fd,65536)
	events = []
	offset = 0
	while offset < len(raw):
		wd,mask,_,namelen = _EVENT_HEADER.unpack_from(raw,offset)
		offset += _EVENT_HEADER.size
		name = raw[offset:offset+namelen].split(b"\0",1)[0]
		#explain: what do & and ~ do?
		offset += (namelen+3) & ~3
		base = obj_inotify["dir"].get(wd)
		if wd in obj_inotify["dir"]:
			events.append((mask,base/os.fsdecode(name) if name else base))
	return events
def inotify_close(obj_inotify):
	fd = obj_inotify["fd"]
	if fd != -1:
		os.close(fd)
	obj_inotify["fd"] = -1
	obj_inotify["dir"] = {}
