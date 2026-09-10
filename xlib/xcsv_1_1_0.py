############   from file: _/csv_tok.py   ############

def __csv_tok_tokenize(line: str):
	if not line or not line.strip():
		return None, None

	# Handle line endings: \r\n, \n, \r
	if line.endswith("\r\n"):
		line = line[:-2]
	elif line.endswith("\n") or line.endswith("\r"):
		line = line[:-1]

	# Comment detection: only at line start (after stripping leading whitespace)
	stripped = line.lstrip()
	if stripped.startswith("//"):
		return None, None

	tokens: list[str | None] = []
	i = 0
	line_len = len(line)
	while i < line_len:
		c = line[i]
		if c == '"':
			i += 1
			field = []
			while i < line_len:
				c = line[i]
				if c == '"':
					if i + 1 < line_len and line[i + 1] == '"':
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
			if i < line_len and line[i] == ",":
				i += 1
		elif c == ",":
			tokens.append(None)
			i += 1
		else:
			start = i
			while i < line_len and line[i] != ",":
				i += 1
			field = line[start:i]
			tokens.append(field if field else None)
			if i < line_len and line[i] == ",":
				i += 1

	if line.endswith(","):
		tokens.append(None)

	return tokens, None
############   from file: _/csv_ser.py   ############

def __csv_ser_serialize(*args: str | None):
	fields = []
	for arg in args:
		if arg is None:
			fields.append("")
		else:
			__csv_ser_s = str(arg)
			if "," in __csv_ser_s or '"' in __csv_ser_s or "\n" in __csv_ser_s or "\r" in __csv_ser_s:
				__csv_ser_s = '"' + __csv_ser_s.replace('"', '""') + '"'
			fields.append(__csv_ser_s)
	return ",".join(fields) + "\n", None
############   from file: xcsv.py   ############

"""xcsv — CSV library with // comment support, quoting, and schema-aware parsing.

This library provides a tokenizer/serializer for CSV with:
- Standard CSV quoting (RFC 4180 compatible)
- // line comments (only at line start)
- Empty field support (None)
- Schema-aware parsing/writing

API is organized in three stages:

Stage 1 — Line-based (no schema awareness):
read_line, read_all, write_line_tokens, write_all

Stage 2 — Schema-based (header-aware, no reschema):
schema_parse, parse_line, parse_all, write_entry, write_entries

Stage 3 — Parser/Writer objects (reschema + tail-follow):
file_reader, file_writer, file_writer_open (planned for future version)

All public functions return (result, error) tuples by default.
Pass raise_errors=True to raise exceptions instead.

Exception hierarchy:
CSVError
ParseError          # tokenize/parse failure
SchemaError         # schema mismatch, unknown key, wrong field count
UnfinishedLineError # fewer fields than schema (unless allow_unfinished)
IOError             # file read/write failure
ReschemaError       # malformed reschema row
"""
class CSVError(Exception):
	pass
class ParseError(CSVError):
	pass
class SchemaError(CSVError):
	pass
class UnfinishedLineError(CSVError):
	pass
class IOError(CSVError):
	pass
class ReschemaError(CSVError):
	pass
def _normalize_schema(schema: list[str] | dict[str, int]):
	"""Accept list [col1, col2...] or dict {col: index} → return dict."""
	if isinstance(schema, list):
		return {col: i for i, col in enumerate(schema)}
	return schema
def tokenize(line: str, raise_errors: bool = False):
	"""Split a CSV line (with // comments and quoting) into cells.
	Returns (tokens, error) where tokens is list[str] | None."""
	result, error = __csv_tok_tokenize(line)
	if error:
		if raise_errors:
			raise ParseError(error)
		return None, error
	return result, None
def serialize(*args: str | None, raise_errors: bool = False):
	"""Join values into one CSV line with standard quoting.
	Returns (line, error) where line is str."""
	result, error = __csv_ser_serialize(*args)
	if error:
		if raise_errors:
			raise ParseError(error)
		return None, error
	return result, None
