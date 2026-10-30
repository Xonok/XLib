"""Tests for tools/localbench — no model required."""
import io,json,os,sys,tempfile,unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "localbench"))

import ledger, run as runmod

def write_meta(runs, name, model, family, case, repeat, ok=True, contract=True, final=True):
	run_dir = Path(runs) / name
	run_dir.mkdir(parents=True)
	meta = {"model": model, "task": family, "case": case, "repeat": repeat,
		"started": f"2026-10-30T12:00:0{repeat}", "wall_time_s": 1.5,
		"prefill_tok_s": 100.0, "gen_tok_s": 20.0, "tool_calls": [{"name": "read", "source": "native"}],
		"checker": {"ok": ok, "contract_clean": contract, "reason": "x", "detail": {}}}
	(run_dir / "meta.json").write_text(json.dumps(meta))
	if final:
		(run_dir / "final").mkdir()
	(run_dir / "stdout.txt").write_text("")

class BenchVersionTests(unittest.TestCase):
	def test_stable_and_sensitive(self):
		with tempfile.TemporaryDirectory() as td:
			tasks = Path(td) / "tasks"
			(tasks / "f" / "c").mkdir(parents=True)
			(tasks / "f" / "c" / "task.json").write_text("{}")
			run_py = Path(td) / "run.py"
			run_py.write_text("# x\n")
			first = runmod.bench_version(tasks, run_py)
			self.assertEqual(first, runmod.bench_version(tasks, run_py))
			(tasks / "f" / "c" / "task.json").write_text("{\"a\":1}")
			self.assertNotEqual(first, runmod.bench_version(tasks, run_py))

class LedgerTests(unittest.TestCase):
	def test_one_row_per_run_and_idempotent(self):
		with tempfile.TemporaryDirectory() as td:
			runs = Path(td) / "runs"
			write_meta(runs, "a", "m1", "format", "f1", 1)
			write_meta(runs, "b", "m1", "format", "f1", 2)
			rows = ledger.find_runs(runs)
			self.assertEqual(len(rows), 2)
			out1 = Path(td) / "l1.jsonl"
			out2 = Path(td) / "l2.jsonl"
			ledger.write_jsonl(rows, out1)
			ledger.write_jsonl(rows, out2)
			self.assertEqual(out1.read_bytes(), out2.read_bytes())

	def test_markdown_groups_and_counts(self):
		with tempfile.TemporaryDirectory() as td:
			runs = Path(td) / "runs"
			write_meta(runs, "a", "m1", "format", "f1", 1, ok=True)
			write_meta(runs, "b", "m1", "format", "f1", 2, ok=False, contract=False)
			text = ledger.markdown(ledger.find_runs(runs))
			self.assertIn("| m1 | format | 2 | 1 | 1 |", text)

	def test_check_reports_state_missing_without_failing(self):
		with tempfile.TemporaryDirectory() as td:
			runs = Path(td) / "runs"
			write_meta(runs, "a", "m1", "format", "f1", 1, final=False)
			buf = io.StringIO()
			with redirect_stdout(buf):
				code = ledger.check_rows(ledger.find_runs(runs), Path(td) / "tasks")
			self.assertEqual(code, 0)
			self.assertIn("state_missing", buf.getvalue())

class MedianTests(unittest.TestCase):
	def test_median_ignores_non_numbers(self):
		self.assertEqual(ledger.median([1, 3, None, "x"]), 2)
		self.assertIsNone(ledger.median([]))

if __name__ == "__main__":
	unittest.main()
