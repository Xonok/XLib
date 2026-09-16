import sys
sys.path.insert(0,"..")
import xprod
print(sys.path)
from xlib import xtest_1_0_0


def ordinary():
	inputs = {
		"food": 3,
		"water": 2
	}
	outputs = {
		"energy": 5,
		"waste": 3
	}
	stored = {
		"food": 8,
		"water": 5,
		"energy": 9,
		"waste": 4
	}
	delta = xprod.discrete(inputs,outputs,stored,3)
	return delta
def boundary():
	pass
def erroneous():
	pass

def run():
	ordinary()