def schema_parse(header: str, as_list: bool = False, raise_errors: bool = False):
	"""Header row → schema. as_list=False (default) returns {col: index} dict. as_list=True returns [col1, col2...] list.
	Returns (schema, error) where schema is dict[str, int] | list[str]."""
	tokens, error = tokenize(header)
	if error:
		if raise_errors:
			raise ParseError(error)
		return None, error
	if tokens is None:
		error = "expected header row"
		if raise_errors:
			raise ParseError(error)
		return None, error
	schema = {}
	for i, key in enumerate(tokens):
		if key is None:
			error = "empty column name at index %d" % i
			if raise_errors:
				raise SchemaError(error)
			return None, error
		schema[key] = i
	if as_list:
		return tokens, None
	return schema, None
def parse_line(line: str, schema: list[str] | dict[str, int], allow_unfinished: bool = False, raise_errors: bool = False):
	"""Parse one line against schema. Returns {col: value}. Raises SchemaError if field count mismatch (unless allow_unfinished). Accepts list or dict schema.
	Returns (data, error) where data is dict[str, str | None]."""
	tokens, error = tokenize(line)
	if error:
		if raise_errors:
			raise ParseError(error)
		return None, error
	if tokens is None:
		error = "expected a data row"
		if raise_errors:
			raise ParseError(error)
		return None, error

	schema_dict = _normalize_schema(schema)

	if not allow_unfinished and len(tokens) != len(schema_dict):
		error = "field count mismatch: expected %d, got %d" % (len(schema_dict), len(tokens))
		if raise_errors:
			raise SchemaError(error)
		return None, error

	data = {}
	for key, idx in schema_dict.items():
		data[key] = tokens[idx] if idx < len(tokens) else None
	return data, None
def write_line(path: str, *data: str | None, raise_errors: bool = False):
	"""Append serialized line to file.
	Returns (line, error) where line is str."""
	line, error = serialize(*data)
	if error:
		if raise_errors:
			raise ParseError(error)
		return None, error
	try:
		with open(path, "a", encoding="utf-8") as f:
			f.write(line)
	except IOError as e:
		error = str(e)
		if raise_errors:
			raise IOError(error)
		return None, error
	return line, None
def write_entry(path: str, schema: list[str] | dict[str, int], raise_errors: bool = False, allow_unfinished: bool = False, **data: str | None):
	"""Write one entry. Validates all keys in schema. If allow_unfinished, missing keys become empty fields. Accepts list or dict schema.
	Returns (line, error) where line is str."""
	schema_dict = _normalize_schema(schema)
	tokens = [None] * len(schema_dict)

	for key, value in data.items():
		if key not in schema_dict:
			error = "unknown key: %s" % key
			if raise_errors:
				raise SchemaError(error)
			return None, error
		tokens[schema_dict[key]] = value

	if not allow_unfinished:
		for key, idx in schema_dict.items():
			if tokens[idx] is None:
				error = "missing value for key: %s" % key
				if raise_errors:
					raise SchemaError(error)
				return None, error

	return write_line(path, *tokens, raise_errors=raise_errors)
# Stage 1 — Line-based (no schema awareness)
def read_line(path: str, offset: int = 0, discard_comments: bool = True, raise_errors: bool = False):
	"""Read one line from byte offset. Returns (tokens, next_offset). Comments return (None, next_offset) if not discarded.
	Returns (tokens, next_offset) where tokens is list[str] | None, next_offset is int."""
	try:
		with open(path, "r", encoding="utf-8") as f:
			f.seek(offset)
			line = f.readline()
			if not line:
				return None, offset
			next_offset = f.tell()

			tokens, error = tokenize(line)
			if error:
				if raise_errors:
					raise ParseError(error)
				return None, error

			if tokens is None and not discard_comments:
				return None, next_offset

			return tokens, next_offset
	except IOError as e:
		error = str(e)
		if raise_errors:
			raise IOError(error)
		return None, error
def read_all(path: str, discard_comments: bool = True, raise_errors: bool = False):
	"""Read entire file. Returns [(tokens, line_start, line_end), ...]. Header is just first entry.
	Returns (results, error) where results is list[tuple[list[str], int, int]]."""
	try:
		with open(path, "r", encoding="utf-8") as f:
			results = []
			offset = 0
			while True:
				line_start = offset
				line = f.readline()
				if not line:
					break
				offset = f.tell()
				line_end = offset

				tokens, error = tokenize(line)
				if error:
					if raise_errors:
						raise ParseError(error)
					return None, error

				if tokens is None and discard_comments:
					continue

				results.append((tokens, line_start, line_end))
			return results, None
	except IOError as e:
		error = str(e)
		if raise_errors:
			raise IOError(error)
		return None, error
