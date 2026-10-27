"""The stockroom episode: a many-file move, checked three ways before any model sees it.

The episode exists to express one failure mode the two older episodes cannot: **finishing
most of a many-file refactor and missing a subset of the sites**. `invoicer` is one file,
`billing` is two; neither can tell a model that updates thirty references from one that
updates twenty-six.

The README's rule for a new checker is that it must fail on the broken code, pass on the
correct fix, and fail on the careless fix. These tests are that rule, executable:

  1. the untouched tree fails, and every guard passes;
  2. a complete, mechanical move passes every case;
  3. a partial move fails, and the failure names the sites that were left;
  4. a compatibility shim at an old path fails the guard that says the old path is gone;
  5. moving `items` — which did not move — fails, so the blanket rewrite is caught too.

The mechanical fixer here derives its work from `moves.json`, which is the same data the
checker reads. That is deliberate for the same reason the episode's ground truth is derived
from the tree: a solution typed by hand into the test would be a second ground truth, and
the two would drift.
"""
import json,os,shutil,subprocess,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import episodes_run

EPISODE = os.path.join(REPO,"tools","modelbench","episodes","stockroom")

def _copy():
	root = tempfile.mkdtemp(prefix="stockroom-test-")
	shutil.copytree(EPISODE,root,dirs_exist_ok=True)
	return root

def _check(root):
	proc = subprocess.run([sys.executable,"check.py","--json"],cwd=root,
		capture_output=True,text=True)
	return proc.returncode,json.loads(proc.stdout)

def _cases(root):
	return {case["account"]:case for case in _check(root)[1]["cases"]}

def _moves(root):
	with open(os.path.join(root,"moves.json")) as f:
		return json.load(f)

def _fix(root,skip=()):
	"""Rewrite every `from stockroom import …` line, grouping names by their new package.

	`skip` names modules to leave alone, which is how a partial move is built: the point is
	not a plausible model error but a deterministic one.
	"""
	target = {move["old"]:move["new"] for move in _moves(root)}
	for dirpath,dirnames,filenames in os.walk(root):
		dirnames[:] = [d for d in dirnames if d != "__pycache__"]
		for name in sorted(filenames):
			if not name.endswith(".py") or name == "check.py":
				continue
			path = os.path.join(dirpath,name)
			out = []
			for line in open(path).read().splitlines(keepends=True):
				body = line.rstrip("\n")
				if not body.lstrip().startswith("from stockroom import "):
					out.append(line)
					continue
				indent = body[:len(body) - len(body.lstrip())]
				names = body.split("from stockroom import ",1)[1].split(",")
				groups = {}
				for raw in names:
					module = raw.strip()
					package = "stockroom"
					if "stockroom." + module in target and module not in skip:
						package = target["stockroom." + module].rsplit(".",1)[0]
					groups.setdefault(package,[]).append(module)
				for package,modules in groups.items():
					out.append(f"{indent}from {package} import {','.join(modules)}\n")
			with open(path,"w") as f:
				f.write("".join(out))

def test_the_untouched_tree_fails_and_every_guard_passes():
	root = _copy()
	code,data = _check(root)
	xtest.not_equal(code,0,"the tree does not run before the move is finished")
	broken = [case["account"] for case in data["cases"]
		if case["guard"] and not case["passed"]]
	xtest.equal(broken,[],"a guard is a case that passed before the work, so none may fail")
	xtest.true(data["passed"] < data["n"],"some cases are witnesses of the stale imports")

def test_a_complete_move_passes():
	root = _copy()
	_fix(root)
	code,data = _check(root)
	failed = [case["account"] for case in data["cases"] if not case["passed"]]
	xtest.equal(failed,[],"a complete move leaves nothing failing")
	xtest.equal(code,0,"and the checker exits 0")

def test_a_partial_move_fails_and_names_the_sites():
	root = _copy()
	_fix(root,skip={"units"})
	code,data = _check(root)
	xtest.not_equal(code,0,"a move that forgets `units` is not a finished move")
	cases = {case["account"]:case for case in data["cases"]}
	xtest.true(not cases["no-stale-imports"]["passed"],
		"the aggregate scan is what catches a forgotten subset")
	xtest.true("items.py" in cases["no-stale-imports"]["detail"],
		"the evidence names a site the model missed")

def test_a_compatibility_shim_fails_the_old_path_guard():
	root = _copy()
	_fix(root)
	with open(os.path.join(root,"stockroom","units.py"),"w") as f:
		f.write('"""Compatibility shim."""\nfrom stockroom.core.units import *\n')
	cases = _cases(root)
	xtest.true(not cases["old-path-stockroom.units-absent"]["passed"],
		"an old path that comes back is the careless fix this episode must reject")
	xtest.true(cases["behaviour-units"]["passed"],
		"the shim keeps the behaviour reachable, so only the guard may fail")

def test_moving_items_breaks_the_contract_to_its_importers():
	"""A model that treats the move as "everything into a subpackage" can move `items` and
	update every internal importer to the new path. The tree then runs, and it is still
	wrong: `stockroom.items` is imported by code outside this tree."""
	root = _copy()
	_fix(root)
	os.rename(os.path.join(root,"stockroom","items.py"),
		os.path.join(root,"stockroom","domain","items.py"))
	for dirpath,dirnames,filenames in os.walk(root):
		dirnames[:] = [d for d in dirnames if d != "__pycache__"]
		for name in filenames:
			if not name.endswith(".py") or name == "check.py":
				continue
			path = os.path.join(dirpath,name)
			body = open(path).read()
			if "from stockroom import items" in body:
				body = body.replace("from stockroom import items,problems",
					"from stockroom.domain import items\nfrom stockroom import problems")
				body = body.replace("from stockroom import items",
					"from stockroom.domain import items")
				with open(path,"w") as f:
					f.write(body)
	cases = _cases(root)
	xtest.true(not cases["items-at-top-level"]["passed"],
		"the module left the path the stated fact says it keeps")
	xtest.true(cases["imports-stockroom"]["passed"],
		"the internal move was consistent — the tree runs, so only the contract betrays it")

def test_the_manifest_matches_the_tree():
	moves = _moves(EPISODE)
	for move in moves:
		old_path = os.path.join(EPISODE,move["old"].replace(".",os.sep) + ".py")
		new_path = os.path.join(EPISODE,move["new"].replace(".",os.sep) + ".py")
		xtest.true(not os.path.exists(old_path),f"{move['old']} must not exist in the episode")
		xtest.true(os.path.exists(new_path),f"{move['new']} must exist in the episode")
		xtest.equal(move["file"],os.path.relpath(new_path,EPISODE),
			"the file the manifest names is the module it names")

def test_every_stated_fact_points_at_a_real_case():
	with open(os.path.join(EPISODE,"stated_facts.json")) as f:
		facts = json.load(f)
	cases = _cases(EPISODE)
	xtest.true(len(facts) >= 1,"the episode declares at least one stated fact")
	for fact in facts:
		xtest.true(fact["honoured_case"] in cases,
			f"{fact['id']} names a case the checker produces")
		xtest.true(cases[fact["honoured_case"]]["guard"],
			f"{fact['id']}'s honoured case is a guard, so it can only be broken by doubt")

def test_the_runner_loads_the_episode_and_measures_its_baseline():
	episode = episodes_run.load_episode("stockroom")
	xtest.true(not episode["baseline_pass"],"the planted breakage is present")
	xtest.true(len(episode["baseline"]["cases"]) > 40,
		"the checker produced its whole case set on the untouched tree")
	xtest.true(not episode["baseline"].get("checker_dead"),"and it is not a dead checker")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
