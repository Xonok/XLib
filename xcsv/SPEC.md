# xcsv Spec

## Overview

**xcsv** is a CSV library with `//` comment support, quoting, and a simple tokenizer/serializer. Current release (1_0_1) is write-only: `write_line`, `write_entry`, `serialize`, `tokenize`, `schema_parse`, `parse_line`. The next version adds a reader layer for append-only log databases (logdb).

**Design principle**: header-ignoring is the default; header-aware reads/writes are a layer on top.

**Schema representation**: A **list of header names** `["col1", "col2", ...]`. Position in list = column index. (Dict form `{col: index}` is internal only, for fast lookup.) **v1_1_0 accepts both list and dict** (dual support); **v2_0_0 drops dict**.

## Current Write API (released, v1_0_1)

| Function | Role |
|----------|------|
| `tokenize(line)` | Split line (handles `//` comments, quoting, escaped quotes) → `(tokens, error)` |
| `serialize(*args)` | Join values into quoted CSV line → `(line, error)` |
| `schema_parse(header)` | Header row → `{col: index}` schema dict |
| `parse_line(line, schema)` | Data row + schema dict → `{col: value}` dict |
| `write_line(path, *data)` | Append serialized line to file |
| `write_entry(path, schema, **data)` | Append entry matching schema to file |

All return `(result, error)` tuples. Internals: `csv_tok.py` (tokenizer), `csv_ser.py` (serializer).

**v1_1_0 dual-support note**: `parse_line`, `write_entry`, `schema_parse` accept both **list** (preferred) and **dict** (deprecated). Internal helper `_normalize_schema(schema)` converts list → dict.

## Error Model & Schema Migration (v1_1_0 → v2 → v3)

**v1_1_0 (minor)**: Add optional `raise_errors=False` parameter to all public functions. When `True`, raises specific exceptions instead of returning `(result, error)`. **Add `as_list=False` to `schema_parse`** (default `False` = returns dict; `True` = returns list). **`parse_line`, `write_entry`, `parse_all`, `write_entries` accept both dict and list schema** (dict deprecated).

**v2_0_0 (major)**: `raise_errors=True` becomes default. Tuple return still works but deprecated. **Dict schema support removed** — only list accepted.

**v3_0_0 (major)**: Tuple return removed; exceptions only. List schema only.

Exception hierarchy:
```python
class CSVError(Exception): pass
class ParseError(CSVError): pass          # tokenize/parse failure
class SchemaError(CSVError): pass         # schema mismatch, unknown key, wrong field count
class UnfinishedLineError(CSVError): pass # fewer fields than schema (unless allow_unfinished)
class IOError(CSVError): pass             # file read/write failure
class ReschemaError(CSVError): pass       # malformed reschema row
```
Each carries context (line number, column, raw line). Writer functions also get `raise_errors` for consistency.

**Internal helper** (not public):
```python
def _normalize_schema(schema):
    """Accept list [col1, col2...] or dict {col: index} → return dict."""
    if isinstance(schema, list):
        return {col: i for i, col in enumerate(schema)}
    return schema
```

## Staged API Design

### Stage 1 — Line-based (no schema awareness)

Basic CSV I/O. Tokens = `[val, None, val...]` (`None` for empty fields). Comments (`//`) skipped by default.

```python
def read_line(path: str, offset: int = 0, discard_comments: bool = True, raise_errors: bool = False):
    """Read one line from byte offset. Returns (tokens, next_offset). Comments return (None, next_offset) if not discarded."""
    ...

def read_all(path: str, discard_comments: bool = True, raise_errors: bool = False):
    """Read entire file. Returns [(tokens, line_start, line_end), ...]. Header is just first entry."""
    ...

def write_line(path: str, tokens: list, raise_errors: bool = False):
    """Append one line (list of values/None) to file."""
    ...

def write_all(path: str, lines: list[list], raise_errors: bool = False):
    """Append multiple lines to file."""
    ...
```

### Stage 2 — Schema-based (header-aware, no reschema)

Schema = **list of header names** (preferred) or **dict {col: index}** (deprecated, v1_1_0 only). `parse_*` functions validate field count; `write_entry` validates keys against schema. `schema_parse` gets `as_list=False` parameter.

