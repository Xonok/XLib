# CSV version history

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
