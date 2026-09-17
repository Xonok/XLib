#requires a dictionary library to multiply a dictionary by a value

def discrete(inputs,outputs,inventory,processors=1) -> dict:
	limit = processors
	for k,v in inputs.items():
		stored = inventory.get(k,0)
		limit = min(stored//v,limit)
	output = {k: v*limit for k,v in inputs.items()}
	return output
def _discrete_limit(reqs,stored) -> int:
	
	for k,v in inputs.items():
		stored = inventory.get(k,0)
		limit = min(stored//v,limit)
	return stored//req