```python
def schema_parse(header: str, as_list: bool = False, raise_errors: bool = False):
    """Header row → schema. as_list=False (default) returns {col: index} dict. as_list=True returns [col1, col2...] list."""
    ...

def parse_line(line: str, schema: list[str] | dict, allow_unfinished: bool = False, raise_errors: bool = False):
    """Parse one line against schema. Returns {col: value}. Raises SchemaError if field count mismatch (unless allow_unfinished). Accepts list or dict schema."""
    ...

def parse_all(path: str, schema: list[str] | dict, allow_unfinished: bool = False, raise_errors: bool = False, reschema: bool = False):
    """Read all lines, parse each against schema. Returns [entry_dict, ...]. Comments skipped. By default (reschema=False), reschema rows raise ReschemaError. If reschema=True, handles reschema rows and updates schema. Accepts list or dict schema."""
    ...

def write_entry(path: str, schema: list[str] | dict, raise_errors: bool = False, allow_unfinished: bool = False, **data):
    """Write one entry. Validates all keys in schema. If allow_unfinished, missing keys become empty fields. Accepts list or dict schema."""
    ...

def write_entries(path: str, schema: list[str] | dict, entries: list[dict], raise_errors: bool = False, allow_unfinished: bool = False):
    """Write multiple entries. Accepts list or dict schema."""
    ...
```

**Stage mixing behavior**: Stage 1 ignores `__reschema__` rows — not aware of reschema, treats them as ordinary data rows (does not skip). Stage 2 raises `ReschemaError` on them by default; `parse_all(reschema=False)` option enables reschema handling. Stage 3 handles them.

### Stage 3 — Parser/Writer objects (reschema + tail-follow)

Requires exclusive process ownership of the file. Process tracks previous header location for reschema.

```python
def file_reader(path: str, schema: list[str] = None, allow_unfinished: bool = False):
    """
    Returns a parser object (keeps file open):
    - `next()` → entry_dict (blocks until new line available)
    - `schema` property → current schema (updates on reschema)
    - Handles reschema rows (__reschema__,col1,col2,...) — updates internal schema
    - No schema pointers; reschema works by tracking previous header position in memory
    """
    ...

def file_writer(path: str, schema: list[str], allow_unfinished: bool = False):
    """
    Returns a writer object (keeps file open in append mode, exclusive):
    - `write(entry_dict)`
    - `reschema(new_schema: list[str])` — writes __reschema__ row, replaces schema entirely (previous schema dropped)
    - Writer tracks previous header position for potential future use
    """
    ...

def file_writer_open(path: str, initial_schema: list[str] = None):
    """
    Combined workflow: read existing file fully (via file_reader), then transition to writer.
    Returns (entries_so_far, writer_object). Schema handling: if file has reschema rows,
    the reader's final schema becomes the writer's schema.
    """
    ...
```

## Reschema (Stage 3 only; Stage 2 opt-in)

A data row with first column `__reschema__` signals schema change:
```
task_id,title,status
1,"Task 1","pending"
__reschema__,task_id,title,status,priority
2,"Task 2","pending","high"
```
**No pointers** — the writer tracks the previous header's file position in memory. `reschema(new_schema)` writes the `__reschema__` row and **replaces the schema entirely** (previous schema dropped). If the process crashes before a reschema row is fully written, that reschema didn't happen (append-only atomicity per line). Writer raises `IOError` on partial write; caller decides recovery.

Stage 1: treats `__reschema__` as ordinary data row (tokens).
Stage 2: raises `ReschemaError` on `__reschema__` row by default; `parse_all(reschema=True)` enables handling.
Stage 3: handles reschema, updates internal schema, continues.

Version/timestamp metadata are logdb concerns, not CSV.

## Comments & Line endings

- `read_line`: `discard_comments=True` default; if `False`, comments return `(None, next_offset)`
- `parse_*`, Stage 2/3: comments always skipped
- Tokenizer handles `\n`, `\r\n`, `\r`. Writer outputs `\n`.

## KV mode — DROPPED

Not a CSV concern. User-level patterns achieve the same:
- Web messages: omit unused columns entirely
- Empty fields = no-op (don't overwrite existing data) — user guideline
- Special marker for explicit clear — user/logdb concern

## Roadmap

| Step | Version | Scope |
|------|---------|-------|
| 1 | 1_1_0 (minor) | Stage 1: `read_line`, `read_all`, `write_line_tokens`, `write_all` + `raise_errors` opt-in |
| 2 | 1_1_0 (same) | Stage 2: `parse_line`, `parse_all`, `write_entry`, `write_entries`, `schema_parse(as_list)` — **dual dict/list support** + `allow_unfinished` |
| 3 | 2_0_0 (major) | Dict schema support removed; list-only; `raise_errors=True` default |
| 4 | 1_2_0 / 2_0_0 | Stage 3: `file_reader`, `file_writer`, `file_writer_open` with reschema, tail-follow |

## Out of scope for v1_1_0

- Folding (logdb)
- Reschema handling (Stage 3)
- KV mode (dropped)
- Indices, random access by line number (logdb)
- Automatic encoding detection (assume UTF-8)
- Concurrent writer support (exclusive ownership assumed)