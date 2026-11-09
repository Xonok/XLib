import unittest
import multibug

class TestAverage(unittest.TestCase):
    def test_average(self):
        self.assertEqual(multibug.average([2, 4]), 3)
    def test_empty(self):
        self.assertEqual(multibug.average([]), 0)

class TestClamp(unittest.TestCase):
    def test_mid(self):
        self.assertEqual(multibug.clamp(5, 0, 10), 5)
    def test_high(self):
        self.assertEqual(multibug.clamp(15, 0, 10), 10)
    def test_low(self):
        self.assertEqual(multibug.clamp(-3, 0, 10), 0)
    def test_boundary(self):
        self.assertEqual(multibug.clamp(10, 0, 10), 10)

class TestDedup(unittest.TestCase):
    def test_order(self):
        self.assertEqual(multibug.dedup([1, 2, 1, 3, 2]), [1, 2, 3])

if __name__ == "__main__":
    unittest.main()
