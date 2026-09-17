items = {"a": 1}
label = "one"

def show():
	return label + ":" + ",".join(map(str, items))
