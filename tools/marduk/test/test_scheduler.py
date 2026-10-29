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

	def interval(self):
		return self._interval

	def stale_after(self):
		return 180.0

	def keys(self):
		return []

	def check(self, now):
		self.calls += 1
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

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
