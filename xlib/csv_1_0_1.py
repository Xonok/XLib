############   from file: csv_tok.py   ############

def csv_tok_tokenize(line):
	if not line or not line.strip():
		return None, None
	if line.strip().startswith("//"):
		return None, None
	if line.endswith("\n"):
		line = line[:-1]
	in_quotes = False
	comment_pos = -1
	i = 0
	while i < len(line):
		c = line[i]
		if c == '"':
			in_quotes = not in_quotes
		elif c == "/" and not in_quotes and i + 1 < len(line) and line[i + 1] == "/":
			comment_pos = i
			break
		i += 1
	if comment_pos >= 0:
		line = line[:comment_pos].rstrip()
	if not line:
		return None, None
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
				return None, "unterminated quoted field"
			tokens.append("".join(field))
			if i < n and line[i] == ",":
				i += 1
		elif c == ",":
			tokens.append(None)
			i += 1
		else:
			start = i
			while i < n and line[i] != ",":
				i += 1
			field = line[start:i]
			tokens.append(field if field else None)
			if i < n and line[i] == ",":
				i += 1
	if line.endswith(","):
		tokens.append(None)
	return tokens, None

############   from file: csv_ser.py   ############

def csv_ser_serialize(*args):
	fields = []
	for arg in args:
		if arg is None:
			fields.append("")
		else:
			csv_ser_s = str(arg)
			if "," in csv_ser_s or '"' in csv_ser_s or "\n" in csv_ser_s:
				csv_ser_s = '"' + csv_ser_s.replace('"', '""') + '"'
			fields.append(csv_ser_s)
	return ",".join(fields) + "\n", None

def tokenize(line):
	"""Split a CSV line (with // comments and quoting) into cells."""
	return csv_tok_tokenize(line)

def serialize(*args):
	"""Join values into one CSV line with standard quoting."""
	return csv_ser_serialize(*args)

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
