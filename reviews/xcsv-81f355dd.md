# xcsv Code Review

**Date:** 2026-09-10  
**Content Hash:** 81f355dd (xcsv/ dev folder)  
**Reviewed:** `xcsv/` dev folder (intended for v1.1.0 minor release)  
**Compared against:** SPEC.md (v1.1.0), style/common.md, style/python.md, released v1.0.1

---

## Summary

The dev version implements **Stage 1 (line-based)** and **Stage 2 (schema-aware)** APIs as specified for v1.1.0. The feature set is complete and matches the SPEC. However, there are **critical structural issues** that will prevent the library from working when released, plus a few correctness bugs and style deviations.

**Verdict: Not ready for release. Fix the module structure first.**

---

## Critical Issues (Blockers)

### 1. Broken Module Structure — Bundler Doesn't Support `_` Folder Convention

**Files:** `xcsv/xcsv.py` (lines 31-32), `xcsv/_/csv_tok.py`, `xcsv/_/csv_ser.py`, `pybundle/bundler_impl.py`

The internal modules correctly live in `xcsv/_/` (per the project's internal convention), and the entry point uses:
```python
from ._.csv_tok import tokenize as _tokenize
from ._.csv_ser import serialize as _serialize
```

However, the bundler's `_locate` function (`pybundle/bundler_impl.py:115`) requires `__init__.py` to recognize a folder as a package. Since `xcsv/_/` lacks `__init__.py` (and AGENTS.md forbids `__init__.py` in dev folders), the import fails to resolve. The bundler emits the broken relative import verbatim in the output.

**Evidence:** Running the bundler on `xcsv/xcsv.py` produces output containing `from ._.csv_tok import ...` which fails at runtime.

**Fix:** The bundler needs to treat `_` as a special internal folder that doesn't require `__init__.py`. Either:
- Add special-case handling in `_locate` for `_` segments, or
- Inline `_` modules directly when encountered (they're private to the library anyway)

This is a bundler bug, not an xcsv structure bug — the `_` folder convention is correct.

---

### 2. Bundler Doesn't Produce Standalone Release

**Root cause:** Issue #1. The bundler resolves imports by looking for `__init__.py` in subdirectories (`pybundle/bundler_impl.py:_locate`). Since `xcsv/_/` lacks `__init__.py`, the import fails to resolve and is emitted as-is.

**Result:** A released `xcsv_1_1_0.py` would be non-functional.

---

## Correctness Bugs

### 3. Serializer Doesn't Quote Carriage Return (`\r`)

**File:** `xcsv/_/csv_ser.py` line 8

```python
if "," in s or '"' in s or "\n" in s:
```

**Missing:** `"\r" in s`. The tokenizer correctly handles `\r\n`, `\r`, and `\n` line endings (SPEC §Comments & Line endings), but the serializer only quotes `\n`. A field containing `\r` will be written unquoted and break round-trip parsing.

**Test evidence:**
```python
serialize('a\rb', 'c')  # -> 'a\rb,c\n'  (unquoted \r)
```

**Fix:** Add `"\r" in s` to the condition.

---

### 4. `parse_all` Returns Mixed-Schema Results Silently

**File:** `xcsv/xcsv.py` lines 244-296

When `reschema=True` and a `__reschema__` row is encountered, the local `schema_dict` is updated, but the function returns a flat list of dicts where **earlier entries use the old schema, later entries use the new schema**. Callers get no indication that the schema changed mid-stream.

**SPEC §Stage 2** documents this behavior but it's a footgun. Consider returning `(results, final_schema, reschema_positions)` or at minimum documenting the behavior prominently in the docstring.

---

### 5. `write_line` Returns `(None, None)` on Success

**File:** `xcsv/xcsv.py` line 134

```python
return None, None
```

All other public functions return `(result, error)` where `result` is meaningful. `write_line` returns `None` for success. The SPEC says "Returns (None, error)" for write functions, but this is inconsistent with the `(result, error)` convention used elsewhere. At minimum, return `(True, None)` or the written line.

---

### 6. Comment Detection Triggers on `//` Anywhere (Outside Quotes)

**File:** `xcsv/_/csv_tok.py` line 25 (in the old v1.0.x tokenizer; current `csv_tok.py` uses line-start-only logic at line 12-14)

Wait — the current `xcsv/_/csv_tok.py` (lines 11-14) correctly checks for comments only at line start after stripping whitespace:
```python
stripped = line.lstrip()
if stripped.startswith("//"):
    return None, None
```

But the released v1.0.1 (`xlib/xcsv_1_0_1.py` lines 10-22) has the buggy behavior:
```python
if line.strip().startswith("//"):  # triggers on "a//comment,b"
```

And the v1.0.1 tokenizer loop (lines 13-20) scans for `//` anywhere outside quotes.

**Current dev version is correct** (line-start only). The released versions have the bug. This is a **release regression** — the dev version fixed it.

---

## Style & Convention Issues

### 7. AGENTS.md Documents Old Convention (`csv/csv/` vs `_`)

**AGENTS.md line 102:** "Internal modules go in a subfolder (e.g., `csv/csv/`)..." but the actual convention used in xcsv is `_/`. The AGENTS.md should be updated to match the `_` convention.

---

### 8. Missing Type Hints on Public API

**SPEC.md** shows type hints in all function signatures (e.g., `def read_line(path: str, offset: int = 0, ...)`). The implementation has none.

**style/python.md:** "Annotate where the name doesn't carry the type or the contract is non-obvious." Function signatures like `parse_all(path, schema, allow_unfinished=False, raise_errors=False, reschema=False)` have non-obvious contracts — type hints would help.

---

### 9. No Module Docstring

**File:** `xcsv/xcsv.py`

No module-level docstring describing the library, its stages, or the exception hierarchy. The SPEC has this information but it's not in the code.

---

### 10. `write_line_tokens` Naming Inconsistency

**SPEC §Stage 1:** `write_line(path, tokens)` — takes a token list.  
**Implementation:** Has both `write_line(path, *data)` (serialize + write) and `write_line_tokens(path, tokens)` (write token list directly).

Not wrong, but the dual naming is confusing. Consider aligning with SPEC: rename `write_line` to `write_line_data` or similar, and `write_line_tokens` to `write_line`.

---

## Positive Findings

- ✅ Feature-complete for v1.1.0 (Stage 1 + Stage 2 per SPEC)
- ✅ Exception hierarchy well-designed and matches SPEC
- ✅ `raise_errors` parameter consistently implemented on all public functions
- ✅ Dual schema support (list/dict) via `_normalize_schema`
- ✅ `allow_unfinished` parameter works correctly
- ✅ Reschema support in `parse_all` implemented
- ✅ Tokenizer correctly handles quotes, escaped quotes, comments, and all line endings (`\n`, `\r\n`, `\r`)
- ✅ Current dev tokenizer correctly restricts comments to line-start (unlike released versions)
- ✅ No `xlint` violations
- ✅ Clean separation of tokenizer (`csv_tok.py`) and serializer (`csv_ser.py`)
- ✅ VERSIONS.md correctly documents planned v1.1.0 changes

---

## Recommendations

### Must Fix Before Release
1. **Fix bundler to support `_` folder** — add special handling in `_locate` for `_` segments so internal modules inline correctly (fixes Issues #1, #2)
2. **Fix serializer** to quote `\r` (Issue #3)
3. **Document `parse_all` mixed-schema behavior** prominently (Issue #4)

### Should Fix
4. **Fix `write_line` return value** for consistency (Issue #5)
5. **Add type hints** to public API (Issue #8)
6. **Add module docstring** (Issue #9)
7. **Update AGENTS.md** to document `_` convention (Issue #7)

### Nice to Have
8. **Align `write_line`/`write_line_tokens` naming** with SPEC (Issue #10)

---

## Test Coverage Gap

**No tests exist for xcsv.** The repo has tests for `xschema`, `pybundle`, `xconf`, `xtest` but not `xcsv`. Given the tokenizer/serializer complexity and the schema migration path (v1→v2→v3), tests are essential before release.

The existing test file `xcsv/tests/test_xcsv.py` is minimal (106 lines) and covers:
- Basic tokenize/serialize
- Schema parsing
- Parse line with schema
- File read/write basics

**Missing coverage for:**
- `\r` quoting round-trip
- Comment edge cases (line-start vs inline)
- `parse_all` with `reschema=True`
- `write_entry`/`write_entries`
- `allow_unfinished` in `parse_all`

---

## Next Steps

1. Fix bundler (`pybundle/bundler_impl.py:_locate`) to recognize `_` as a valid internal folder without `__init__.py`
2. Fix the `\r` quoting bug in `xcsv/_/csv_ser.py`
3. Add type hints and module docstring to `xcsv/xcsv.py`
4. Fix `write_line` return value
5. Write comprehensive tests for tokenizer, serializer, and schema functions
6. Run bundler to verify standalone release works
7. Update AGENTS.md line 102 to document `_` convention
8. Release as v1.1.0 (minor bump per VERSIONS.md)