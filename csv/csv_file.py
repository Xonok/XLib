from .csv_tok import tokenize
from .csv_ser import serialize

def write_line(path, *data):
	"""Append a CSV line to a file.

	Returns (None, error) where:
	- error is None on success, or a string describing the error
	"""
	line, error = serialize(*data)
	if error:
		return (None, error)
	try:
		with open(path, "a") as f:
			f.write(line)
	except IOError as e:
		return (None, str(e))
	return (None, None)

def write_entry(path, schema, **data):
	"""Append a structured entry to a CSV file.

	Returns (None, error) where:
	- error is None on success, or a string describing the error
	"""
	tokens = [None] * len(schema)
	for key, value in data.items():
		if key not in schema:
			return (None, "unknown key: %s" % key)
		idx = schema[key]
		tokens[idx] = value
	return write_line(path, *tokens)
