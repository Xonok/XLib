from db import core

def go():
	return core.create_conn().ping()

if __name__ == "__main__":
	print("deep:", go())
