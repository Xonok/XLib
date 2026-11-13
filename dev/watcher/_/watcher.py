import time
from . import ctypes

def watch(paths,callback,interval=0.5):
	obj_inotify = ctypes.inotify_init()
	for path in paths:
		ctypes.inotify_add_watch(obj_inotify,path)
	while True:
		events = ctypes.inotify_read(obj_inotify,interval)
		callback(events)
		time.sleep(1)
