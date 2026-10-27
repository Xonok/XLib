"""The JSON export the reporting service reads."""

import json
from stockroom import items

def export_items(path,rows):
	payload = [{"sku":item.sku,"name":item.name,"mass_g":item.mass_g,
		"price_cents":item.price_cents} for item in rows]
	with open(path,"w") as f:
		json.dump(payload,f)

def read_item(row):
	return items.StockItem(row["sku"],row["name"],int(row["mass_g"]),
		int(row["price_cents"]))
