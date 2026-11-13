from . import notifier,pathutil

def watch(callback,paths,excludes):
	paths = [pathutil.to_native(p) for p in paths]
	excludes = [pathutil.to_native(p) for p in excludes]
	interval = 0.5
	try:
		notify = notifier.notifier(excludes)
	except OSError:
		print("Watcher: no inotify available. Falling back to polling.")
		notify = notifier.fallback_notifier()
	for path in paths:
		notify.add_watch(path)
	
	try:
		while True:
			events = notify.read(interval)
			events_out = {}
			for path,evt in events.items():
				if pathutil.path_in_scope(path,excludes): continue
				if not pathutil.path_in_scope(path,paths): continue
				events_out[path] = evt
			if not len(events_out): continue
			callback(events_out)
	except KeyboardInterrupt:
		print("Interrupted.")
	finally:
		notify.destroy()
