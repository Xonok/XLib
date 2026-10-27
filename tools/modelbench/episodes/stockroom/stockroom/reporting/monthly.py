"""Roll a month of daily summaries into one figure."""

from stockroom import daily,money

def month_totals(summaries):
	revenue = sum(summary["revenue"] for summary in summaries)
	return {"revenue":revenue,"formatted":money.format_cents(revenue)}

def month_from_days(book,orders_by_day):
	return month_totals([daily.daily_summary(book,day) for day in orders_by_day])
