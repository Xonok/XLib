import os,sys
# xtest, one folder up from this one.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import xtest

@xtest.test
def registered():
	xtest.equal(2 + 2, 4)

@xtest.test
def registered_two():
	xtest.true(not False)

if __name__ == "__main__":
	import sys
	sys.exit(xtest.run(__file__))
