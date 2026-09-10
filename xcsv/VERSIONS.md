# XCSV version history

## 1_1_0 (minor)

Major feature release adding read API and schema improvements:

- **Exception hierarchy**: CSVError, ParseError, SchemaError, UnfinishedLineError, IOError, ReschemaError
- **raise_errors parameter**: All public functions accept optional `raise_errors=False`. When True, raises exceptions instead of returning (result, error) tuples.
- **schema_parse(as_list)**: New parameter; as_list=False (default) returns dict {col: index}, as_list=True returns list [col1, col2...]
- **Dual schema support**: parse_line, parse_all, write_entry, write_entries accept both list [col1, col2...] and dict {col: index} schemas (dict deprecated, removed in v2_0_0)
- **allow_unfinished parameter**: parse_line, parse_all, write_entry, write_entries accept allow_unfinished=False to allow missing fields
- **Stage 1 (line-based) API**: read_line, read_all, write_line (tokens list), write_all
- **Stage 2 (schema-aware) API**: parse_all, write_entries
- **Reschema support**: parse_all(reschema=True) handles __reschema__ rows; raises ReschemaError by default
- **Internal helper**: _normalize_schema converts list → dict
- Tokenizer handles \r\n, \n, \r line endings

## 1_0_1 (revision)

Fixes a release bug: the bundled file renamed the public `write_line` and `write_entry`
functions to `csv_file_write_line` / `csv_file_write_entry`, so they could not be called
under their documented names, and `csv_file_write_line` called the internal `serialize`
unprefixed, which raised a `NameError` at runtime.

The library was restructured so the public API (tokenize, serialize, schema_parse,
parse_line, write_line, write_entry) lives entirely in `csv.py`, with internal helpers
in `csv_tok.py` and `csv_ser.py`. This gives the bundler clean names to keep and room
for docstrings. The underlying cause was a pybundle `base_of` bug (now fixed) plus the
older library layout re-exporting internal names.

Note: as a one-time exception to the rule of not touching existing `xlib/` releases,
double blank lines in this file (and in `1_0_0`) were collapsed to fix a linter flag.
This was cosmetic only, with no version bump and no change in behavior.

## 1_0_0

Initial release of the CSV library.

Public API: tokenize, serialize, schema_parse, parse_line, write_line, write_entry.
All functions return a `(result, error)` pair. Supports standard CSV quoting, `//`
comments, and empty fields. First release was tagged with a bundler bug (see 1_0_1).