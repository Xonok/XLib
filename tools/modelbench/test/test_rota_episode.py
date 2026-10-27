"""The rota episode: write tests that discriminate, checked before any model sees it.

The episode answers a question the other three cannot: *can this model write tests with
teeth?* The implementation is correct by construction, and the grade is whether the model's
own suite passes on it **and fails on a mutant** — discrimination, not coverage.

The checker's own validation follows the README's rule, executable here: the untouched tree
has no suite and fails every witness; a real suite passes every case; six `assert True`
methods pass on the correct code and catch nothing; a suite with one wrong assertion fails
on the correct code; and editing the implementation breaks the stated fact's guard.

The suite used as the "real suite" fixture is written here, from SPEC.md, and is a second
expression of the spec on purpose: a solution derived from the checker's mutants would be a
test of the mutants, not of the behaviour.
"""
import json,os,shutil,subprocess,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import episodes_run

EPISODE = os.path.join(REPO,"tools","modelbench","episodes","rota")

GOOD_SUITE = '''import unittest
from rota.rules import pay_cents,payable_minutes
from rota.shifts import Shift
from rota.schedule import Schedule

class ShiftTest(unittest.TestCase):
	def test_minutes(self):
		self.assertEqual(Shift("ana",9 * 60,17 * 60).minutes(),480)

	def test_hours_text(self):
		self.assertEqual(Shift("ana",9 * 60,16 * 60 + 30).hours_text(),"7h30")

	def test_end_before_start_is_refused(self):
		with self.assertRaises(ValueError):
			Shift("ana",10 * 60,9 * 60)

class PayTest(unittest.TestCase):
	def test_exactly_six_hours_is_paid_in_full(self):
		self.assertEqual(payable_minutes(360),360)

	def test_above_six_hours_loses_the_break(self):
		self.assertEqual(payable_minutes(420),390)

	def test_four_hours(self):
		self.assertEqual(pay_cents(240,1000),4000)

	def test_overtime_after_forty_paid_hours(self):
		self.assertEqual(pay_cents(2700,1000),46750)

class ScheduleTest(unittest.TestCase):
	def test_touching_shifts_are_fine(self):
		schedule = Schedule()
		schedule.add(Shift("ana",9 * 60,12 * 60))
		schedule.add(Shift("ana",12 * 60,14 * 60))
		self.assertEqual(schedule.total_minutes(),300)

	def test_overlap_is_refused(self):
		schedule = Schedule()
		schedule.add(Shift("ana",9 * 60,12 * 60))
		with self.assertRaises(ValueError):
			schedule.add(Shift("ana",11 * 60,13 * 60))
'''

TRIVIAL_SUITE = "import unittest\n\nclass NothingTest(unittest.TestCase):\n" + "".join(
	f"\tdef test_nothing_{i}(self):\n\t\tself.assertTrue(True)\n\n" for i in range(6))

WRONG_SUITE = '''import unittest
from rota.rules import pay_cents

class WrongTest(unittest.TestCase):
	def test_zero(self):
		self.assertEqual(pay_cents(0,1000),0)

	def test_four_hours_is_off_by_one(self):
		self.assertEqual(pay_cents(240,1000),4001)

	def test_six_hours(self):
		self.assertEqual(pay_cents(360,1000),6000)
'''

def _copy():
	root = tempfile.mkdtemp(prefix="rota-test-")
	shutil.copytree(EPISODE,root,dirs_exist_ok=True)
	return root

def _install(root,body,name="test_rota.py"):
	path = os.path.join(root,"tests",name)
	with open(path,"w") as f:
		f.write(body)

def _check(root):
	proc = subprocess.run([sys.executable,"check.py","--json"],cwd=root,
		capture_output=True,text=True)
	return proc.returncode,json.loads(proc.stdout)

def _cases(root):
	return {case["account"]:case for case in _check(root)[1]["cases"]}

