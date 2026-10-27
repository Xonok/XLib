"""Reconcile the stock book against the supplier's export; run by hand, not by the CLI."""

import sys
from stockroom import csvio,daily,paths

def main():
	book = csvio.stock_from(paths.data_file("supplier-export.csv"))
	return daily.daily_summary(book,[])

if __name__ == "__main__":
	print(main())
