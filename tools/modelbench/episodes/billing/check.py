"""Deterministic checker for the `billing` episode.

Ground truth here is NOT a hand-typed table. The invoicer episode's first draft had four
of five expected values miscalculated by hand, and a checker that is itself wrong is
indistinguishable from a model that is. So every attribution case is checked three ways:

	1. against an independent reference implementation written below, using different
	   arithmetic (ordinals and a stepped month walk, explicit half-up division) so a slip
	   in the episode's own formulas cannot be mirrored by the reference;
	2. against a literal from SPEC.md's reconciliation table, which is the number finance
	   actually reconciles against;
	3. the two must agree with each other.

If the reference and the literal disagree, the case fails as CHECKER-FAULT and says so —
that is a defect in this file, not a result about the model, and the two are never allowed
to blur.
"""

import json,sys
from datetime import date,timedelta

sys.path.insert(0,".")
import billing,fiscal,money

FY_START = 4

# --- independent reference -----------------------------------------------------

def _ref_add_months(d,n):
	y,m = d.year,d.month
	for _ in range(n):
		m += 1
		if m == 13:
			y,m = y + 1,1
	return date(y,m,1)

def _ref_bounds(fy,q):
	start = _ref_add_months(date(fy,FY_START,1),3 * (q - 1))
	return start,date.fromordinal(_ref_add_months(start,3).toordinal() - 1)

def _ref_half_up(num,den):
	whole,rest = divmod(num,den)
	return whole + (1 if 2 * rest >= den else 0)

def _ref_attribute(start,end,cents):
	parts,cur,guard = [],start,0
	while cur <= end and guard < 12:
		guard += 1
		fy = cur.year if cur.month >= FY_START else cur.year - 1
		q = ((cur.month - FY_START) % 12) // 3 + 1
		lo,hi = _ref_bounds(fy,q)
		first = max(start.toordinal(),lo.toordinal())
		last = min(end.toordinal(),hi.toordinal())
		# Inclusive at BOTH ends: the first and last day of a quarter belong to it.
		if last >= first:
			parts.append(((fy,q),last - first + 1))
		cur = date.fromordinal(hi.toordinal() + 1)
	if not parts:
		return []
	total = sum(days for _,days in parts)
	out = []
	for i,(period,days) in enumerate(parts):
		# The denominator is the whole span's days, not this quarter's length.
		cents_here = cents - sum(c for _,c in out) if i == len(parts) - 1 \
			else _ref_half_up(cents * days,total)
		out.append((period,cents_here))
	return out

def _ref_pct(cents,percent):
	return _ref_half_up(cents * percent,100)

def _ref_prorate(cents,part,whole):
	return _ref_half_up(cents * part,whole)

# --- cases ---------------------------------------------------------------------
#
# guard=true means the case passes under the planted bugs. A guard that passes at the
# start and fails at the end is collateral damage, not an unfixed bug.

def _label(parts):
	return repr([(f"FY{p[0]}Q{p[1]}",c) for p,c in parts])

def _attr_case(name,start,end,cents,want,guard):
	reference = _ref_attribute(date.fromisoformat(start),date.fromisoformat(end),cents)
	return {"account":name,"guard":guard,
		"got":_label(billing.attribute(date.fromisoformat(start),date.fromisoformat(end),cents)),
		"want":_label(want),"reference":_label(reference),"expected":_label(want),
		"checker_fault":_label(reference) != _label(want)}

ATTRIBUTION_CASES = [
	_attr_case("recon-1-august-line","2026-08-01","2026-08-31",9200,
		[((2026,2),9200)],True),
	_attr_case("recon-2-whole-quarter","2026-07-01","2026-09-30",4600,
		[((2026,2),4600)],False),
	_attr_case("recon-3-boundary-crossing","2026-06-30","2026-07-15",3200,
		[((2026,1),200),((2026,2),3000)],False),
	_attr_case("recon-4-june-plus-july","2026-06-01","2026-07-31",46000,
		[((2026,1),22623),((2026,2),23377)],False),
	_attr_case("recon-5-last-day-only","2026-09-30","2026-09-30",700,
		[((2026,2),700)],False),
	_attr_case("recon-6-november-line","2026-11-01","2026-11-30",10000,
		[((2026,3),10000)],True),
]

# The parts of an attribution must always add back up to the line total, whatever else is
# wrong. This is what catches a "fix" that drops the leftover-cent reconciliation and
# silently loses or invents money.
#
# The guard flags are measured, not assumed: the first draft marked all four as guards and
# two of them are not, because dropping every part makes the sum zero rather than the
# amount. Those two are witnesses, and they are the more valuable of the set — a line whose
# parts vanish takes its money with them, and nothing else in the suite says so.
INVARIANT_SPANS = [
	("invariant-1-june-plus-july","2026-06-01","2026-07-31",46000,True),
	("invariant-2-boundary-crossing","2026-06-30","2026-07-15",3200,False),
	("invariant-3-full-fiscal-year","2026-01-01","2027-03-31",123457,False),
	("invariant-4-august-line","2026-08-01","2026-08-31",9200,True),
]

