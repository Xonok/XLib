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

This file is the public interface and nothing else: the implementation lives in
`_/`, as csv_tok (the tokenizer), csv_ser (the serializer), csv_schema (schema
mapping), csv_io (file IO) and csv_err (the exception hierarchy, bound here
under the names this library publishes). Every function below hands one call
into `_deliver`, which is the whole of the raise_errors policy.

Exception hierarchy: CSVError is the base. ParseError is a tokenize or parse
failure; SchemaError a schema mismatch, an unknown key or a wrong field count;
UnfinishedLineError fewer fields than the schema, unless allow_unfinished is
set; IOError a file read or write failure; ReschemaError a malformed reschema
row.
"""
from ._ import csv_err,csv_io,csv_schema,csv_ser,csv_tok

CSVError = csv_err.CSVError
ParseError = csv_err.ParseError
SchemaError = csv_err.SchemaError
UnfinishedLineError = csv_err.UnfinishedLineError
IOError = csv_err.IOError
ReschemaError = csv_err.ReschemaError

def _deliver(fn, raise_errors: bool, *args):
	"""Run one internal call and answer with the public (result, error) pair.

	An internal signals failure by raising a csv_err exception; this is the one
	place that decides whether the caller sees it raised or as the error half.
	The internals know nothing about raise_errors."""
	try:
		return fn(*args), None
	except csv_err.CSVError as error:
		if raise_errors:
			raise
		return None, str(error)

#Primitives: the tokenizer and the serializer.
def tokenize(line: str, raise_errors: bool = False):
	"""Split a CSV line (with // comments and quoting) into cells.
	Returns (tokens, error) where tokens is list[str] | None."""
	return _deliver(csv_tok.tokenize, raise_errors, line)

def serialize(*args: str | None, raise_errors: bool = False):
	"""Join values into one CSV line with standard quoting.
	Returns (line, error) where line is str. The serializer has no failure mode,
	so the error half is always None."""
	return csv_ser.serialize(*args), None

#Stage 1 — line-based: no schema awareness, comments discarded unless asked otherwise.
#read_line already answers with a pair on success, so it cannot hand a call into _deliver.
def read_line(path: str, offset: int = 0, discard_comments: bool = True, raise_errors: bool = False):
	"""Read one line from byte offset. Returns (tokens, next_offset). Comments return (None, next_offset) if not discarded.
	Returns (tokens, next_offset) where tokens is list[str] | None, next_offset is int."""
	try:
		return csv_io.read_line(path, offset, discard_comments)
	except csv_err.CSVError as error:
		if raise_errors:
			raise
		return None, str(error)

def read_all(path: str, discard_comments: bool = True, raise_errors: bool = False):
	"""Read entire file. Returns [(tokens, line_start, line_end), ...]. Header is just first entry.
	Returns (results, error) where results is list[tuple[list[str], int, int]]."""
	return _deliver(csv_io.read_all, raise_errors, path, discard_comments)

def write_line(path: str, *data: str | None, raise_errors: bool = False):
	"""Append serialized line to file.
	Returns (line, error) where line is str."""
	return _deliver(csv_io.append_line, raise_errors, path, *data)

def write_line_tokens(path: str, tokens: list[str | None], raise_errors: bool = False):
	"""Append one line (list of values/None) to file.
	Returns (None, error) where error is str | None."""
	_, error = _deliver(csv_io.append_line, raise_errors, path, *tokens)
	return None, error

def write_all(path: str, lines: list[list[str | None]], raise_errors: bool = False):
	"""Append multiple lines to file. Returns count of lines written on success.
	Returns (count, error) where count is int."""
	return _deliver(csv_io.append_lines, raise_errors, path, lines)

#Stage 2 — schema-based: header-aware, reschema only where it is opted into.
def schema_parse(header: str, as_list: bool = False, raise_errors: bool = False):
	"""Header row → schema. as_list=False (default) returns {col: index} dict. as_list=True returns [col1, col2...] list.
	Returns (schema, error) where schema is dict[str, int] | list[str]."""
	return _deliver(lambda: csv_schema.schema_from(csv_tok.tokenize(header), as_list), raise_errors)

def parse_line(line: str, schema: list[str] | dict[str, int], allow_unfinished: bool = False, raise_errors: bool = False):
	"""Parse one line against schema. Returns {col: value}. Raises SchemaError if field count mismatch (unless allow_unfinished). Accepts list or dict schema.
	Returns (data, error) where data is dict[str, str | None]."""
	return _deliver(lambda: csv_schema.row_to_entry(csv_tok.tokenize(line), schema, allow_unfinished), raise_errors)

def parse_all(path: str, schema: list[str] | dict[str, int], allow_unfinished: bool = False, raise_errors: bool = False, reschema: bool = False):
	"""Read all lines, parse each against schema. Returns [entry_dict, ...]. Comments skipped. By default (reschema=False), reschema rows raise ReschemaError. If reschema=True, handles reschema rows and updates schema. Accepts list or dict schema.

	WARNING: When reschema=True and a __reschema__ row is encountered, the schema is updated for subsequent rows. The returned list contains entries with DIFFERENT schemas (earlier entries use old schema, later entries use new schema). Callers must handle this if they need schema consistency.
	Returns (results, error) where results is list[dict[str, str | None]]."""
	return _deliver(csv_io.parse_all, raise_errors, path, schema, allow_unfinished, reschema)

def write_entry(path: str, schema: list[str] | dict[str, int], raise_errors: bool = False, allow_unfinished: bool = False, **data: str | None):
	"""Write one entry. Validates all keys in schema. If allow_unfinished, missing keys become empty fields. Accepts list or dict schema.
	Returns (line, error) where line is str."""
	def append():
		tokens = csv_schema.entry_to_tokens(data, schema, allow_unfinished)
		return csv_io.append_line(path, *tokens)
	return _deliver(append, raise_errors)

def write_entries(path: str, schema: list[str] | dict[str, int], entries: list[dict[str, str | None]], raise_errors: bool = False, allow_unfinished: bool = False):
	"""Write multiple entries. Accepts list or dict schema. Returns count of entries written on success.
	Returns (count, error) where count is int."""
	return _deliver(csv_io.write_entries, raise_errors, path, schema, entries, allow_unfinished)
