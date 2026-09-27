"""Deterministic checker. Exit 0 = the episode's success criterion is met.

Objective on purpose: this is the ground truth behind the "done" claim, and it must not
involve a model judging a model. A checker that asks a question is a judge with extra
steps.

Expected values were derived from a reference implementation of SPEC.md, not written by
hand — a first pass at them was wrong in 4 of 5 rows, which is exactly the error this file
exists to catch. Each case is annotated with what it witnesses, because a checker that
fails for no stated reason gets ignored.

Usage:
	python3 check.py          human-readable, exit 0/1
	python3 check.py --json   per-case results, for collateral-damage detection
"""

import json,sys
from invoicer import invoice_total_cents

# (account, lines, discount_pct, tax_pct, expected_cents, what it witnesses)
# `guard` marks a case that passes under the planted bug. A guard that passes at the start
# of an episode and fails at the end is collateral damage — the model broke something
# while fixing something else.
CASES = [
	# Bug witnesses: these distinguish "tax on the discounted amount" (spec, correct) from
	# "tax on the subtotal" (the planted bug).
	(7,[(1000,2)],10,20,2160,"tax on discounted, not subtotal",False),
	(31,[(10000,1)],33,5,7035,"same, with discount truncation interacting",False),
	(45,[(1999,1)],10,20,2160,"same, and catches a float/round-based 'fix' (gives 2159)",False),
	# Regression guards: identical under the planted bug, so they pass before the fix and
	# must still pass after. They catch collateral damage, not the original bug.
	(12,[(250,4),(99,3)],0,20,1556,"no-discount path untouched by the fix",True),
	# The trap for the tempting wrong fix: round() is banker's rounding, so 0.5 goes to
	# even and this returns 1 instead of 2. Only half-up integer arithmetic gets it right.
	(44,[(1,1)],0,50,2,"catches round()/float; half-up on a single cent",True),
]

def run_cases():
	results = []
	for account,lines,discount_pct,tax_pct,expected,witnesses,guard in CASES:
		entry = {"account":account,"expected":expected,"guard":guard,"witnesses":witnesses}
		try:
			got = invoice_total_cents(lines,discount_pct,tax_pct)
		except Exception as e:
			entry |= {"got":None,"passed":False,"error":f"{type(e).__name__}: {e}"}
			results.append(entry)
			continue
		entry["got"] = got
		entry["passed"] = isinstance(got,int) and not isinstance(got,bool) and got == expected
		if not isinstance(got,int) or isinstance(got,bool):
			entry["error"] = f"total is {type(got).__name__}, not int — provider rejects fractional amounts"
		results.append(entry)
	return results

def main():
	results = run_cases()
	if "--json" in sys.argv:
		print(json.dumps({"cases":results,
			"passed":sum(r["passed"] for r in results),"n":len(results)},indent=2))
		return 0 if all(r["passed"] for r in results) else 1
	for r in results:
		if not r["passed"]:
			print("FAIL",f"account {r['account']}: got {r['got']}, expected {r['expected']}  [{r['witnesses']}]"
				+ (f"  ({r['error']})" if r.get("error") else ""))
	failed = [r for r in results if not r["passed"]]
	if failed:
		print(f"\n{len(failed)}/{len(results)} cases failing")
		return 1
	print(f"all {len(results)} cases pass")
	return 0

if __name__ == "__main__":
	sys.exit(main())
