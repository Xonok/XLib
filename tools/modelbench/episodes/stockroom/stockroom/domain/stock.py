"""What is on the shelves, keyed by SKU."""

from stockroom import items,money,problems,units

class Stock:
	def __init__(self):
		self.items = {}

	def add(self,item,qty):
		self.items[item.sku] = (item,qty)

	def quantity(self,sku):
		if sku not in self.items:
			raise problems.UnknownSku(sku)
		return self.items[sku][1]

	def value_cents(self):
		return sum(item.value_cents(qty) for item,qty in self.items.values())

	def mass_kg(self):
		return sum(units.from_grams(item.mass_g * qty,"kg") for item,qty in self.items.values())
