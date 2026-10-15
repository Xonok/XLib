#!/usr/bin/env python3
"""
Tests for `cli(argv)` — D13 and D14.

Run with: python3 -m unittest tools.pybundle.test.test_bundler_cli -v

D12 put `cli` in the function set and D13 settled what it does: parse argv, open
and close the sink, call `main`, and answer 0 or 1. Before D13 the whole command
line was untestable, because no function owned it.

**One reading is assumed, and it is flagged as an open question.** Every call
below passes the arguments *without* a program name, i.e. what `sys.argv[1:]`
holds. D13 names the parameter `argv` and does not say whether the program name
is in it. If the human rules the other way, every literal in this file gains that
name at the front — and `test_no_arguments_returns_one` still passes either way,
because an empty list and a one-element list holding a program name are both
"no flags given". See `doc/reviews/pybundle-tests-pass1.md`, flaw F14.
"""

import contextlib,io,sys,tempfile,unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pybundle.bundler import main
from tools.pybundle.bundler_cli import cli

class CliTestCase(unittest.TestCase):
	"""A throwaway folder per test, and a tree with one local import in it."""

	TREE = {"server.py": "import helper\n", "helper.py": "count = 1\n"}

	def setUp(self):
		tmpdir = tempfile.TemporaryDirectory()
		self.addCleanup(tmpdir.cleanup)
		self.root = Path(tmpdir.name)
		self.write_files(self.TREE)

	def write_files(self, files):
		for name, text in files.items():
			path = self.root / name
			path.parent.mkdir(parents=True, exist_ok=True)
			path.write_text(text, encoding="utf-8", newline="")

	def run_cli(self, argv):
		"""Runs `cli` with both standard streams captured, and returns the exit
		code and the two streams in that order."""
		stdout, stderr = io.StringIO(), io.StringIO()
		with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
			code = cli(argv)
		return code, stdout.getvalue(), stderr.getvalue()

	def bundle_main_writes(self):
		"""The bundle for the current tree, through the core seam and nothing
		else. stderr is swallowed because a diagnostic reaching it is not what
		these tests are about."""
		sink = io.StringIO()
		with contextlib.redirect_stderr(io.StringIO()):
			main(str(self.root / "server.py"), sink)
		return sink.getvalue()

class TestSuccess(CliTestCase):
	"""D13: a run that works exits 0, and the bundle reaches the out file."""

	def test_a_valid_run_returns_zero(self):
		code, _, _ = self.run_cli(["--in", str(self.root / "server.py"), "--out", str(self.root / "out.py")])
		self.assertEqual(code, 0)

	def test_the_out_file_holds_the_whole_bundle(self):
		# The root's block is written last, so finding it in a file read after
		# `cli` returned means `cli` closed what it opened — D13, and R5's "never
		# closes a sink it did not open" from the other side.
		out_path = self.root / "out.py"
		self.run_cli(["--in", str(self.root / "server.py"), "--out", str(out_path)])
		self.assertIn("## server.py", out_path.read_text(encoding="utf-8"))

	def test_the_bundle_cli_writes_is_the_bundle_main_writes(self):
		# R5 — one code path, only the sink differs.
		out_path = self.root / "out.py"
		self.run_cli(["--in", str(self.root / "server.py"), "--out", str(out_path)])
		self.assertEqual(out_path.read_text(encoding="utf-8"), self.bundle_main_writes())

class TestStdoutSink(CliTestCase):
	"""D13: `--out -` is stdout, and it opens nothing."""

	def setUp(self):
		super().setUp()
		self.write_files({"first.py": "import shared\n", "shared.py": "count = 1\n"})
		self.write_files({"server.py": "import first\nimport shared\n"})

	def test_out_dash_writes_the_bundle_to_stdout(self):
		_, stdout_text, _ = self.run_cli(["--in", str(self.root / "server.py"), "--out", "-"])
		self.assertIn("helper__count = 1", stdout_text)

	def test_out_dash_returns_zero(self):
		code, _, _ = self.run_cli(["--in", str(self.root / "server.py"), "--out", "-"])
		self.assertEqual(code, 0)

	def test_a_diagnostic_warns_on_stderr_while_stdout_carries_only_the_bundle(self):
		# D14, and the case F9 was about: a message on stdout would corrupt the
		# bundle whenever the sink *is* stdout.
		_, stdout_text, _ = self.run_cli(["--in", str(self.root / "server.py"), "--out", "-"])
		self.assertEqual(stdout_text, self.bundle_main_writes())

	def test_a_dropped_second_reference_warns_on_stderr(self):
		_, _, stderr_text = self.run_cli(["--in", str(self.root / "server.py"), "--out", "-"])
		self.assertTrue(stderr_text)

class TestUsage(CliTestCase):
	"""D13: both flags are required and nothing else is accepted."""

	def test_no_arguments_returns_one(self):
		code, _, _ = self.run_cli([])
		self.assertEqual(code, 1)

	def test_a_missing_out_flag_returns_one(self):
		code, _, _ = self.run_cli(["--in", str(self.root / "server.py")])
		self.assertEqual(code, 1)

	def test_a_missing_in_flag_returns_one(self):
		code, _, _ = self.run_cli(["--out", str(self.root / "out.py")])
		self.assertEqual(code, 1)

	def test_an_unrecognised_argument_returns_one(self):
		code, _, _ = self.run_cli(["--in", str(self.root / "server.py"), "--out", "-", "--extra"])
		self.assertEqual(code, 1)

	def test_an_input_path_that_does_not_exist_returns_one(self):
		# The flag is given and names something unusable, which is a cli error
		# rather than a bundler one. `main` still raises; `cli` is what answers 1.
		code, _, _ = self.run_cli(["--in", str(self.root / "gone.py"), "--out", "-"])
		self.assertEqual(code, 1)

	def test_an_output_path_that_cannot_be_opened_returns_one(self):
		# The same reading, on the other flag: the sink cannot be opened.
		code, _, _ = self.run_cli(["--in", str(self.root / "server.py"), "--out", str(self.root / "gone" / "out.py")])
		self.assertEqual(code, 1)

	def test_usage_is_printed_on_stderr(self):
		_, _, stderr_text = self.run_cli([])
		self.assertTrue(stderr_text)

	def test_usage_is_not_printed_on_stdout(self):
		_, stdout_text, _ = self.run_cli([])
		self.assertEqual(stdout_text, "")

class TestBundlerErrors(CliTestCase):
	"""D13: a bundler error is reported on stderr and becomes exit code 1."""

	def setUp(self):
		super().setUp()
		self.write_files({"server.py": "from . import helper\n"})

	def test_a_relative_import_in_the_root_returns_one(self):
		code, _, _ = self.run_cli(["--in", str(self.root / "server.py"), "--out", "-"])
		self.assertEqual(code, 1)

	def test_a_bundler_error_is_reported_on_stderr(self):
		_, _, stderr_text = self.run_cli(["--in", str(self.root / "server.py"), "--out", "-"])
		self.assertIn("RELATIVE_IMPORT_IN_ROOT", stderr_text)

	def test_a_bundler_error_writes_nothing_to_stdout(self):
		_, stdout_text, _ = self.run_cli(["--in", str(self.root / "server.py"), "--out", "-"])
		self.assertEqual(stdout_text, "")

if __name__ == "__main__":
	unittest.main()
