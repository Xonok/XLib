"""Integer-cent money helpers.

Every amount in this project is an integer number of cents at every stage. Never introduce
floating point: the till and the invoice exporter both reject fractional amounts, and a
float in the middle of the chain moves totals by whole cents.
"""

def mul(cents,factor):
	return cents * factor

def pct(cents,percent):
	"""Apply an integer percentage, rounded half up: 2.5 becomes 3, 4.5 becomes 5."""
	n = cents * percent
	return (2 * n + 100) // 200

def format_cents(cents):
	"""`1234` -> `12.34`, with a leading minus for negatives and no float anywhere."""
	sign = "-" if cents < 0 else ""
	units,rest = divmod(abs(cents),100)
	return f"{sign}{units}.{rest:02d}"
