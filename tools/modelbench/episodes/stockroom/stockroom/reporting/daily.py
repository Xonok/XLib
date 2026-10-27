"""The day's summary, built from the stock book and the day's orders."""

from stockroom import money,orders,stock

def daily_summary(book,todays_orders):
	revenue = sum(order.subtotal_cents() for order in todays_orders)
	return {"revenue":revenue,"tax":money.pct(revenue,20),
		"stock_value":book.value_cents(),
		"units":sum(order.total_units() for order in todays_orders)}

def low_stock(book,minimum):
	"""A fresh book holding the SKUs at or below `minimum`, so the floor can reorder them."""
	out = stock.Stock()
	for sku,(item,qty) in book.items.items():
		if qty <= minimum:
			out.add(item,qty)
	return out
