"""The repository's test layout, and the guard over it.

A suite that cannot be run is a suite that does not exist, and one that cannot
be run by the obvious command is worse than one that fails loudly: it reports
success over content it never examined. Five suites in this repository were in
that state on 2026-10-20 — `tools/test/test_epiq_pending.py`, `dev/xconf`,
`dev/xschema` and xtest's own two — and every one of them exited 0 having run
nothing.

These tests pin the shape that keeps that from happening again: every test
file is in a suite the runner knows about, every test file can be run on its
own, and every suite the runner lists holds at least one test.
"""
import os,sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dev" / "xtest"))
sys.path.insert(0, str(ROOT / "tools"))
import xtest

import run_tests

# Files whose names start with `test_` and that are not tests. The comparison
# scripts in `dev/xhttp/compare/` are hand-run probes against another
# implementation; they were moved out of `dev/xhttp/test/` on purpose, because
# that folder's runner discovers `test_*.py` and would enrol them in the
# suite.
NOT_TESTS = [
	"dev/xhttp/compare/test_original_ping.py",
	"dev/xhttp/compare/test_original_websocket.py",
	"dev/xhttp/compare/test_selenium.py",
	"dev/xhttp/compare/test_server.py",
	"dev/xhttp/compare/test_websocket_client.py",
	"dev/xhttp/compare/test_working_comprehensive.py",
]

# Trees that are benchmark inputs rather than repository code. An episode is a small
# project the model under test works in, and it carries its own test suite on purpose:
# that suite is what the model runs and what the episode's checker exercises. Those files
# are not this repository's tests and no runner here is supposed to reach them, so the
# whole tree is excluded rather than every episode being listed above.
NOT_TEST_TREES = ("tools/modelbench/episodes/",)

def test_every_suite_the_runner_lists_exists():
	for suite in run_tests.SUITES:
		xtest.true((ROOT / suite).is_dir(), f"{suite} is listed but is not a folder")

def test_every_suite_holds_at_least_one_test():
	for suite in run_tests.SUITES:
		found = list((ROOT / suite).glob("test_*.py"))
		xtest.true(found, f"{suite} is listed but holds no test file")

def test_every_test_file_is_in_a_suite_or_a_listed_exception():
	in_suite = set()
	for suite in run_tests.SUITES:
		for path in (ROOT / suite).glob("test_*.py"):
			in_suite.add(str(path.relative_to(ROOT)))
	everywhere = set()
	for path in ROOT.rglob("test_*.py"):
		relative = str(path.relative_to(ROOT))
		if "__pycache__" in relative or relative.startswith(".work/"):
			continue
		if relative.startswith(NOT_TEST_TREES):
			continue
		everywhere.add(relative)
	stray = everywhere - in_suite - set(NOT_TESTS)
	xtest.equal(stray, set(), f"test files that no runner reaches: {sorted(stray)}")

def test_every_test_file_can_be_run_on_its_own():
	# A file with no `__main__` block runs as an import and does nothing, which
	# is the shape of the failure this file exists to prevent.
	for suite in run_tests.SUITES:
		for path in sorted((ROOT / suite).glob("test_*.py")):
			text = path.read_text(encoding="utf-8")
			xtest.contains("__main__", text,
				f"{path.relative_to(ROOT)} cannot be run on its own")

def test_the_runner_reaches_every_suite_it_lists():
	# The runner's list and its own behaviour have to agree: a suite in the
	# list that the runner cannot load is a suite that silently does nothing.
	for suite in run_tests.SUITES:
		folder = ROOT / suite
		files = [str(p) for p in sorted(folder.glob("test_*.py"))]
		xtest.true(files, f"{suite} holds no test file")
		# The internal, because the public `run` also runs them, and the
		# runner has already run them; what is being asked here is only
		# whether the runner would find anything.
		groups = xtest._groups_for(files)
		found = sum(len(group.plain) + len(group.xtest_cases) + len(group.unittest_cases)
			for group in groups)
		xtest.true(found, f"{suite} holds test files but xtest finds no tests in them")
