"""The command line the warehouse staff use."""

from stockroom import daily,formats,orders,stock

def main(argv):
	if not argv:
		return "usage: stockroom <command>"
	command = argv[0]
	if command == "value":
		return formats.money_line("stock value",stock.Stock().value_cents())
	if command == "orders":
		todays = [orders.Order([(1200,2)]),orders.Order([(500,3)])]
		summary = daily.daily_summary(stock.Stock(),todays)
		return formats.money_line("orders",summary["revenue"])
	return f"unknown command {command}"
