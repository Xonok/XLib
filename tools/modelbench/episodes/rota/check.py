"""Deterministic checker for the rota tests. Exit 0 = the suite is a suite: it passes on
the implementation as written, it has at least six test methods, and it catches every
planted regression.

The mutants are applied to a copy of the tree, never to the sandbox: the implementation is
the ground truth, and a checker that edited it would change what it is measuring.

Usage:
	python3 check.py          human-readable, exit 0/1
	python3 check.py --json   per-case results, for collateral-damage detection
"""

import ast,hashlib,json,os,re,shutil,subprocess,sys,tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
IMPLEMENTATION = ["rota/shifts.py","rota/rules.py","rota/schedule.py"]
MIN_TESTS = 6

# The implementation is correct as written. These hashes are the fact that nobody changed
# it; a change to the episode's code must be made here with it, or every run reports the
# model for the operator's edit.
EXPECTED = {
	"rota/shifts.py":"5c30d14d7d4c8f8e244dd00d8ad1910a6f12376a6c97187db6528c12a7a640e7",
	"rota/rules.py":"15550cacbaad02321d389a35570a069e43fb1586f374eda0b7f1ca643c09bc16",
	"rota/schedule.py":"d058300bd4665705fc350d09ce785129c77584333e224cedc1a5f2a96bedd420",
}

# One regression per rule that a suite is expected to pin. Each entry is applied to a
# copy of the tree and the model's tests are run against it: a suite with teeth fails.
MUTANTS = [
	("break-threshold","rota/rules.py",
		"if minutes > BREAK_AFTER_MINUTES:",
		"if minutes >= BREAK_AFTER_MINUTES:",
		"a six-hour shift starts losing a break"),
	("overtime-rate","rota/rules.py",
		"OVERTIME_DENOMINATOR = 2",
		"OVERTIME_DENOMINATOR = 3",
		"overtime pays 4/3 instead of 3/2"),
	("minutes-off-by-one","rota/shifts.py",
		"return self.end - self.start",
		"return self.end - self.start + 1",
		"a shift is one minute longer than it is"),
	("touching-shifts","rota/schedule.py",
		"first.start < second.end and second.start < first.end",
		"first.start <= second.end and second.start <= first.end",
		"shifts that merely touch are now a conflict"),
]

def _digest(path):
	with open(path,"rb") as f:
		return hashlib.sha256(f.read()).hexdigest()

def _test_methods():
	count = 0
	base = os.path.join(ROOT,"tests")
	for dirpath,dirnames,filenames in os.walk(base):
		dirnames[:] = [d for d in dirnames if d != "__pycache__"]
		for name in sorted(filenames):
			if not name.endswith(".py"):
				continue
			try:
				tree = ast.parse(open(os.path.join(dirpath,name)).read())
			except SyntaxError:
				continue
			for node in ast.walk(tree):
				if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) \
						and node.name.startswith("test_"):
					count += 1
	return count

def _run(root):
	"""Run the model's suite. Returns (exit code, how many tests ran, output).

	The count matters: Python 3.14's unittest exits 5 when no test ran, so an empty suite
	must not read as "the tests failed" — that would let a model with no tests at all pass
	every mutant case for the wrong reason."""
	proc = subprocess.run([sys.executable,"-m","unittest","discover","-s","tests","-t","."],
		cwd=root,capture_output=True,text=True,timeout=120)
	output = (proc.stdout + proc.stderr).strip()
	match = re.search(r"Ran (\d+) tests?",output)
	ran = int(match.group(1)) if match else 0
	return proc.returncode,ran,output

def _mutant_copy(root,name,path,old,new):
	"""A copy of the tree with one regression planted. Returns (copy, planted)."""
	target = os.path.join(root,path)
	try:
		body = open(target).read()
	except OSError:
		return None,False
	if old not in body:
		return None,False
	copy = tempfile.mkdtemp(prefix=f"rota-{name}-")
	for dirpath,dirnames,filenames in os.walk(root):
		dirnames[:] = [d for d in dirnames if d != "__pycache__"]
		for filename in filenames:
			src = os.path.join(dirpath,filename)
			dst = os.path.join(copy,os.path.relpath(src,root))
			os.makedirs(os.path.dirname(dst),exist_ok=True)
			shutil.copyfile(src,dst)
	with open(os.path.join(copy,path),"w") as f:
		f.write(body.replace(old,new))
	return copy,True

def cases():
	out = []
	def unchanged():
		changed = [path for path in IMPLEMENTATION
			if _digest(os.path.join(ROOT,path)) != EXPECTED[path]]
		return not changed,("changed: " + ", ".join(changed)) if changed \
			else "the implementation is untouched"
	out.append({"account":"implementation-unchanged","guard":True,
		"witnesses":"the implementation is the ground truth","run":unchanged})
	def present():
		count = _test_methods()
		return count >= MIN_TESTS,f"{count} test method(s); at least {MIN_TESTS} are required"
	out.append({"account":"tests-present","guard":False,
		"witnesses":"a real suite, not one giant test","run":present})
	def correct():
		code,ran,output = _run(ROOT)
		if not ran:
			return False,"no test ran"
		return code == 0,output[-300:] if code else "the suite passes on the implementation as written"
	out.append({"account":"tests-pass-on-the-correct-code","guard":False,
		"witnesses":"no false positives against the code as written","run":correct})
	for name,path,old,new,witnesses in MUTANTS:
		def catches(path=path,old=old,new=new,name=name):
			copy,planted = _mutant_copy(ROOT,name,path,old,new)
			if not planted:
				return False,f"the mutation target is missing from {path}"
			try:
				code,ran,output = _run(copy)
			finally:
				shutil.rmtree(copy,ignore_errors=True)
			if not ran:
				return False,"no test ran, so nothing could catch the mutant"
			return code != 0,("caught by the suite" if code
				else "the suite passed on the mutant")
		out.append({"account":f"catches-{name}","guard":False,
			"witnesses":f"the suite fails when {witnesses}","run":catches})
	return out

def main():
	results = []
	for case in cases():
		try:
			passed,detail = case["run"]()
		except Exception as e:
			passed,detail = False,f"{type(e).__name__}: {e}"
		entry = {"account":case["account"],"passed":bool(passed),"guard":case["guard"],
			"witnesses":case["witnesses"],"detail":detail}
		results.append(entry)
	if "--json" in sys.argv:
		print(json.dumps({"cases":results,
			"passed":sum(r["passed"] for r in results),"n":len(results)},indent=2))
		return 0 if all(r["passed"] for r in results) else 1
	for r in results:
		if not r["passed"]:
			print("FAIL",f"{r['account']}: {r['detail']}  [{r['witnesses']}]")
	failed = [r for r in results if not r["passed"]]
	if failed:
		print(f"\n{len(failed)}/{len(results)} cases failing")
		return 1
	print(f"all {len(results)} cases pass")
	return 0

if __name__ == "__main__":
	sys.exit(main())
