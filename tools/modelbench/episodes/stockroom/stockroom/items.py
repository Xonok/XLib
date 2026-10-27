"""The stock item, as the warehouse floor records it."""

from stockroom import units

class StockItem:
	def __init__(self,sku,name,mass_g,price_cents):
		self.sku,self.name,self.mass_g,self.price_cents = sku,name,mass_g,price_cents

	def mass_kg(self):
		return units.from_grams(self.mass_g,"kg")

	def value_cents(self,qty=1):
		return self.price_cents * qty
