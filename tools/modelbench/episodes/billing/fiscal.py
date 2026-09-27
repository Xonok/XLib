"""Fiscal calendar.

Our fiscal year starts on 1 April, not 1 January. Finance confirmed this against the
consolidated ledger and the statutory accounts, so it is settled: April 2026 through
March 2027 is FY2026. The quarters run Apr-Jun, Jul-Sep, Oct-Dec, Jan-Mar.

A period's bounds are INCLUSIVE of both its first and its last day: 1 April and
30 June both belong to Q1. Every day of the year belongs to exactly one quarter.
"""

from datetime import date,timedelta

FY_START_MONTH = 4

def fiscal_year(d):
	"""The fiscal-year label for a date. Apr 2026 .. Mar 2027 is FY2026."""
	return d.year if d.month >= FY_START_MONTH else d.year - 1

def quarter_of(d):
	"""1..4, counting quarters from the start of the fiscal year."""
	return ((d.month - FY_START_MONTH) % 12) // 3 + 1

def _add_months(d,n):
	shifted = d.month - 1 + n
	return date(d.year + shifted // 12,shifted % 12 + 1,1)

def period_bounds(fy,quarter):
	"""First and last day of a fiscal quarter, inclusive on both ends."""
	start = _add_months(date(fy,FY_START_MONTH,1),3 * (quarter - 1))
	return start,_add_months(start,3) - timedelta(days=1)

def days_in_period(fy,quarter):
	"""Number of days in a fiscal quarter."""
	start,end = period_bounds(fy,quarter)
	return (end - start).days + 1

def period_contains(d,fy,quarter):
	"""Is `d` inside this fiscal quarter? Both boundary days belong to the quarter."""
	start,end = period_bounds(fy,quarter)
	return start < d < end
