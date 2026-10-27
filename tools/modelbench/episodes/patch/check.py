"""Deterministic checker for the patch review. Exit 0 = the review found every planted
defect and raised no false positives.

The scoring is structural, never a judge. `REVIEW.md` carries one
`FINDING: <path>:<line> — <text>` per finding; each defect is anchored by a literal line
in the changed file, and a finding counts when its path matches and its line is within
two of the anchor. The anchors are validated against the file on every run: a checker that
cannot find its own defect reports a fault rather than a model that missed it.

A defect anchor missing is a fault only while the code is untouched. If the reviewer
edited the implementation, the hash case says so and a missing anchor is that edit's
consequence, not the episode's own defect.

Usage:
	python3 check.py          human-readable, exit 0/1
	python3 check.py --json   per-case results, for collateral-damage detection
"""

import hashlib,json,os,re,subprocess,sys

ROOT = os.path.dirname(os.path.abspath(__file__))
IMPLEMENTATION = ["patchlib/tokenizer.py","patchlib/slugs.py","patchlib/truncate.py",
	"patchlib/stats.py"]
TOLERANCE = 2
MIN_FINDINGS = 1

# The implementation is correct in the pre-change state; these are the post-change files.
# A change to the episode must be made here with it.
EXPECTED = {
	"patchlib/tokenizer.py":"7a8f47ea8390d1c42a8b7c16342088ce07cba4fcd01df2d06a18419fe0cda362",
	"patchlib/slugs.py":"ad78762b7d91a2e320d039f74dff9686b461a20d1fb410eb4aab18bb75d898b5",
	"patchlib/truncate.py":"124b2a12ace14a79d0502be16e60ea811f4157e2034a64ffb95d41048b8e2e4a",
	"patchlib/stats.py":"b03adb355a05188719f73a516ffe800412a39039ca9e007e2556726570dfbbcc",
}

# (id, path, the line the defect lives on, what the change got wrong). Each needle must
# appear exactly once in its file in the untouched tree, or the checker says it cannot
# find its own ground truth.
DEFECTS = [
	("word-rule","patchlib/tokenizer.py",'re.compile(r"\\w+")',
		"digits and underscores are counted as words"),
	("slug-strip","patchlib/slugs.py",'return text.lower().replace(" ", "-")',
		"leading and trailing whitespace becomes a hyphen"),
	("truncate-boundary","patchlib/truncate.py","if len(text) >= limit:",
		"a string of exactly the limit is truncated"),
	("average-empty","patchlib/stats.py","return sum(len(word) for word in words) / len(words)",
		"empty text raises instead of returning 0.0"),
	("longest-order","patchlib/stats.py",'return max(words) if words else ""',
		"the lexicographically largest word is returned, not the longest"),
]

def _digest(path):
	with open(path,"rb") as f:
		return hashlib.sha256(f.read()).hexdigest()

def _changed():
	return [path for path in IMPLEMENTATION
		if _digest(os.path.join(ROOT,path)) != EXPECTED[path]]

def _anchor(path,needle):
	"""The line number a defect lives on, or None when the needle is gone."""
	with open(os.path.join(ROOT,path)) as f:
		for number,line in enumerate(f,1):
			if needle in line:
				return number
	return None

def _findings():
	"""The structured findings in REVIEW.md.

	Only `FINDING: path:line — text` is read. The brief asks for that form because a free
	prose report cannot be scored without a judge, and the episode exists to avoid one.
	"""
	path = os.path.join(ROOT,"REVIEW.md")
	if not os.path.exists(path):
		return []
	out = []
	for line in open(path).read().splitlines():
		m = re.match(r"^\s*FINDING\s*:\s*(\S+?)\s*:\s*(\d+)\s*[—–-]\s*(.+?)\s*$",line)
		if not m:
			continue
		out.append({"path":os.path.normpath(m.group(1)),"line":int(m.group(2)),
			"text":m.group(3)})
	return out

def _matches(finding,path,line):
	if line is None:
		return False
	if finding["path"] != path and not finding["path"].endswith("/" + path):
		return False
	return abs(finding["line"] - line) <= TOLERANCE

def _anchored():
	return [(defect_id,path,_anchor(path,needle)) for defect_id,path,needle,_ in DEFECTS]

def cases():
	findings = _findings()
	changed = _changed()
	anchored = _anchored()
	out = []
	def unchanged():
		return not changed,("changed: " + ", ".join(changed)) if changed \
			else "the review did not edit the code"
	out.append({"account":"implementation-unchanged","guard":True,
		"witnesses":"the review is a review, not a repair","run":unchanged})
	def review_present():
		return len(findings) >= MIN_FINDINGS,f"{len(findings)} structured finding(s) in REVIEW.md"
	out.append({"account":"review-present","guard":False,
		"witnesses":"REVIEW.md carries the structured findings the brief asks for",
		"run":review_present})
	missing = [(defect_id,path,needle) for defect_id,path,needle,_ in DEFECTS
		if _anchor(path,needle) is None]
	def anchors_ok():
		if not missing:
			return True,"every defect anchor is present"
		detail = "; ".join(f"{path}: {needle!r}" for _,path,needle in missing)
		if changed:
			return False,detail + " (the code was edited)"
		return False,detail
	out.append({"account":"checker-anchors","guard":True,"fault":bool(missing and not changed),
		"witnesses":"the checker can find its own ground truth in the tree","run":anchors_ok})
	for (defect_id,path,_,witness),(_,_,line) in zip(DEFECTS,anchored):
		def found(path=path,line=line):
			if line is None:
				return False,f"the anchor is gone from {path}"
			hits = [f for f in findings if _matches(f,path,line)]
			return bool(hits),f"{len(hits)} finding(s) within {TOLERANCE} lines of {path}:{line}"
		out.append({"account":f"defect-{defect_id}","guard":False,
			"witnesses":witness,"run":found})
	def all_found():
		missed = [defect_id for defect_id,path,line in anchored
			if not any(_matches(f,path,line) for f in findings)]
		return not missed,("missed: " + ", ".join(missed)) if missed else "every defect was reported"
	out.append({"account":"all-defects-found","guard":False,
		"witnesses":"every planted defect appears in the review","run":all_found})
	def no_false():
		unknown = [f for f in findings
			if not any(_matches(f,path,line) for _,path,line in anchored)]
		return not unknown,("unmatched findings: " +
			"; ".join(f'{f["path"]}:{f["line"]}' for f in unknown)) if unknown \
			else "every finding matches a defect"
	out.append({"account":"no-false-positives","guard":True,
		"witnesses":"the review did not invent defects","run":no_false})
	def tests_pass():
		proc = subprocess.run([sys.executable,"-m","unittest","discover","-s","tests","-t","."],
			cwd=ROOT,capture_output=True,text=True,timeout=120)
		return proc.returncode == 0,(proc.stdout + proc.stderr).strip()[-300:] \
			if proc.returncode else "the author's tests pass"
	out.append({"account":"tests-pass","guard":True,
		"witnesses":"the change set did not break the suite","run":tests_pass})
	return out

def main():
	results = []
	for case in cases():
		try:
			passed,detail = case["run"]()
		except Exception as e:
			passed,detail = False,f"{type(e).__name__}: {e}"
		entry = {"account":case["account"],"passed":bool(passed),"guard":case["guard"],
			"fault":case.get("fault",False),"witnesses":case["witnesses"],"detail":detail}
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
