"""Turning numbers into the lines the reports print."""

from stockroom import money

def money_line(label,cents):
	return f"{label}: {money.format_cents(cents)}"

def count_line(label,count,unit):
	return f"{label}: {count} {unit}"
