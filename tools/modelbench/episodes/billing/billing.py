"""Attributing invoice lines to fiscal periods.

A line covers a span of days. The part of a line falling inside a period is attributed to
that period, prorated by days, in integer cents. The leftover cent from rounding belongs
to the LAST period in the span, so the parts always add back up to the line total exactly.
"""

from datetime import date
from fiscal import days_in_period,fiscal_year,period_bounds,period_contains,quarter_of
from money import prorate

def spanned(start,end):
	"""Every fiscal quarter the span [start,end] touches, in order."""
	out = []
	fy,q = fiscal_year(start),quarter_of(start)
	for _ in range(8):
		if period_bounds(fy,q)[0] > end:
			break
		out.append((fy,q))
		fy,q = (fy,q + 1) if q < 4 else (fy + 1,1)
	return out

def attribute(start,end,amount_cents):
	"""Split `amount_cents` across every fiscal period the span touches.

	Returns [(period, cents), ...] in period order, or [] if the span touches no period."""
	parts = []
	for fy,q in spanned(start,end):
		bounds = period_bounds(fy,q)
		lo,hi = max(start,bounds[0]),min(end,bounds[1])
		if not period_contains(lo,fy,q):
			continue
		parts.append(((fy,q),(hi - lo).days + 1))
	if not parts:
		return []
	whole = sum(days for _,days in parts)
	out = []
	for i,(period,days) in enumerate(parts):
		if i == len(parts) - 1:
			cents = amount_cents - sum(c for _,c in out)
		else:
			cents = prorate(amount_cents,days,days_in_period(*period))
		out.append((period,cents))
	return out
