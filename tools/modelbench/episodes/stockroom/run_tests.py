"""Run the project's own tests: python3 run_tests.py"""

import sys,unittest

def main():
	suite = unittest.defaultTestLoader.discover("tests",top_level_dir=".")
	result = unittest.TextTestRunner(verbosity=2).run(suite)
	return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
	sys.exit(main())
