from ._ import watcher,notifier

#Events
REMOVE = notifier.REMOVE #0 - file moved out of scope or removed.
CREATE = notifier.CREATE #1 - file moved into scopre or created.
CHANGE = notifier.CHANGE #2 - file changed.
def watch(callback,paths:list[str],excludes:list[str]):
	"""
	On every set of file changes, callback is called.
	Example callback:
	watch_callback(events):
		for evt,path in events:
			#do stuff
	Each event is a tuple of event type and file path.
	"""
	watcher.watch(callback,paths,excludes)