def write_line_tokens(path: str, tokens: list[str | None], raise_errors: bool = False):
	"""Append one line (list of values/None) to file.
	Returns (None, error) where error is str | None."""
	line, error = serialize(*tokens)
	if error:
		if raise_errors:
			raise ParseError(error)
		return None, error
	try:
		with open(path, "a", encoding="utf-8") as f:
			f.write(line)
	except IOError as e:
		error = str(e)
		if raise_errors:
			raise IOError(error)
		return None, error
	return None, None
def write_all(path: str, lines: list[list[str | None]], raise_errors: bool = False):
	"""Append multiple lines to file. Returns count of lines written on success.
	Returns (count, error) where count is int."""
	count = 0
	for tokens in lines:
		result, error = write_line_tokens(path, tokens, raise_errors=raise_errors)
		if error:
			return None, error
		count += 1
	return None, None
# Stage 2 — Schema-based (header-aware, no reschema)
def parse_all(path: str, schema: list[str] | dict[str, int], allow_unfinished: bool = False, raise_errors: bool = False, reschema: bool = False):
	"""Read all lines, parse each against schema. Returns [entry_dict, ...]. Comments skipped. By default (reschema=False), reschema rows raise ReschemaError. If reschema=True, handles reschema rows and updates schema. Accepts list or dict schema.

	WARNING: When reschema=True and a __reschema__ row is encountered, the schema is updated for subsequent rows. The returned list contains entries with DIFFERENT schemas (earlier entries use old schema, later entries use new schema). Callers must handle this if they need schema consistency.
	Returns (results, error) where results is list[dict[str, str | None]]."""
	schema_dict = _normalize_schema(schema)
	results = []

	try:
		with open(path, "r", encoding="utf-8") as f:
			for line in f:
				tokens, error = tokenize(line)
				if error:
					if raise_errors:
						raise ParseError(error)
					return None, error

				if tokens is None:
					continue  # skip comments

				if tokens and tokens[0] == "__reschema__":
					if not reschema:
						error = "reschema row encountered"
						if raise_errors:
							raise ReschemaError(error)
						return None, error
					# Update schema from reschema row
					new_schema = tokens[1:]
					if not new_schema:
						error = "empty reschema row"
						if raise_errors:
							raise ReschemaError(error)
						return None, error
					schema_dict = {col: i for i, col in enumerate(new_schema)}
					continue

				if not allow_unfinished and len(tokens) != len(schema_dict):
					error = "field count mismatch: expected %d, got %d" % (len(schema_dict), len(tokens))
					if raise_errors:
						raise SchemaError(error)
					return None, error

				data = {}
				for key, idx in schema_dict.items():
					data[key] = tokens[idx] if idx < len(tokens) else None
				results.append(data)
	except IOError as e:
		error = str(e)
		if raise_errors:
			raise IOError(error)
		return None, error

	return results, None
def write_entries(path: str, schema: list[str] | dict[str, int], entries: list[dict[str, str | None]], raise_errors: bool = False, allow_unfinished: bool = False):
	"""Write multiple entries. Accepts list or dict schema. Returns count of entries written on success.
	Returns (count, error) where count is int."""
	schema_dict = _normalize_schema(schema)
	count = 0

	for entry in entries:
		tokens = [None] * len(schema_dict)
		for key, value in entry.items():
			if key not in schema_dict:
				error = "unknown key: %s" % key
				if raise_errors:
					raise SchemaError(error)
				return None, error
			tokens[schema_dict[key]] = value

		if not allow_unfinished:
			for key, idx in schema_dict.items():
				if tokens[idx] is None:
					error = "missing value for key: %s" % key
					if raise_errors:
						raise SchemaError(error)
					return None, error

		result, error = write_line_tokens(path, tokens, raise_errors=raise_errors)
		if error:
			return None, error
		count += 1

	return None, None
