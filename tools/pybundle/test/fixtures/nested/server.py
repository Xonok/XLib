from server import Analysis
from server import defs,io

if __name__ == "__main__":
	print("nested:", Analysis.itemcount.run(), Analysis.itemcount.more("!"), defs.label, defs.items["a"], defs.show(), io.save())
