"""The newsroom episode: find and aggregate, without judging whether a story is true.

The episode measures a different task from the code episodes: the corpus is given, and
the model writes a shortlist. These tests are the checker's own rule, executable:

  1. the untouched tree fails and every guard passes;
  2. a digest built from the seeded stories passes;
  3. splitting one event across two items fails aggregation;
  4. filling the shortlist with noise fails precision.

The solution is derived from `check.SIGNAL`, the same ground truth the checker reads, so
the test cannot drift into a second answer.
"""
import importlib.util,json,os,shutil,subprocess,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import episodes_run

EPISODE = os.path.join(REPO,"tools","modelbench","episodes","newsroom")

def _checker():
	spec = importlib.util.spec_from_file_location("newsroom_check",
		os.path.join(EPISODE,"check.py"))
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module

def _copy():
	root = tempfile.mkdtemp(prefix="newsroom-test-")
	shutil.copytree(EPISODE,root,dirs_exist_ok=True)
	return root

def _write(root,items):
	with open(os.path.join(root,"digest.json"),"w") as f:
		json.dump({"items":items},f)

def _check(root):
	proc = subprocess.run([sys.executable,"check.py","--json"],cwd=root,
		capture_output=True,text=True)
	return proc.returncode,json.loads(proc.stdout)

def _signal_items(count=6,split=None):
	checker = _checker()
	items=[]
	for name,ids in list(checker.SIGNAL.items())[:count]:
		if name == split:
			items.append({"ids":ids[:1],"title":name,"why":"why"})
			items.append({"ids":ids[1:],"title":name,"why":"why"})
			continue
		items.append({"ids":list(ids),"title":name,"why":"why"})
	return items

def test_the_untouched_tree_fails_and_every_guard_passes():
	episode = episodes_run.load_episode("newsroom")
	xtest.equal(episode["baseline_pass"],False,"the untouched tree does not solve the task")
	guards = [case for case in episode["baseline"]["cases"] if case["guard"]]
	xtest.equal([case["passed"] for case in guards],[True],
		"the corpus guard passes before any model touches the tree")

def test_a_digest_built_from_the_seeded_stories_passes():
	root = _copy()
	try:
		_write(root,_signal_items())
		code,detail = _check(root)
		xtest.equal(code,0,"the correct shortlist passes")
		xtest.equal([case["passed"] for case in detail["cases"]],
			[True]*len(detail["cases"]),"every case passes")
	finally:
		shutil.rmtree(root,ignore_errors=True)

def test_splitting_one_event_across_two_items_fails_aggregation():
	root = _copy()
	try:
		_write(root,_signal_items(split="quake"))
		code,detail = _check(root)
		cases = {case["account"]:case for case in detail["cases"]}
		xtest.equal(code,1,"a split event is not accepted")
		xtest.equal(cases["aggregated"]["passed"],False,"aggregation names the split")
	finally:
		shutil.rmtree(root,ignore_errors=True)

def test_a_noise_only_item_fails_precision():
	root = _copy()
	try:
		checker = _checker()
		noise = sorted(checker.NOISE)[0]
		items = _signal_items() + [{"ids":[noise],"title":"Football","why":"noise"}]
		_write(root,items)
		code,detail = _check(root)
		cases = {case["account"]:case for case in detail["cases"]}
		xtest.equal(code,1,"a noise-only item is not accepted")
		xtest.equal(cases["precision"]["passed"],False,"precision names the noise")
	finally:
		shutil.rmtree(root,ignore_errors=True)
