#!/usr/bin/env python3
"""
Tests for the release gate — D37.

Run with: python3 -m unittest tools.release.test.test_release -v

**The gate is this repository's, not the bundler's.** The bundler's rule is that it
adds no findings of its own and passes through whatever the source already had
(D36), so a bundle can arrive carrying a finding. This repository does not
release those, so `release()` refuses. The pair of tests that matter is the
second one: the bundler is *supposed* to pass a pre-existing finding through, and
the gate is *supposed* to refuse it, and neither half is testable without the
other.

The fixtures live under `dev/` because `release()` deliberately derives the entry
from the library name — `dev/<library>/<library>.py` — and that check is the
thing being kept. Each one is removed on cleanup.
"""

import contextlib,io,shutil,sys,tempfile,unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import importlib.util
_spec = importlib.util.spec_from_file_location("release", ROOT / "tools" / "release" / "release.py")
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)

class ReleaseGateTestCase(unittest.TestCase):
	"""A throwaway library under `dev/`, and a throwaway destination for it."""

	def setUp(self):
		self.library = "gatetest"
		self.devdir = ROOT / "dev" / self.library
		self.addCleanup(shutil.rmtree, self.devdir, True)
		self.devdir.mkdir(parents = True)
		self.outdir = Path(tempfile.mkdtemp())
		self.addCleanup(shutil.rmtree, self.outdir, True)
		self.written = self.outdir / f"{self.library}_1_0_0.py"
		self.original = release.release_path
		release.release_path = lambda library, version: self.written
		self.addCleanup(setattr, release, "release_path", self.original)

	def write_library(self, text):
		(self.devdir / f"{self.library}.py").write_text(text, encoding = "utf-8", newline = "")

	def release_it(self):
		stderr = io.StringIO()
		with contextlib.redirect_stderr(stderr):
			release.release(self.library, "rev", False)
		return stderr.getvalue()

CLEAN = "import time\n\ndef stamp():\n\treturn time.time()\n"

class TestCleanBundleIsReleased(ReleaseGateTestCase):
	def test_a_lint_clean_library_is_released(self):
		self.write_library(CLEAN)
		self.release_it()
		self.assertTrue(self.written.is_file())
		self.assertIn("def stamp", self.written.read_text(encoding = "utf-8"))

	def test_the_written_file_is_the_bundler_output_unchanged(self):
		# The README's scope rule: no edits to what the bundler produced, so the
		# gate is the only thing between the bundle and `xlib/`.
		self.write_library(CLEAN)
		entry = self.devdir / f"{self.library}.py"
		self.release_it()
		self.assertEqual(self.written.read_text(encoding = "utf-8"), release.bundled(entry))

class TestDirtyBundleIsRefused(ReleaseGateTestCase):
	def test_a_bundle_carrying_a_finding_is_refused(self):
		# D36 in action: trailing whitespace is verbatim text, so the bundler
		# passes it through — and D37 says a release here will not have it.
		self.write_library("value = 1   \n")
		with self.assertRaises(ValueError) as caught:
			self.release_it()
		self.assertIn("trailing whitespace", str(caught.exception))

	def test_a_refusal_writes_nothing(self):
		self.write_library("value = 1   \n")
		with contextlib.redirect_stderr(io.StringIO()):
			with self.assertRaises(ValueError):
				release.release(self.library, "rev", False)
		self.assertFalse(self.written.exists())

	def test_the_refusal_reaches_the_caller_as_exit_one(self):
		self.write_library("value = 1   \n")
		stderr = io.StringIO()
		with contextlib.redirect_stderr(stderr):
			code = self.exit_code()
		self.assertEqual(code, 1)
		self.assertIn("not xlint-clean", stderr.getvalue())

	def exit_code(self):
		"""`main`'s own answer, which is what a person running the script sees."""
		with self.assertRaises(SystemExit) as exited:
			release.main([self.library])
		return exited.exception.code

class TestTheGateRunsXlintOnTheOutput(ReleaseGateTestCase):
	def test_a_clean_source_is_not_what_is_checked(self):
		# The gate is on the artefact, so this is the assertion that would fail if
		# it were pointed at the dev tree instead: the source's own finding travels
		# verbatim into the bundle, and it is the bundle that is refused.
		self.write_library("import time, sys\n\ndef stamp():\n\treturn time.time()\n")
		with self.assertRaises(ValueError) as caught:
			release.release(self.library, "rev", False)
		self.assertIn("space after comma", str(caught.exception))

	def test_the_probe_file_does_not_survive_the_check(self):
		self.write_library(CLEAN)
		before = set(self.outdir.iterdir())
		self.release_it()
		self.assertEqual(set(self.outdir.iterdir()) - before, {self.written})

if __name__ == "__main__":
	unittest.main()
