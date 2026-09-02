import xtest

@xtest.test
def registered():
	xtest.equal(2 + 2, 4)

@xtest.test
def registered_two():
	xtest.true(not False)
