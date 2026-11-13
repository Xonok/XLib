import time,os
from . import inotify,pathutil

REMOVE = 0 #Falsy
CREATE = 1
CHANGE = 2
NONE = 99

class notifier:
	def __init__(self,excludes):
		self.fd = inotify.create()
		self.paths = {}
		self.wds = {}
		self.excludes = excludes
	def add_watch(self,path):
		base = path if os.path.isdir(path) else os.path.dirname(path)
		if pathutil.path_in_scope(base,self.excludes): return
		if base in self.wds: return
		wd = inotify.add_watch(self.fd,base)
		self.wds[base] = wd
		self.paths[wd] = base
		if os.path.isdir(path):
			for fname in os.listdir(path):
				child = os.path.join(path,fname)
				if os.path.isdir(child):
					self.add_watch(child)
	def remove_path(self,path):
		prefix = path + os.sep
		for wd,p in list(self.paths.items()):
			if p == path or p.startswith(prefix):
				inotify.remove_watch(self.fd,wd)
				self.paths.pop(wd,None)
				self.wds.pop(p,None)
	def read(self,timeout):
		events = inotify.read_events(self.fd,timeout)
		events_out = {}
		evt_map = {
			inotify.MODIFY: CHANGE,
			inotify.MOVED_TO: CREATE,
			inotify.MOVED_FROM: REMOVE,
			inotify.CREATE: CREATE,
			inotify.DELETE: REMOVE,
			inotify.DELETE_SELF: REMOVE,
			inotify.MOVE_SELF: REMOVE,
			inotify.CLOSE_WRITE: CHANGE
		}
		for wd,mask,path in events:
			if mask & inotify.IS_IGNORED:
				p = self.paths.pop(wd,None)
				if p is not None:
					self.wds.pop(p,None)
				continue
			if mask & inotify.Q_OVERFLOW:
				#TODO: figure out what to do about this.
				continue
			base = self.paths.get(wd)
			if base is None: continue
			if mask & inotify.IS_DIR:
				fullpath = os.path.join(base,path) if path else base
				if mask & (inotify.CREATE | inotify.MOVED_TO):
					self.add_watch(fullpath)
				elif mask & inotify.MOVED_FROM:
					self.remove_path(fullpath)
			evt = NONE
			for k,v in evt_map.items():
				if mask & k:
					evt = min(evt,v)
			if evt == NONE: continue
			base = self.paths.get(wd)
			if not base: continue
			fullpath = os.path.join(base,path) if path else base
			prev = events_out.get(fullpath,NONE)
			if evt < prev:
				events_out[fullpath] = evt
		return events_out
	def destroy(self):
		inotify.destroy(self.fd)
class fallback_notifier:
	#IGNORE this one for now. I'll get the inotify path correct first.
	def __init__(self):
		self.paths = []
		self.mtimes = {}
	def add_watch(self,path):
		self.paths.append(path)
	def read(self,timeout):
		time.sleep(timeout)
		return self.check_paths()
	def check_file(self,path):
		mtime_old = self.mtimes.get(path)
		file_exists = os.path.exists(path)
		if not file_exists:
			return None
		#mtime_new = ??? #Q: how to get mtime?
		mtime_new = 0 #placeholder
		if mtime_old is None:
			mtime_old = mtime_new
		return mtime_old != mtime_new
	def check_path(self,path,changes=None):
		if changes is None:
			changes = []
		if os.isdir(path):
			paths = os.listdir(path)
			for path2 in paths:
				changes.extend(self.check_path(path2,changes))
		else:
			mtime_new = self.check_file(path)
			if mtime_new != False:
				changes.append(mtime_new)
		return changes
	def check_paths(self):
		events = []
		for path in self.paths:
			changes = self.check_path(path)
			events.extend(changes)
		return events
	def destroy(self):
		pass
