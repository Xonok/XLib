import traceback
from .test2 import raw

def do_test(name,func):
	try:
		func()
	except Exception as e:
		print(traceback.format_exc())
def run():
	raw.peek()
	raw.tokenize()
	raw.read_line()
	raw.read_lines()
