"""
Run the repository's test suites.

	python3 tools/run_tests.py

One command, one runner, every suite. The list below is explicit rather than
a sweep of the tree: `dev/xhttp/compare/` holds ad-hoc scripts whose names
start with `test_` and that are not tests, and a runner that picks them up
would run a browser and a socket server where a suite was meant.

Every suite is run by `xtest`, the repository's own testing library, in
`dev/xtest/`. The suites are written in two styles — plain functions and
`unittest.TestCase` classes — and xtest runs both, so the style of a suite is
not a reason for it not to run.

Exit status is 0 if every suite passed, 1 otherwise.
"""

import os,sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The suites, in the order they are worth reading: the small ones first, so a
# failure in one of them is not buried under a long run.
SUITES = [
	"tools/test",
	"tools/release/test",
	"tools/skynet/test",
	"dev/xtest/tests",
	"dev/xconf/tests",
	"dev/xcsv/tests",
	"dev/xschema/tests",
	"tools/bbprs/test",
	"tools/taskview/test",
	"tools/xlint/test",
	"tools/marduk/test",
	"dev/xhttp/test",
	"tools/pybundle/test",
	"xlib_dev/tests",
]

def main():
	# `dev/` so the library suites find their library, and the repository root
	# so `xlib` and `xlib_dev` resolve. A suite may also set this up for
	# itself; doing it here means one place rather than one per suite.
	for entry in (os.path.join(ROOT, "dev"), ROOT):
		if entry not in sys.path:
			sys.path.insert(0, entry)
	sys.path.insert(0, os.path.join(ROOT, "dev", "xtest"))
	import xtest

	chosen = sys.argv[1:]
	suites = [s for s in SUITES if not chosen or s in chosen]
	if not suites:
		print("no suite matches %s" % " ".join(chosen))
		print("the suites are:")
		for s in SUITES:
			print("  " + s)
		return 1

	passed = failed = skipped = 0
	bad = []
	for suite in suites:
		print("")
		print("=== %s" % suite)
		outcome = xtest.run([os.path.join(ROOT, suite)])
		# xtest prints one line per test; the totals are what the summary needs.
		if outcome:
			failed += 1
			bad.append(suite)
		else:
			passed += 1
	print("")
	print("%d suites passed, %d failed" % (passed, failed))
	if bad:
		print("failed: " + ", ".join(bad))
	return 1 if failed else 0

if __name__ == "__main__":
	sys.exit(main())