def _invariant_case(name,start,end,cents,guard):
	parts = billing.attribute(date.fromisoformat(start),date.fromisoformat(end),cents)
	total = sum(c for _,c in parts)
	return {"account":name,"guard":guard,"got":f"parts sum to {total}",
		"want":f"parts sum to {cents}","reference":"","expected":f"parts sum to {cents}",
		"checker_fault":False}

INVARIANT_CASES = [_invariant_case(n,s,e,c,g) for n,s,e,c,g in INVARIANT_SPANS]

# Direct pins on the rounding contract. All pass under the planted bugs, so all are guards,
# and together they separate half-up from banker's rounding: 2.5 and 4.5 both round up here
# and both round down under round(). This is where a "fix" that reaches for floats and
# round() gets caught.
MONEY_CASES = [
	{"account":"money-prorate-2.5","guard":True,"got":repr(money.prorate(10,1,4)),
		"want":"3","reference":repr(_ref_prorate(10,1,4)),"expected":"3","checker_fault":False},
	{"account":"money-prorate-4.5","guard":True,"got":repr(money.prorate(9,1,2)),
		"want":"5","reference":repr(_ref_prorate(9,1,2)),"expected":"5","checker_fault":False},
	{"account":"money-prorate-0.5","guard":True,"got":repr(money.prorate(1,1,2)),
		"want":"1","reference":repr(_ref_prorate(1,1,2)),"expected":"1","checker_fault":False},
	{"account":"money-prorate-exact","guard":True,"got":repr(money.prorate(3200,30,61)),
		"want":"1574","reference":repr(_ref_prorate(3200,30,61)),"expected":"1574",
		"checker_fault":repr(_ref_prorate(3200,30,61)) != "1574"},
	{"account":"money-pct-2.5","guard":True,"got":repr(money.pct(25,10)),
		"want":"3","reference":repr(_ref_pct(25,10)),"expected":"3","checker_fault":False},
	{"account":"money-pct-199","guard":True,"got":repr(money.pct(199,10)),
		"want":"20","reference":repr(_ref_pct(199,10)),"expected":"20","checker_fault":False},
	{"account":"money-split-remainder","guard":True,"got":repr(money.split_evenly(10,4)),
		"want":"[3, 3, 2, 2]","reference":"","expected":"[3, 3, 2, 2]","checker_fault":False},
	{"account":"money-split-exact","guard":True,"got":repr(money.split_evenly(100,3)),
		"want":"[34, 33, 33]","reference":"","expected":"[34, 33, 33]","checker_fault":False},
]

CALENDAR_CASES = [
	{"account":"fiscal-year-starts-april","guard":True,"got":repr(fiscal.FY_START_MONTH),
		"want":"4","reference":"","expected":"4","checker_fault":False},
	{"account":"fy2026-quarter-bounds","guard":True,
		"got":repr([(q,)+tuple(str(d) for d in fiscal.period_bounds(2026,q)) for q in (1,2,3,4)]),
		"want":repr([(1,"2026-04-01","2026-06-30"),(2,"2026-07-01","2026-09-30"),
			(3,"2026-10-01","2026-12-31"),(4,"2027-01-01","2027-03-31")]),
		"reference":"","expected":"","checker_fault":False},
]

def build_cases():
	return ATTRIBUTION_CASES + INVARIANT_CASES + MONEY_CASES + CALENDAR_CASES

def run():
	cases = []
	for case in build_cases():
		entry = dict(case)
		# A checker fault is decided by the checker's own statements disagreeing with each
		# other, and is independent of what the episode's code did. All three of
		# reference / want / expected describe the same correct answer, so if they are not
		# identical then this file is wrong — and a wrong ground truth must never be able
		# to present as a model being wrong. Comparing reference against `expected` alone
		# was not enough: corrupting only `want` slipped through and would have been
		# reported as an ordinary model failure.
		statements = {case["reference"],case["want"],case["expected"]} - {""}
		entry["fault"] = bool(case["checker_fault"]) or len(statements) > 1
		entry["passed"] = case["got"] == case["want"] and not entry["fault"]
		entry.pop("expected",None)
		entry.pop("checker_fault",None)
		cases.append(entry)
	return cases

def main():
	cases = run()
	if "--json" in sys.argv:
		print(json.dumps({"cases":cases}))
		return
	faults = [c["account"] for c in cases if c.get("fault")]
	for case in cases:
		mark = "pass" if case["passed"] else ("FAULT" if case.get("fault") else "FAIL")
		guard = " (guard)" if case["guard"] else ""
		print(f"{mark:5s} {case['account']}{guard}")
		if not case["passed"]:
			print(f"        got  {case['got']}")
			print(f"        want {case['want']}")
	failed = [c for c in cases if not c["passed"] and not c.get("fault")]
	print(f"\n{len(cases) - len(failed)}/{len(cases)} cases pass")
	if faults:
		print(f"CHECKER FAULT on {faults} — this file is wrong, not the model. Exit 2.")
		return 2
	return 0 if not failed else 1

if __name__ == "__main__":
	sys.exit(main())
