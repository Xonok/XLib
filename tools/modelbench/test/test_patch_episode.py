"""The patch episode: a review graded on defects found and false positives, checked before
any model sees it.

The episode asks a question the suite cannot: *can this model review a change set* — find
the planted defects and not invent any? The scoring is structural: `REVIEW.md` carries one
`FINDING: path:line — text` per finding, each defect is anchored by a literal line, and a
finding counts when its path matches and its line is within two of the anchor.

The README's rule for a checker is that it must fail on the broken code, pass on the
correct fix, and fail on the careless one. The review's counterparts are these tests: the
untouched tree fails every witness; a perfect review passes; a partial one misses exactly
what it missed; a review that invents findings fails precision; a shotgun review finds the
defects and fails precision; and a reviewer who repairs the code instead of reporting it
fails the guard. The diff is checked as a stimulus too: each defect must appear as an
added line in `CHANGES.diff`, or the reviewer is being asked to find something the change
set does not show.
"""
import importlib.util,json,os,shutil,subprocess,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import episodes_run

EPISODE = os.path.join(REPO,"tools","modelbench","episodes","patch")

def _check_module():
	spec = importlib.util.spec_from_file_location("patch_check",
		os.path.join(EPISODE,"check.py"))
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module

def _copy():
	root = tempfile.mkdtemp(prefix="patch-test-")
	shutil.copytree(EPISODE,root,dirs_exist_ok=True)
	return root

def _review(root,text):
	with open(os.path.join(root,"REVIEW.md"),"w") as f:
		f.write(text)

def _findings(defects):
	return "".join(f"FINDING: {path}:{line} — {defect_id} is wrong\n"
		for defect_id,path,line in defects)

def _run(root):
	proc = subprocess.run([sys.executable,"check.py","--json"],cwd=root,
		capture_output=True,text=True)
	return proc.returncode,json.loads(proc.stdout)

def _cases(root):
	return {case["account"]:case for case in _run(root)[1]["cases"]}

def _anchors():
	check = _check_module()
	return check._anchored()

def test_the_untouched_tree_fails_and_every_guard_passes():
	root = _copy()
	code,data = _run(root)
	xtest.not_equal(code,0,"there is no review, so the episode cannot pass")
	broken = [case["account"] for case in data["cases"]
		if case["guard"] and not case["passed"]]
	xtest.equal(broken,[],"a guard is a case that passed before the work")
	xtest.equal(data["n"],11,"five defects, the review, the aggregate, precision and three guards")

def test_a_perfect_review_passes_every_case():
	root = _copy()
	_review(root,_findings(_anchors()))
	code,data = _run(root)
	failed = [case["account"] for case in data["cases"] if not case["passed"]]
	xtest.equal(failed,[],"a review of every defect and nothing else is the pass")
	xtest.equal(code,0,"and the checker exits 0")

def test_a_partial_review_misses_exactly_what_it_missed():
	root = _copy()
	reviewed = [entry for entry in _anchors() if entry[0] != "longest-order"]
	_review(root,_findings(reviewed))
	cases = _cases(root)
	xtest.true(not cases["defect-longest-order"]["passed"],
		"the missed defect is the one that fails")
	xtest.true(cases["defect-word-rule"]["passed"],
		"and the reported ones still count")
	xtest.true(not cases["all-defects-found"]["passed"],
		"the aggregate says the review is incomplete")

def test_a_review_that_invents_findings_fails_precision():
	root = _copy()
	_review(root,_findings(_anchors()) + "FINDING: patchlib/slugs.py:1 — looks odd\n")
	cases = _cases(root)
	xtest.true(cases["all-defects-found"]["passed"],"every planted defect was found")
	xtest.true(not cases["no-false-positives"]["passed"],
		"but the extra finding is a false positive")

def test_a_shotgun_review_finds_defects_and_fails_precision():
	root = _copy()
	lines = "".join(f"FINDING: patchlib/{name}:{number} — suspicious\n"
		for name in ("slugs.py","stats.py","tokenizer.py","truncate.py")
		for number in range(1,15))
	_review(root,lines)
	cases = _cases(root)
	xtest.true(cases["all-defects-found"]["passed"],
		"a finding on every line covers every defect")
	xtest.true(not cases["no-false-positives"]["passed"],
		"and precision is what rejects it")

def test_repairing_the_code_instead_of_reporting_it_fails_the_guard():
	root = _copy()
	_review(root,_findings(_anchors()))
	path = os.path.join(root,"patchlib","truncate.py")
	with open(path) as f:
		body = f.read()
	with open(path,"w") as f:
		f.write(body.replace("if len(text) >= limit:","if len(text) > limit:"))
	cases = _cases(root)
	xtest.true(not cases["implementation-unchanged"]["passed"],
		"the stated fact is that the change set is under review, not to be repaired")

def test_every_defect_is_visible_in_the_diff():
	"""A review can only find what the change set shows. A defect introduced by removing a
	guard is visible as the removed lines, so the test asks that the defective line is in
	the diff — as an added line, a removed one, or the context of the hunk."""
	check = _check_module()
	diff = open(os.path.join(EPISODE,"CHANGES.diff")).read()
	for defect_id,path,needle,witness in check.DEFECTS:
		xtest.contains(needle,diff,f"{defect_id} is not visible in CHANGES.diff")

def test_the_runner_loads_the_episode():
	episode = episodes_run.load_episode("patch")
	xtest.true(not episode["baseline_pass"],"there is no review yet")
	xtest.true(len(episode["baseline"]["cases"]) == 11,
		"the checker produced its whole case set on the untouched tree")
	xtest.true(not episode["baseline"].get("checker_fault"),"and it is not faulted")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