def test_the_untouched_tree_has_no_suite_and_every_guard_passes():
	root = _copy()
	code,data = _check(root)
	xtest.not_equal(code,0,"there is no suite, so the episode cannot pass")
	broken = [case["account"] for case in data["cases"]
		if case["guard"] and not case["passed"]]
	xtest.equal(broken,[],"every case that passed before the work still passes")
	xtest.true(not _cases(root)["tests-present"]["passed"],"and there are no test methods")

def test_a_real_suite_passes_every_case():
	root = _copy()
	_install(root,GOOD_SUITE)
	code,data = _check(root)
	failed = [case["account"] for case in data["cases"] if not case["passed"]]
	xtest.equal(failed,[],"a suite that pins the rules passes every case")
	xtest.equal(code,0,"and the checker exits 0")

def test_one_giant_test_is_not_a_suite():
	root = _copy()
	# One method with every assertion in it: correct, and not a suite.
	_install(root,'''import unittest
from rota.rules import pay_cents,payable_minutes
from rota.shifts import Shift

class GiantTest(unittest.TestCase):
	def test_everything(self):
		self.assertEqual(Shift("ana",9 * 60,17 * 60).minutes(),480)
		self.assertEqual(payable_minutes(360),360)
		self.assertEqual(payable_minutes(420),390)
		self.assertEqual(pay_cents(240,1000),4000)
		self.assertEqual(pay_cents(2700,1000),46750)
		self.assertEqual(Shift("ana",9 * 60,16 * 60 + 30).hours_text(),"7h30")
''')
	cases = _cases(root)
	xtest.true(not cases["tests-present"]["passed"],
		"the brief asks for one test per behaviour, and one method is not a suite")

def test_a_suite_of_assert_true_catches_nothing():
	root = _copy()
	_install(root,TRIVIAL_SUITE)
	cases = _cases(root)
	xtest.true(cases["tests-pass-on-the-correct-code"]["passed"],
		"trivial tests do pass on the correct code, which is why passing is not enough")
	for name in ("break-threshold","overtime-rate","minutes-off-by-one","touching-shifts"):
		xtest.true(not cases[f"catches-{name}"]["passed"],
			f"a suite of assert True cannot catch {name}")

def test_a_suite_that_fails_on_the_correct_code_is_not_a_suite():
	root = _copy()
	_install(root,WRONG_SUITE)
	cases = _cases(root)
	xtest.true(not cases["tests-pass-on-the-correct-code"]["passed"],
		"a wrong assertion is a wrong test, not a finding about the code")

def test_editing_the_implementation_fails_the_guard():
	root = _copy()
	_install(root,GOOD_SUITE)
	path = os.path.join(root,"rota","rules.py")
	with open(path) as f:
		body = f.read()
	with open(path,"w") as f:
		f.write(body.replace("if minutes > BREAK_AFTER_MINUTES:",
			"if minutes >= BREAK_AFTER_MINUTES:"))
	cases = _cases(root)
	xtest.true(not cases["implementation-unchanged"]["passed"],
		"the implementation is the ground truth and the stated fact says not to edit it")

def test_the_expected_hashes_match_the_episode():
	import importlib.util
	spec = importlib.util.spec_from_file_location("rota_check",
		os.path.join(EPISODE,"check.py"))
	check = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(check)
	for path,digest in check.EXPECTED.items():
		actual = check._digest(os.path.join(EPISODE,path))
		xtest.equal(actual,digest,
			f"{path} changed without the checker's hash being updated with it")

def test_the_runner_loads_the_episode():
	episode = episodes_run.load_episode("rota")
	xtest.true(not episode["baseline_pass"],"there is no suite yet")
	xtest.true(len(episode["baseline"]["cases"]) >= 6,
		"the checker produced its whole case set on the untouched tree")
	xtest.true(not episode["baseline"].get("checker_dead"),"and it is not a dead checker")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
