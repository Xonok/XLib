import unittest
from stockroom import money,orders

class OrderTest(unittest.TestCase):
	def test_subtotal(self):
		self.assertEqual(orders.Order([(120,3),(80,2)]).subtotal_cents(),520)

	def test_tax_is_half_up(self):
		self.assertEqual(money.pct(5,50),3)

	def test_weight(self):
		self.assertEqual(orders.Order([(100,2)]).shipping_weight_grams(),2000)

	def test_units(self):
		self.assertEqual(orders.Order([(100,2),(50,3)]).total_units(),5)

if __name__ == "__main__":
	unittest.main()
