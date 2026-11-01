import os,sys
# xtest, one folder up from this one.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import xtest

def test_equal_pass():
	xtest.equal(1, 1)

def test_equal_fail():
	try:
		xtest.equal(1, 2)
	except AssertionError:
		pass
	else:
		raise AssertionError("expected equal to raise")

def test_not_equal():
	xtest.not_equal(1, 2)

def test_same():
	a = []
	xtest.same(a, a)

def test_true_pass():
	xtest.true("yes")

def test_true_fail():
	try:
		xtest.true(0)
	except AssertionError:
		pass
	else:
		raise AssertionError("expected true to raise")

def test_raises_pass():
	def boom():
		raise ValueError("bad")
	xtest.raises(ValueError, boom)

def test_raises_wrong_type():
	def boom():
		raise TypeError("bad")
	try:
		xtest.raises(ValueError, boom)
	except AssertionError:
		pass
	else:
		raise AssertionError("expected raises to reject wrong exception")

def test_raises_none():
	def ok():
		return 1
	try:
		xtest.raises(ValueError, ok)
	except AssertionError:
		pass
	else:
		raise AssertionError("expected raises to reject no exception")

def test_contains():
	xtest.contains("a", "banana")

def test_kind():
	xtest.kind(3, int)

if __name__ == "__main__":
	import sys
	sys.exit(xtest.run(__file__))

def test_not_contains_pass():
	xtest.not_contains("z", "banana")

def test_not_contains_fail():
	try:
		xtest.not_contains("a", "banana")
	except AssertionError:
		pass
	else:
		raise AssertionError("expected not_contains to raise")
