from .csv_tok import tokenize
from .csv_ser import serialize
from .csv_file import write_line,write_entry

def schema_parse(header):
	"""Parse a header line into a schema dict.

	Returns (schema, error) where:
	- schema is a dict mapping column names to indices, or None on error
	- error is None on success, or a string describing the error
	"""
	tokens, error = tokenize(header)
	if error:
		return (None, error)
	if tokens is None:
		return (None, "empty header")
	schema = {}
	for i, key in enumerate(tokens):
		if key is None:
			return (None, "empty column name at index %d" % i)
		schema[key] = i
	return (schema, None)

def parse_line(line, schema):
	"""Parse a data line using a schema.

	Returns (data, error) where:
	- data is a dict mapping column names to values, or None on error
	- error is None on success, or a string describing the error
	"""
	tokens, error = tokenize(line)
	if error:
		return (None, error)
	if tokens is None:
		return (None, "empty line")
	data = {}
	for key, idx in schema.items():
		if idx < len(tokens):
			data[key] = tokens[idx]
		else:
			data[key] = None
	return (data, None)
