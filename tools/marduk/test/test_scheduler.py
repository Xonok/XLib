"""The scheduler: intervals, forced runs, failures and the saved result."""
import os,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk._ import event,scheduler,store

class Source:
	def __init__(self, id="fake", results=None, error=None, interval=60.0):
		self.id = id
		self.results = results or []
		self.error = error
		self._interval = interval
		self.calls = 0
		self.seen = []

	def interval(self):
		return self._interval

	def stale_after(self):
		return 180.0

	def keys(self):
		return []

	def check(self, now, memory=None):
		self.calls += 1
		self.seen.append(dict(memory or {}))
		if memory is not None:
			memory["runs"] = memory.get("runs", 0) + 1
		if self.error:
			raise self.error
		return self.results

def _condition(state, checked):
	return event.Condition("fake", "fake:a", "health", "a", state, "a is " + state, checked=checked)

def _scheduler(folder, source):
	state = store.Store(os.path.join(folder, "state.json"))
	state.load()
	return scheduler.Scheduler(state, [source])

def test_the_first_run_is_due():
	with tempfile.TemporaryDirectory() as folder:
		source = Source(results=[_condition(event.STATE_OK, 1000.0)])
		run = _scheduler(folder, source)
		run.run_due(1000.0)
		xtest.equal(source.calls, 1, "the first run happens at once")

def test_a_second_run_waits_for_the_interval():
	with tempfile.TemporaryDirectory() as folder:
		source = Source(results=[_condition(event.STATE_OK, 1000.0)])
		run = _scheduler(folder, source)
		run.run_due(1000.0)
		run.run_due(1030.0)
		xtest.equal(source.calls, 1, "half an interval is not due")
		run.run_due(1060.0)
		xtest.equal(source.calls, 2, "a full interval is due")

def test_force_runs_every_source():
	with tempfile.TemporaryDirectory() as folder:
		source = Source(results=[_condition(event.STATE_OK, 1000.0)])
		run = _scheduler(folder, source)
		run.run_due(1000.0, force=True)
		run.run_due(1000.0, force=True)
		xtest.equal(source.calls, 2, "a forced run ignores the interval")

def test_a_failed_run_records_the_error():
	with tempfile.TemporaryDirectory() as folder:
		source = Source(error=RuntimeError("boom"))
		run = _scheduler(folder, source)
		run.run_due(1000.0)
		xtest.contains("boom", run.store.sources["fake"]["last_error"], "the error is recorded")
		xtest.equal(len(run.store.conditions), 0, "a failed run adds no conditions")

def test_a_successful_run_clears_the_previous_error():
	with tempfile.TemporaryDirectory() as folder:
		source = Source(error=RuntimeError("boom"))
		run = _scheduler(folder, source)
		run.run_due(1000.0)
		source.error = None
		source.results = [_condition(event.STATE_OK, 1060.0)]
		run.run_due(1060.0)
		xtest.equal(run.store.sources["fake"]["last_error"], "", "a good run clears the error")
		xtest.equal(len(run.store.conditions), 1, "the condition is stored")

def test_the_store_is_saved_after_a_run():
	with tempfile.TemporaryDirectory() as folder:
		source = Source(results=[_condition(event.STATE_ALERT, 1000.0)])
		run = _scheduler(folder, source)
		run.run_due(1000.0)
		again = store.Store(os.path.join(folder, "state.json"))
		again.load()
		xtest.equal(len(again.conditions), 1, "the result reached the file")
		xtest.equal(len(again.news), 1, "the transition reached the file")

def test_the_source_memory_is_passed_back_and_persisted():
	with tempfile.TemporaryDirectory() as folder:
		source = Source(results=[_condition(event.STATE_OK, 1000.0)])
		run = _scheduler(folder, source)
		run.run_due(1000.0)
		xtest.equal(source.seen[0], {}, "the first run gets empty memory")
		xtest.equal(run.store.sources["fake"]["memory"], {"runs": 1}, "the change is stored")
		run.run_due(1060.0)
		xtest.equal(source.seen[1], {"runs": 1}, "the second run gets the last memory")
		again = store.Store(os.path.join(folder, "state.json"))
		again.load()
		xtest.equal(again.memory("fake"), {"runs": 2}, "the memory survives the file")

def test_a_failed_run_does_not_persist_the_memory():
	with tempfile.TemporaryDirectory() as folder:
		source = Source(error=RuntimeError("boom"))
		run = _scheduler(folder, source)
		run.run_due(1000.0)
		xtest.equal(run.store.sources["fake"].get("memory"), None,
			"a run that raised leaves no memory behind")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
