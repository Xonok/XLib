import os,tempfile,unittest
from stockroom import csvio,items

CSV = "sku,name,mass_g,price_cents\nBOLT-M8,M8 bolt,2500,120\nNUT-M8,M8 nut,300,15\n"

class CsvTest(unittest.TestCase):
	def test_read_items(self):
		with tempfile.TemporaryDirectory() as d:
			path = os.path.join(d,"items.csv")
			with open(path,"w") as f:
				f.write(CSV)
			rows = csvio.read_items(path)
		self.assertEqual([row.sku for row in rows],["BOLT-M8","NUT-M8"])
		self.assertEqual(rows[0].mass_kg(),2)

	def test_stock_from_keeps_every_sku(self):
		with tempfile.TemporaryDirectory() as d:
			path = os.path.join(d,"items.csv")
			with open(path,"w") as f:
				f.write(CSV)
			book = csvio.stock_from(path)
		self.assertEqual(sorted(book.items),["BOLT-M8","NUT-M8"])

	def test_json_round_trip(self):
		from stockroom import jsonio
		with tempfile.TemporaryDirectory() as d:
			path = os.path.join(d,"items.json")
			jsonio.export_items(path,[items.StockItem("BOLT-M8","M8 bolt",2500,120)])
			with open(path) as f:
				payload = f.read()
		self.assertIn('"sku": "BOLT-M8"',payload)

if __name__ == "__main__":
	unittest.main()
