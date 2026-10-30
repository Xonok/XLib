import unittest
import stats

class TestMean(unittest.TestCase):
    def test_mean(self):
        self.assertEqual(stats.mean([2, 4]), 3)
    def test_empty(self):
        self.assertEqual(stats.mean([]), 0)

if __name__ == "__main__":
    unittest.main()
