
############   from file: csv_tok.py   ############

def csv_tok_tokenize(line):
	"""Tokenize a CSV line into a list of tokens.

	Returns (tokens, error) where:
	- tokens is a list of strings/None values, or None if line is empty/comment
	- error is None on success, or a string describing the error
	"""
	if not line or not line.strip():
		return (None, None)
	if line.strip().startswith("//"):
		return (None, None)
	if line.endswith("\n"):
		line = line[:-1]
	in_quotes = False
	comment_pos = -1
	i = 0
	while i < len(line):
		c = line[i]
		if c == '"':
			in_quotes = not in_quotes
		elif c == '/' and not in_quotes and i + 1 < len(line) and line[i + 1] == '/':
			comment_pos = i
			break
		i += 1
	if comment_pos >= 0:
		line = line[:comment_pos].rstrip()
	if not line:
		return (None, None)
	tokens = []
	i = 0
	n = len(line)
	while i < n:
		c = line[i]
		if c == '"':
			i += 1
			field = []
			while i < n:
				c = line[i]
				if c == '"':
					if i + 1 < n and line[i + 1] == '"':
						field.append('"')
						i += 2
					else:
						i += 1
						break
				else:
					field.append(c)
					i += 1
			else:
				return (None, "unterminated quoted field")
			tokens.append("".join(field))
			if i < n and line[i] == ',':
				i += 1
		elif c == ',':
			tokens.append(None)
			i += 1
		else:
			start = i
			while i < n and line[i] != ',':
				i += 1
			field = line[start:i]
			tokens.append(field if field else None)
			if i < n and line[i] == ',':
				i += 1
	if line.endswith(','):
		tokens.append(None)
	return (tokens, None)

############   from file: csv_ser.py   ############

def csv_ser_serialize(*args):
	"""Serialize arguments into a CSV line.

	Returns (string, error) where:
	- string is the CSV line (with trailing newline), or None on error
	- error is None on success, or a string describing the error
	"""
	fields = []
	for arg in args:
		if arg is None:
			fields.append("")
		else:
			csv_ser_s = str(arg)
			if ',' in csv_ser_s or '"' in csv_ser_s or '\n' in csv_ser_s:
				csv_ser_s = '"' + csv_ser_s.replace('"', '""') + '"'
			fields.append(csv_ser_s)
	return (",".join(fields) + "\n", None)

############   from file: csv_file.py   ############


def csv_file_write_line(path, *data):
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

def csv_file_write_entry(path, schema, **data):
	"""Append a structured entry to a CSV file.

	Returns (None, error) where:
	- error is None on success, or a string describing the error
	"""
	tokens = [None] * len(schema)
	for key, value in data.items():
		if key not in schema:
			return (None, "unknown key: %s" % key)
		csv_file_idx = schema[key]
		tokens[csv_file_idx] = value
	return csv_file_write_line(path, *tokens)


def schema_parse(header):
	"""Parse a header line into a schema dict.

	Returns (schema, error) where:
	- schema is a dict mapping column names to indices, or None on error
	- error is None on success, or a string describing the error
	"""
	tokens, error = csv_tok_tokenize(header)
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
	tokens, error = csv_tok_tokenize(line)
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
