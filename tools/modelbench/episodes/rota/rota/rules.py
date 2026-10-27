"""Pay rules: an unpaid break, and overtime after forty paid minutes.

All money is integer cents, truncated to the cent at each part. The two parts of a
shift's pay are computed separately and added, so the total is the sum of two truncated
amounts and never a single division of the whole.
"""

OVERTIME_AFTER_MINUTES = 40 * 60
OVERTIME_NUMERATOR = 3
OVERTIME_DENOMINATOR = 2
BREAK_AFTER_MINUTES = 6 * 60
BREAK_MINUTES = 30

def payable_minutes(minutes):
	"""Minutes paid for a shift: a thirty-minute break is deducted above six hours.

	The comparison is strict, so a shift of exactly six hours is paid in full."""
	if minutes > BREAK_AFTER_MINUTES:
		return minutes - BREAK_MINUTES
	return minutes

def pay_cents(minutes,rate_cents_per_hour):
	"""Pay for a shift in integer cents.

	The first forty *paid* minutes are at `rate_cents_per_hour`; everything after the
	break is at one and a half times the rate. The break comes out before the overtime
	threshold is applied."""
	paid = payable_minutes(minutes)
	regular = min(paid,OVERTIME_AFTER_MINUTES)
	overtime = paid - regular
	regular_cents = regular * rate_cents_per_hour // 60
	overtime_cents = overtime * rate_cents_per_hour * OVERTIME_NUMERATOR // (60 * OVERTIME_DENOMINATOR)
	return regular_cents + overtime_cents
