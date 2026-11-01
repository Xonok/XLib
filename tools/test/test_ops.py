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

	def test_filler_tag_changes_the_start(self):
		plain = ops.human_filler(100)
		tagged = ops.human_filler(100, tag="a")
		self.assertTrue(tagged.startswith("Request a."))
		self.assertNotEqual(plain.splitlines()[0], tagged.splitlines()[0])
		self.assertTrue(tagged.endswith(ops.COUNT_PROMPT))
		self.assertTrue(ops.human_filler(100, tag="b").startswith("Request b."))

class HelperTests(unittest.TestCase):
	def test_median(self):
		self.assertEqual(ops.median([1, 3, None]), 2)
		self.assertIsNone(ops.median([]))

	def test_host_parts(self):
		self.assertEqual(ops.host_parts("http://host:1234"), ("host", 1234))
		self.assertEqual(ops.host_parts("host:1234"), ("host", 1234))
		self.assertEqual(ops.host_parts("bare"), ("bare", 11434))

	def test_proc_sample_has_pressure_counters(self):
		sample = ops.proc_sample()
		for key in ("pswpin", "pswpout", "oom_kill", "MemAvailable", "SwapFree"):
			self.assertIsInstance(sample[key], int)
		self.assertEqual(len(sample["loadavg"]), 3)

	def test_ps_lookup_matches_the_tag_not_the_family(self):
		ps = {"models": [{"name": "gemma4:12b", "size": 10, "size_vram": 0},
			{"name": "gemma4:e4b", "size": 5, "size_vram": 99}]}
		self.assertEqual(ops.ps_lookup(ps, "gemma4:e4b"), {"size": 5, "size_vram": 99})
		self.assertIsNone(ops.ps_lookup(ps, "gemma4:26b"))

	def test_ps_lookup_tolerates_a_latest_suffix(self):
		ps = {"models": [{"name": "qwen2.5-3b-32k:latest", "size": 7, "size_vram": 7}]}
		self.assertEqual(ops.ps_lookup(ps, "qwen2.5-3b-32k"), {"size": 7, "size_vram": 7})
		self.assertEqual(ops.ps_lookup(ps, "qwen2.5-3b-32k:latest"), {"size": 7, "size_vram": 7})

	def test_stress_drift_ignores_a_rotating_prompt_mix(self):
		# the last third holds more long calls, but no target got slower
		targets = [100, 500, 1000] * 4
		calls = [{"target": t, "wall_s": {100: 1.0, 500: 5.0, 1000: 10.0}[t]} for t in targets]
		by_target, drift = ops.stress_drift(calls)
		self.assertEqual(drift, 1.0)
		self.assertEqual(by_target["1000"]["calls"], 4)

	def test_stress_drift_reports_a_real_slowdown(self):
		calls = [{"target": 100, "wall_s": w} for w in (1.0, 1.0, 2.0, 2.0)]
		calls += [{"target": 500, "wall_s": 5.0} for _ in range(4)]
		_, drift = ops.stress_drift(calls)
		self.assertEqual(drift, 1.5)

if __name__ == "__main__":
	unittest.main()
