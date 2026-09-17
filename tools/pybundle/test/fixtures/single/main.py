import helper
import os

def run():
	return helper.area(2.0), helper.shadow(2.0), helper.piq

if __name__ == "__main__":
	print("single:", run(), os.name)
