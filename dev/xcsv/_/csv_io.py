from . import csv_err,csv_schema,csv_ser,csv_tok

def read_line(path: str, offset: int = 0, discard_comments: bool = True):
	"""Read one line from a byte offset -> (tokens, next_offset).

	A comment or a blank line yields (None, next_offset), because the caller
	asked for the offset whatever the line turned out to be."""
	try:
		with open(path, "r", encoding="utf-8") as f:
			f.seek(offset)
			line = f.readline()
			if not line:
				return None, offset
			next_offset = f.tell()
	except OSError as error:
		raise csv_err.IOError(str(error)) from None
	tokens = csv_tok.tokenize(line)
	if tokens is None and not discard_comments:
		return None, next_offset
	return tokens, next_offset

def read_all(path: str, discard_comments: bool = True):
	"""Read the whole file -> [(tokens, line_start, line_end), ...]."""
	results = []
	try:
		with open(path, "r", encoding="utf-8") as f:
			offset = 0
			while True:
				line_start = offset
				line = f.readline()
				if not line:
					break
				offset = f.tell()
				line_end = offset
				tokens = csv_tok.tokenize(line)
				if tokens is None and discard_comments:
					continue
				results.append((tokens, line_start, line_end))
	except OSError as error:
		raise csv_err.IOError(str(error)) from None
	return results

def append_line(path: str, *tokens: str | None):
	"""Serialize tokens and append them to path -> the line written."""
	line = csv_ser.serialize(*tokens)
	try:
		with open(path, "a", encoding="utf-8") as f:
			f.write(line)
	except OSError as error:
		raise csv_err.IOError(str(error)) from None
	return line

def append_lines(path: str, lines: list[list[str | None]]):
	"""Append every line -> how many were written."""
	count = 0
	for tokens in lines:
		append_line(path, *tokens)
		count += 1
	return count

def parse_all(path: str, schema: list[str] | dict[str, int], allow_unfinished: bool = False, reschema: bool = False):
	"""Parse every data row of path -> [entry, ...].

	Comments are skipped. A __reschema__ row is a schema change: it raises
	unless reschema is set, and from then on the rows are parsed against the
	schema it declared, so the entries before it and after it do not share one."""
	schema_dict = csv_schema.normalize_schema(schema)
	results = []
	try:
		with open(path, "r", encoding="utf-8") as f:
			for line in f:
				tokens = csv_tok.tokenize(line)
				if tokens is None:
					continue
				if tokens and tokens[0] == "__reschema__":
					if not reschema:
						raise csv_err.ReschemaError("reschema row encountered")
					schema_dict = csv_schema.reschema_from(tokens)
					continue
				results.append(csv_schema.row_to_entry(tokens, schema_dict, allow_unfinished))
	except OSError as error:
		raise csv_err.IOError(str(error)) from None
	return results

def write_entries(path: str, schema: list[str] | dict[str, int], entries: list[dict[str, str | None]], allow_unfinished: bool = False):
	"""Append every entry -> how many were written."""
	count = 0
	for entry in entries:
		tokens = csv_schema.entry_to_tokens(entry, schema, allow_unfinished)
		append_line(path, *tokens)
		count += 1
	return count
