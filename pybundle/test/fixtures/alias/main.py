import util
from util import connect as link
from util import ping
import random as rr

def report():
	return link("http://x") + " " + ping()

if __name__ == "__main__":
	print("alias:", report(), rr.random() < 1.0)
