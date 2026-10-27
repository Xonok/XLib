"""Customer orders: a list of (unit_price_cents, quantity) lines."""

from stockroom import money,units

class Order:
	def __init__(self,lines):
		self.lines = list(lines)

	def subtotal_cents(self):
		return sum(money.mul(unit_cents,qty) for unit_cents,qty in self.lines)

	def total_cents(self,tax_pct):
		subtotal = self.subtotal_cents()
		return subtotal + money.pct(subtotal,tax_pct)

	def total_units(self):
		return sum(qty for _,qty in self.lines)

	def shipping_weight_grams(self,kg_per_unit=1):
		return sum(units.to_grams(kg_per_unit * qty,"kg") for _,qty in self.lines)
