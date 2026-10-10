"""
One-line runner for the xhttp test suite.

	python3 dev/xhttp/test/run.py

Runs every test. `--core` leaves out the edge cases, which are the ones
needing hand-crafted or hostile requests - tracked, but not yet the thing to
judge the library by.

Exit status is the usual unittest one: 0 if everything passed, 1 otherwise.
"""

import os,sys,unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
	sys.path.insert(0,HERE)

import harness

def build_suite(core_only = False):
	loader = unittest.TestLoader()
	suite = loader.discover(HERE,pattern = "test_*.py",top_level_dir = HERE)
	if not core_only:
		return suite
	return _prune(suite)

def _prune(suite):
	kept = unittest.TestSuite()
	for test in suite:
		if isinstance(test,unittest.TestSuite):
			kept.addTest(_prune(test))
			continue
		method = getattr(type(test),test._testMethodName,None)
		if method is not None and harness._is_tagged(method,"edge"):
			continue
		kept.addTest(test)
	return kept

def main():
	core_only = "--core" in sys.argv[1:]
	suite = build_suite(core_only)

	findings = harness.preflight()
	if findings:
		print("PREFLIGHT")
		for finding in findings:
			print("  ! " + finding)
		print("")

	runner = unittest.TextTestRunner(verbosity = 2,buffer = False)
	result = runner.run(suite)

	if core_only:
		print("")
		print("(--core: edge tests skipped)")
	if not result.wasSuccessful():
		print("")
		print("See dev/xhttp/test/README.md for what each group is for.")
	return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
	sys.exit(main())
