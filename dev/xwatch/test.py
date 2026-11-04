import xwatch

def on_change(events):
	for e in events:
		print(e)
def run():
	try:
		xwatch.watch(["xwatch.py","test.py","_"],on_change)
	except KeyboardInterrupt:
		pass
	#create file a
	#initialize an inotify instance
	#change file a - does inotify react?
	#create file b - does inotify react?
	#change file b - does inotify react?
	#remove files a and b - does inotify react?
	#close inotify

run()
