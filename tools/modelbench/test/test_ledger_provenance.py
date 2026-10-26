"""The ledger refuses a run whose session opened outside the episode sandbox.

**H01QJF2, observed 2026-10-20.** opencode 2 took the session directory from `$PWD`, so a
harness run could succeed in the launch directory while the checker ran on an untouched
sandbox. The run produced turns and a full case set, a grade was written, and the ledger's
standing audit admitted it as a result — the model's own words said *"The listed files
weren't at that path."*

The transport fix sets both `cwd` and `$PWD` (E21), but a record still has to be able to
say where the session actually was. The run now carries the sandbox it meant to use and
the directory opencode recorded for the session; the ledger refuses a contradiction. **An
absent value is `unverified` and stays admissible** — only a contradiction is evidence, and
a harness failure is a hole in the run, never a finding about a model.
"""
import json,os,shutil,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import episodes_run
import ledger

def _db_with(rows):
	"""A throwaway opencode-shaped database with a `session_v2` table."""
	path = tempfile.mktemp(suffix=".db")
	import sqlite3
	with sqlite3.connect(path) as db:
		db.execute("create table session_v2 (id text primary key, directory text)")
		db.executemany("insert into session_v2 (id,directory) values (?,?)",rows)
	return path

def test_a_session_that_opened_in_the_sandbox_is_a_match():
	xtest.equal(ledger._provenance({"root":"/tmp/opencode/ep-invoicer-a",
		"session_directory":"/tmp/opencode/ep-invoicer-a"}),"matches")

def test_a_session_that_opened_elsewhere_is_a_contradiction():
	xtest.equal(ledger._provenance({"root":"/tmp/opencode/ep-invoicer-a",
		"session_directory":"/storage/modelbench-runs/2026-10-20"}),"wrong directory",
		"the exact E21 shape: the run succeeded in the launch directory")

def test_an_absent_directory_is_unverified_not_wrong():
	xtest.equal(ledger._provenance({"root":"/tmp/opencode/ep-invoicer-a"}),"unverified")
	xtest.equal(ledger._provenance({"session_directory":"/tmp/opencode/ep-invoicer-a"}),
		"unverified","old records carry neither field, and are not retroactively refused")
	xtest.equal(ledger._provenance(None),"unverified")

def test_the_audit_refuses_a_contradiction_and_admits_an_unverified_row():
	base = {"grade":"self-corrected","cases":3,"n_turns":7}
	xtest.true(ledger._admitted(dict(base,session_in_sandbox="matches")))
	xtest.true(ledger._admitted(dict(base,session_in_sandbox="unverified")),
		"an unverified row stays a result; only a contradiction is evidence")
	xtest.true(not ledger._admitted(dict(base,session_in_sandbox="wrong directory")),
		"a run whose session was elsewhere is a hole")

def test_the_audit_still_refuses_a_dead_checker_or_an_empty_run():
	xtest.true(not ledger._admitted({"grade":"autonomy","cases":0,"n_turns":4,
		"session_in_sandbox":"matches"}),"a dead checker is not a result")
	xtest.true(not ledger._admitted({"grade":"autonomy","cases":3,"n_turns":0,
		"session_in_sandbox":"matches"}),"a run that produced nothing is not a result")
	xtest.true(not ledger._admitted({"grade":None,"cases":3,"n_turns":4,
		"session_in_sandbox":"matches"}),"a missing grade is a hole")

def test_the_run_records_the_directory_open_code_said_it_used():
	path = _db_with([("ses_x","/tmp/opencode/ep-billing-x")])
	saved_db = episodes_run.OPENCODE_DB
	episodes_run.OPENCODE_DB = path
	try:
		xtest.equal(episodes_run.session_directory("ses_x"),"/tmp/opencode/ep-billing-x")
		xtest.equal(episodes_run.session_directory("ses_missing"),"",
			"a missing session is unverified, not a wrong directory")
	finally:
		episodes_run.OPENCODE_DB = saved_db
		os.unlink(path)

def test_a_missing_database_is_unverified_rather_than_an_error():
	saved = episodes_run.OPENCODE_DB
	episodes_run.OPENCODE_DB = "/nonexistent/opencode.db"
	try:
		xtest.equal(episodes_run.session_directory("ses_x"),"")
	finally:
		episodes_run.OPENCODE_DB = saved

def test_run_once_carries_both_directories_into_the_record():
	episode = episodes_run.load_episode("billing")
	saved = (episodes_run.agent.run_episode_harness,episodes_run.trace.analyse,
		episodes_run.trace.grade,episodes_run.session_directory)
	def fake_run(*args,**kwargs):
		return {"root":"/tmp/opencode/ep-billing-x","session":"ses_x","turns":[],
			"finished":True,"claim":"","status":"","protocol":"asked","n_turns":0,
			"usage":0,"raw":"","provider_error":"","stderr":"","timed_out":False,
			"returncode":0,"turn_budget":40,"over_budget":False}
	episodes_run.agent.run_episode_harness = fake_run
	episodes_run.trace.analyse = lambda raw,baseline=None: {
		"detail":{"n_turns":0,"checker":{"cases":[]}},"gates":{}}
	episodes_run.trace.grade = lambda result: ("not-measurable",[])
	episodes_run.session_directory = lambda session: "/tmp/opencode/ep-billing-x"
	try:
		rec = episodes_run.run_once(
			{"id":"m","provider":"zen","transport":"harness"},episode,"/tmp/opencode")
	finally:
		(episodes_run.agent.run_episode_harness,episodes_run.trace.analyse,
			episodes_run.trace.grade,episodes_run.session_directory) = saved
	xtest.equal(rec["trace"]["root"],"/tmp/opencode/ep-billing-x",
		"the sandbox the run meant to use")
	xtest.equal(rec["trace"]["session_directory"],"/tmp/opencode/ep-billing-x",
		"and the directory opencode recorded for the session")
	shutil.rmtree(rec["sandbox"],ignore_errors=True)

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
