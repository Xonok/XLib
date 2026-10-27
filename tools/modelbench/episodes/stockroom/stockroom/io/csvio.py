"""Reading the supplier's CSV export and writing the stock book back out."""

import csv
from stockroom import items,stock

def read_items(path):
	rows = []
	with open(path,newline="") as f:
		for row in csv.DictReader(f):
			rows.append(items.StockItem(row["sku"],row["name"],int(row["mass_g"]),
				int(row["price_cents"])))
	return rows

def stock_from(path):
	book = stock.Stock()
	for item in read_items(path):
		book.add(item,0)
	return book

def write_stock(path,book):
	with open(path,"w",newline="") as f:
		writer = csv.writer(f)
		writer.writerow(["sku","qty"])
		for sku,(item,qty) in sorted(book.items.items()):
			writer.writerow([sku,qty])
