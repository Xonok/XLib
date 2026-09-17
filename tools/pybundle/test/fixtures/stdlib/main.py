from urllib.parse import urlparse
import json
import collections
from collections import defaultdict
import math as m

def go(u):
	return m.floor(u), json.dumps(urlparse("http://x/a").scheme), defaultdict(int)

if __name__ == "__main__":
	print("stdlib:", go(1.5))
