"""Defaults shared by the command line and the reports."""

from stockroom import paths

DEFAULT_CURRENCY = "EUR"
DEFAULT_TAX_PCT = 20

def rates_file():
	return paths.data_file("rates.csv")

def export_file():
	return paths.data_file("supplier-export.csv")
