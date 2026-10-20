"""The ledger can find a run's retained state.

The corpus's standing rule is that a record which stored its turns **and** its final
on-disk state can be re-graded offline, so that a change to a gate does not cost a
re-measurement. `ledger.py --check` does that by looking the state up on disk.

**The lookup used to be by the record's model id, and that is the wrong key.** The wave
runner names its state directory after the *registry key* while the trace file records the
*provider id*, and those are different strings. Measured on the 2026-10-20 wave: **22 of
42 measured records found their state and 20 did not** — and all 20 store their raw turns,
so they look re-gradeable in the ledger's own summary and are not.

These tests cover both naming conventions, because the corpus holds both: the
2026-09-27 wave named its traces after the model, and the 2026-10-20 waves name them
after the registry key.
"""
import json,os,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import ledger

def _tree(names):
	"""A temporary tree with a `state/` directory holding the given names."""
	root = tempfile.mkdtemp()
	os.makedirs(os.path.join(root,"wave-free","state"))
	for name in names:
		os.makedirs(os.path.join(root,"wave-free","state",name))
	return root

def _row(**kw):
	base = {"model":"or-minimax.m3.1-flash","model_id":"minimax/minimax-m3.1-flash:free",
		"episode":"invoicer","repeat":2}
	base.update(kw)
	return base

def test_the_state_is_found_when_the_trace_is_named_after_the_registry_key():
	root = _tree(["console-beam-free--billing--2"])
	got = ledger._state_dir(root,"wave-free/console-beam-free--billing.jsonl",
		_row(model="beam-free",model_id="beam-free",episode="billing",repeat=2))
	xtest.equal(got,os.path.join(root,"wave-free","state","console-beam-free--billing--2"),
		"the trace file's own name is the key, and it cannot drift from the directory")

def test_the_state_is_found_when_the_trace_is_named_after_the_model():
	root = _tree(["space-bunny--invoicer--1"])
	got = ledger._state_dir(root,"wave-free/space-bunny.jsonl",
		_row(model="space-bunny",model_id="space-bunny-free",episode="invoicer",repeat=1))
	xtest.equal(got,os.path.join(root,"wave-free","state","space-bunny--invoicer--1"),
		"the 2026-09-27 wave's state must stay findable")

def test_a_record_whose_state_is_gone_says_so():
	root = _tree([])
	got = ledger._state_dir(root,"wave-free/console-beam-free--billing.jsonl",
		_row(model="beam-free",model_id="beam-free",episode="billing",repeat=2))
	xtest.equal(got,None,"no state is None, not a guess")

def test_the_repeat_is_part_of_the_name():
	root = _tree(["console-beam-free--billing--2"])
	got = ledger._state_dir(root,"wave-free/console-beam-free--billing.jsonl",
		_row(model="beam-free",model_id="beam-free",episode="billing",repeat=1))
	xtest.equal(got,None,"repeat 1 is not repeat 2")

def test_a_model_id_that_is_not_the_key_does_not_stop_the_lookup():
	"""The exact case that cost 20 records: the trace says one thing and the row another."""
	root = _tree(["or-minimax.m3.1-flash--invoicer--1"])
	got = ledger._state_dir(root,"wave-free/or-minimax.m3.1-flash--invoicer.jsonl",
		_row(model="minimax.m3.1-flash",model_id="minimax/minimax-m3.1-flash:free",
			episode="invoicer",repeat=1))
	xtest.equal(got,os.path.join(root,"wave-free","state","or-minimax.m3.1-flash--invoicer--1"),
		"the provider id in the row does not have to match the key in the filename")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
