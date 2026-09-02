from .csv_tok import tokenize as _tokenize
from .csv_ser import serialize as _serialize

def tokenize(line):
	"""Split a CSV line (with // comments and quoting) into cells."""
	return _tokenize(line)

def serialize(*args):
	"""Join values into one CSV line with standard quoting."""
	return _serialize(*args)

def schema_parse(header):
	tokens, error = tokenize(header)
	if error:
		return None, error
	if tokens is None:
		return None, "expected header row"
	schema = {}
	for i, key in enumerate(tokens):
		if key is None:
			return None, "empty column name at index %d" % i
		schema[key] = i
	return schema, None

def parse_line(line, schema):
	tokens, error = tokenize(line)
	if error:
		return None, error
	if tokens is None:
		return None, "expected a data row"
	data = {}
	for key, idx in schema.items():
		data[key] = tokens[idx] if idx < len(tokens) else None
	return data, None

def write_line(path, *data):
	line, error = serialize(*data)
	if error:
		return None, error
	try:
		with open(path, "a") as f:
			f.write(line)
	except IOError as e:
		return None, str(e)
	return None, None

def write_entry(path, schema, **data):
	tokens = [None] * len(schema)
	for key, value in data.items():
		if key not in schema:
			return None, "unknown key: %s" % key
		tokens[schema[key]] = value
	return write_line(path, *tokens)
