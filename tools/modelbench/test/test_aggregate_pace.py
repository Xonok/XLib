"""The aggregate gate: one shared minute window across processes, reserved before the call.

NIM's limit is per model **and** watched in aggregate. A per-model pacer in process memory
passes every check while two waves together exceed the account, and the consequence is not
a 429 but a 24-hour block. So the reservation is cross-process (`flock` on a state file)
and it happens before the request is sent: retrying after a refusal is the burst pattern
the block exists to punish.

The clock is mocked, so the suite spends no real minutes.
"""
import json,os,shutil,sys,tempfile,time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest,transport

class FakeTime:
	def __init__(self,now=1000.0):
		self.now = now
		self.sleeps = []
	def time(self):
		return self.now
	def sleep(self,seconds):
		self.sleeps.append(seconds)
		self.now += seconds

def _pace_dir():
	path = tempfile.mkdtemp(prefix="modelbench-pace-")
	saved = os.environ.get("MODELBENCH_PACE_DIR")
	os.environ["MODELBENCH_PACE_DIR"] = path
	return path,saved

def _clean(path,saved):
	if saved is None:
		os.environ.pop("MODELBENCH_PACE_DIR",None)
	else:
		os.environ["MODELBENCH_PACE_DIR"] = saved
	shutil.rmtree(path,ignore_errors=True)

def test_the_window_reserves_until_the_limit_and_then_names_a_wait():
	path,saved = _pace_dir()
	try:
		xtest.equal(transport._aggregate_reserve("nim",2,10,now=100.0),0.0,
			"the first slot fits")
		xtest.equal(transport._aggregate_reserve("nim",2,10,now=101.0),0.0,
			"the second slot fits")
		wait = transport._aggregate_reserve("nim",2,10,now=102.0)
		xtest.true(wait > 0,"the third slot must not fit inside one minute")
		xtest.true(wait <= transport.PACE_WINDOW,"the wait is inside the window")
	finally:
		_clean(path,saved)

def test_the_window_slides_and_frees_the_oldest_slot():
	path,saved = _pace_dir()
	try:
		transport._aggregate_reserve("nim",1,10,now=100.0)
		wait = transport._aggregate_reserve("nim",1,10,now=105.0)
		xtest.true(wait > 0,"the only slot is still inside the window")
		xtest.equal(transport._aggregate_reserve("nim",1,10,now=161.0),0.0,
			"once the oldest reservation is a minute old the slot is free")
	finally:
		_clean(path,saved)

def test_the_state_is_shared_between_callers_and_not_process_memory():
	"""Two calls are two reservations: the function reads the file every time, which is
	what lets a second wave process see the first one's slots."""
	path,saved = _pace_dir()
	try:
		transport._aggregate_reserve("nim",2,10,now=100.0)
		transport._aggregate_reserve("nim",2,10,now=100.0)
		state = os.path.join(path,"nim.json")
		with open(state) as f:
			entries = json.load(f)
		xtest.equal(len(entries),2,"both reservations are on disk")
	finally:
		_clean(path,saved)

def test_pace_sleeps_for_the_group_before_it_calls():
	path,saved = _pace_dir()
	fake = FakeTime()
	saved_time = transport.time
	transport.time = fake
	try:
		model = {"id":"nvidia/test","provider":"nim","transport":"http",
			"aggregate":"nim","aggregate_rpm":1}
		transport._pace(model,10)
		xtest.equal(fake.sleeps,[],"the first request fits")
		transport._pace(model,10)
		xtest.true(fake.sleeps and fake.sleeps[0] > 0,
			"the second request waits for the shared window, not its own model's")
	finally:
		transport.time = saved_time
		_clean(path,saved)

def test_a_model_outside_a_group_is_not_aggregated():
	path,saved = _pace_dir()
	try:
		model = {"id":"x","provider":"openrouter","transport":"http","rpm":100}
		transport._pace(model,10)
		xtest.equal(os.listdir(path),[],"no group means no aggregate state")
	finally:
		_clean(path,saved)

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
