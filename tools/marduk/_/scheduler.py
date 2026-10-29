"""Run sources on their own intervals, off the render thread."""

import threading,time
from . import store

class Scheduler:
	"""One background loop that runs each source when its interval is due."""

	def __init__(self,store:store.Store,sources,clock=time.time):
		self.store=store
		self.sources=sources
		self.clock=clock
		self._stop=threading.Event()
		self._last_run={}
		self._running=set()

	def due(self,source,now:float)->bool:
		last=self._last_run.get(source.id)
		return last is None or now-last>=source.interval()

	def run_due(self,now:float,force:bool=False)->None:
		for source in self.sources:
			if source.id in self._running:
				continue
			if not force and not self.due(source,now):
				continue
			self._run(source,now)

	def _run(self,source,now:float)->None:
		self._running.add(source.id)
		self._last_run[source.id]=now
		try:
			conditions=source.check(now)
		except Exception as exc:
			self._running.discard(source.id)
			self.store.fail(source.id,now,f"{type(exc).__name__}: {exc}")
			self.store.save()
			return
		self._running.discard(source.id)
		self.store.apply(source.id,conditions,now)
		self.store.save()

	def run_forever(self)->None:
		while not self._stop.is_set():
			self.run_due(self.clock())
			self._stop.wait(1.0)

	def stop(self)->None:
		self._stop.set()
