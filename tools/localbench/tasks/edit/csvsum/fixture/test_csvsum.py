import os
import unittest
import csvsum

class TestTotal(unittest.TestCase):
    def test_total(self):
        path = os.path.join(os.path.dirname(__file__), "data.csv")
        self.assertEqual(csvsum.total(path), 10)

if __name__ == "__main__":
    unittest.main()
