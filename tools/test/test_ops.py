"""Tests for tools/localbench/ops.py — no model required."""
import sys,unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "localbench"))

import ops

class FillerTests(unittest.TestCase):
	def test_filler_is_long_enough_and_ends_with_the_task(self):
		text = ops.human_filler(100)
		self.assertGreaterEqual(len(text), 400)
		self.assertTrue(text.endswith(ops.COUNT_PROMPT))

	def test_filler_scales(self):
		self.assertGreater(len(ops.human_filler(1000)), len(ops.human_filler(100)))

class HelperTests(unittest.TestCase):
	def test_median(self):
		self.assertEqual(ops.median([1, 3, None]), 2)
		self.assertIsNone(ops.median([]))

	def test_host_parts(self):
		self.assertEqual(ops.host_parts("http://host:1234"), ("host", 1234))
		self.assertEqual(ops.host_parts("host:1234"), ("host", 1234))
		self.assertEqual(ops.host_parts("bare"), ("bare", 11434))

if __name__ == "__main__":
	unittest.main()
