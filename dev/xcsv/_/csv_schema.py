from . import csv_err

def normalize_schema(schema: list[str] | dict[str, int]):
	"""Accept list [col1, col2...] or dict {col: index} -> dict, whichever form the caller brought."""
	if isinstance(schema, list):
		return {col: i for i, col in enumerate(schema)}
	return schema

def schema_from(header_tokens: list[str | None] | None, as_list: bool = False):
	"""Header tokens -> {col: index} schema, or the tokens themselves when as_list is set.

	A header of None means the line was blank or a comment, so there was no
	header row to take a schema from."""
	if header_tokens is None:
		raise csv_err.ParseError("expected header row")
	schema = {}
	for i, key in enumerate(header_tokens):
		if key is None:
			raise csv_err.SchemaError("empty column name at index %d" % i)
		schema[key] = i
	if as_list:
		return header_tokens
	return schema

def reschema_from(tokens: list[str | None]):
	"""A __reschema__ row -> the schema it declares, replacing the one in force."""
	new_schema = normalize_schema(tokens[1:])
	if not new_schema:
		raise csv_err.ReschemaError("empty reschema row")
	return new_schema

def row_to_entry(tokens: list[str | None] | None, schema: list[str] | dict[str, int], allow_unfinished: bool = False):
	"""Tokens -> {col: value}, rejecting a row whose field count the schema does not allow."""
	if tokens is None:
		raise csv_err.ParseError("expected a data row")
	schema_dict = normalize_schema(schema)
	if not allow_unfinished and len(tokens) != len(schema_dict):
		raise csv_err.SchemaError("field count mismatch: expected %d, got %d" % (len(schema_dict), len(tokens)))
	data = {}
	for key, idx in schema_dict.items():
		data[key] = tokens[idx] if idx < len(tokens) else None
	return data

def entry_to_tokens(entry: dict[str, str | None], schema: list[str] | dict[str, int], allow_unfinished: bool = False):
	"""{col: value} -> positional tokens, rejecting a key the schema does not have."""
	schema_dict = normalize_schema(schema)
	tokens = [None] * len(schema_dict)
	for key, value in entry.items():
		if key not in schema_dict:
			raise csv_err.SchemaError("unknown key: %s" % key)
		tokens[schema_dict[key]] = value
	if not allow_unfinished:
		for key, idx in schema_dict.items():
			if tokens[idx] is None:
				raise csv_err.SchemaError("missing value for key: %s" % key)
	return tokens
