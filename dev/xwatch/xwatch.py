"""
This is a fast prototype, not meant to be the final version.
"""
from _ import watcher

def watch(paths: list[str],callback,interval=0.5):
	watcher.watch(paths,callback,interval)
