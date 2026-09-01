# CSV library

CSV with comment support. Usable standalone and over HTTP (denser than JSON for tabular data).

## Goal

A tokenizer/serializer that understands quotes and comments, with schema-aware parse (header row → dict records), building on `xlib_legacy/CSV.py`'s approach.

## Design direction

- `xlib_legacy/CSV.py` is prior art: tokenizer with `"` quoting, `None` for empty cells, schema header parse, serialize, write helpers. Redo it cleanly; it has no comments and some parsing edge cases to fix.
- Comments: lines starting with a comment char (configurable, e.g. `#`) are ignored on read and skippable on write. Useful for logs and for embedding descriptions.
- Quoting rules refined: escaped quotes, embedded commas/newlines.
- Typed output: cells come back as strings today; pairing with typechecking lets read apply types, and serialization can take typed values.
- HTTP relevance: a "to_csv" path from records/dicts for dense API responses.

## Consumers

- logdb (storage format)
- command-runner / server (dense responses)
- typechecking integration for typed rows

## Order

Phase 1 item 4.

## Open questions

- Support multiline quoted fields or strictly line-based? (Line-based keeps the "log is human-readable" property — lean that way.)
- Comment lines inside quoted rows (must be data, not comments — decide semantics).