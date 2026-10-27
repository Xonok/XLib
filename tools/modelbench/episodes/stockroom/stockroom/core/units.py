"""Unit conversions.

Mass is stored in grams, length in millimetres, and the display units are only ever a
presentation choice. Everything here is integer arithmetic on purpose: a fractional
kilogram going into a stock count is a rounding bug waiting to happen.
"""

def to_grams(value,unit):
	if unit == "kg":
		return value * 1000
	if unit == "g":
		return value
	raise ValueError(f"unknown mass unit {unit!r}")

def from_grams(grams,unit):
	if unit == "kg":
		return grams // 1000
	if unit == "g":
		return grams
	raise ValueError(f"unknown mass unit {unit!r}")

def to_millimetres(value,unit):
	if unit == "cm":
		return value * 10
	if unit == "mm":
		return value
	raise ValueError(f"unknown length unit {unit!r}")
