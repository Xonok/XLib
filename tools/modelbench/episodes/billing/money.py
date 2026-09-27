"""Integer-cent money helpers.

Every amount in this project is an integer number of cents at every stage. Never introduce
floating point: the payment provider rejects fractional amounts outright, and rounding
applied earlier in the pipeline changes the total the customer is charged.
"""

def pct(cents,percent):
	"""Apply an integer percentage, rounded half up. cents >= 0, percent >= 0.

	Half up means 2.5 becomes 3 and 4.5 becomes 5. It is NOT Python's round(), which is
	banker's rounding and would send 2.5 to 2 and 4.5 to 4."""
	n = cents * percent
	return (2 * n + 100) // 200

def prorate(cents,part,whole):
	"""Attribute `cents` across a split where `part` of `whole` units belong here.

	Rounded half up, for the same reason as pct(). The caller owns the leftover cents and
	must hand them to one specific part, so that the parts sum back to `cents` exactly."""
	if whole <= 0:
		raise ValueError("whole must be positive")
	n = cents * part
	return (2 * n + whole) // (2 * whole)

def split_evenly(cents,parts):
	"""Split an integer amount into `parts` integer shares summing to exactly `cents`.

	The remainder goes to the earliest shares, one extra cent each, so the result is
	deterministic and never depends on iteration order of a dict or a set."""
	if parts <= 0:
		raise ValueError("parts must be positive")
	share,extra = divmod(cents,parts)
	return [share + (1 if i < extra else 0) for i in range(parts)]
