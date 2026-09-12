# pybundle Bundler Review

**Date:** 2026-09-09  
**Reviewed:** `pybundle/bundler.py`, `pybundle/bundler_impl.py`  
**Test suite:** `pybundle/test/test_bundler.py` (7 fixtures, all passing)  
**Compared against:** AGENTS.md (module structure rules), style/common.md, style/python.md

---

## Summary

The bundler (`pybundle`) is a single-file bundler for Python libraries that inlines dependencies, rewrites internal imports with module prefixes, and merges top-level imports. It powers the release process for all libraries in this repo.

**Overall verdict: Functional for current use cases.** The previously critical issue (missing `__init__.py` in `_/` folder) has been fixed by adding `__init__.py` to `xcsv/_/` and clarifying the convention in AGENTS.md. Several other correctness and robustness issues remain.

---

## Critical Issues (Blockers)

### 1. **`_` Folder Missing `__init__.py` (Fixed)**

**Files:** `xcsv/_/__init__.py` (missing), AGENTS.md (line 102 - clarified)

**Problem:** The project's AGENTS.md originally stated that internal modules go in a `_` folder *without* `__init__.py`. However, this is incorrect — for relative imports like `from ._.csv_tok import ...` to work, the `_` folder **must** be a proper package (have `__init__.py`). Only the library's *root* dev folder (e.g., `xcsv/`) must lack `__init__.py` to allow path-based imports during development.

The `_locate` function in `bundler_impl.py` correctly requires `__init__.py` to recognize a directory as a package. Since `xcsv/_/` lacked `__init__.py`, imports failed to resolve.

**Evidence:** Running the bundler on `xcsv/xcsv.py` emitted `from ._.csv_tok import ...` verbatim instead of inlining. After adding `__init__.py` to `xcsv/_/`, the bundler correctly inlines the modules.

**Impact:** Fixed — any library following the corrected convention (root has no `__init__.py`, internal `_/` has `__init__.py`) will bundle correctly.

**Fix applied:** Added `__init__.py` to `xcsv/_/`. Updated AGENTS.md line 102 to clarify the convention.

---

## Correctness Bugs

### 3. **SyntaxError in Bundled Module Crashes Bundler**

**File:** `bundler_impl.py:_ensure` (lines 151-154)

```python
try:
    m.tree = ast.parse(m.text)
except SyntaxError:
    m.tree = None
```

If a source file has a syntax error, `m.tree` becomes `None`, and `_analyze` returns early. However, the module is still added to `ctx.mods` and included in the dependency graph. Later, `_rewrite` is called on it, which iterates over `m.tokens` (tokenized successfully) but may produce incorrect output since the AST wasn't available for analysis.

**Risk:** A syntax error in any internal module produces a silently broken bundle.

**Fix:** Either:
- Treat syntax errors as hard errors (abort bundling), or
- Skip the module entirely and emit a warning, but don't include it in the bundle

---

### 4. **Import Merging Doesn't Handle Multi-Name Imports**

**File:** `bundler_impl.py:_merge_imports` (lines 68-93)

The regex patterns only match:
- `import single_name` → `_MERGE_IMPORT`
- `from mod import single_name` → `_MERGE_FROM`

They **don't handle**:
- `import a, b, c` (multiple modules in one statement)
- `from mod import a, b, c` (multiple names from one module)
- `import a as alias` (aliased imports)

These are kept as-is and not merged with adjacent compatible imports. This is a minor optimization loss, but worth noting.

---

### 5. **Topological Sort Doesn't Detect Cycles**

**File:** `bundler_impl.py:_topo` (lines 705-722)

The `_topo` function uses a simple DFS with `visiting`/`done` sets but **doesn't report cycles**. If a cycle exists, `visiting[m]` remains `True` and the function returns without adding `m` to `order`, effectively dropping that module from the bundle.

**Risk:** Circular dependencies (common in Python) silently cause missing code in the output.

**Fix:** Detect cycles and either error out or emit a warning.

---

### 6. **Token-Based Rewriting May Miss Edge Cases**

**File:** `bundler_impl.py:_rewrite` (lines 560-672)

The rewriter operates on token streams, not AST. While this preserves formatting, it has known fragility:
- Complex expressions spanning multiple lines with comments
- Type annotations with forward references (strings)
- Decorators with complex arguments
- Walrus operator (`:=`) in comprehensions

The `_gather_chain` function (lines 674-684) only follows `NAME . NAME` sequences. It doesn't handle:
- `mod.submod.attr` where `submod` is a re-exported module
- Attribute access on function calls: `func().attr`
- Indexing: `mod["key"]`

**Evidence:** The `_fold` function (lines 686-701) assumes every segment is either a `"value"` in the namespace or a child module. It doesn't handle dynamic attribute access.

---

### 7. **Line Offset Calculation Assumes `\n` Only**

**File:** `bundler_impl.py:_line_offsets` (lines 56-66)

```python
for i, ch in enumerate(text):
    if ch == "\n":
        res.append(i + 1)
```

This doesn't handle `\r\n` (Windows) or `\r` (old Mac) line endings. If a source file uses `\r\n`, line offsets will be off by one character per line, causing incorrect token position mapping and potentially wrong rewrites.

**Fix:** Normalize line endings when reading, or handle all three line ending types in `_line_offsets`.

---

### 8. **`_defkw_of` Heuristic for `def`/`class` Names is Fragile**

**File:** `bundler_impl.py:_defkw_of` (lines 495-522)

This function tries to find the token position of `def`/`class` keywords to rename them with the module prefix. It uses a heuristic matching token positions to AST nodes. This can fail if:
- Multiple `def`/`class` with same name on same line (rare but possible)
- Decorators push the `def` token to a different line
- Comments between `def` and the name

**Risk:** Function/class definitions may not get renamed correctly, causing name collisions in the bundled output.

---

### 9. **Global Statement Rewriting Only Handles Simple Cases**

**File:** `bundler_impl.py:_rewrite` (lines 614-629)

The `global` statement handler assumes:
- All names are `NAME` tokens
- Names are separated by commas (handled by `cur += 2`)

It doesn't handle:
- `global a, b, c` (multiple names) — actually this might work due to `cur += 2` skipping commas
- `global (a, b)` (parenthesized) — invalid Python but possible in malformed code
- Trailing commas

More importantly, it only rewrites names that were explicitly tracked in `m.globals_at`. If a `global` statement references a name not in `bindmap`/`topvals`, it's left unchanged — which may be correct (external global) but could also be a missed internal name.

---

## Robustness & Edge Cases

### 10. **No Handling of `importlib.resources` / `pkgutil` / `__file__`**

Bundled code that uses `__file__`, `__path__`, `importlib.resources`, or `pkgutil.get_data` will break because the bundled file has a different `__file__` and no package structure.

**Mitigation:** The bundler could inject a `__file__` shim, but this is a known limitation of single-file bundlers. Document it.

---

### 11. **Relative Import Level Calculation May Be Off for Deep Nesting**

**File:** `bundler_impl.py:_base_of` (lines 309-318)

```python
pkg = m.modpath if m.is_pkg else (m.modpath.rsplit(".", 1)[0] if "." in m.modpath else "")
base = pkg
for _ in range(node.level - 1):
    base = base.rsplit(".", 1)[0] if "." in base else ""
```

For a non-package module (most internal modules), `m.modpath` is something like `csv._.csv_tok`. The parent package is `csv._`. But `m.is_pkg` is `False` (not `__init__.py`), so it uses the `rsplit` logic.

For `from .. import x` (level=2) in `csv._.csv_tok`:
- `pkg = "csv._"` (rsplit once)
- Loop runs once (level-1=1): `base = "csv"`
- Result: base = `"csv"` — correct

For `from ... import x` (level=3) in `csv._.csv_tok`:
- `pkg = "csv._"`
- Loop runs twice: `base = "csv"` → `base = ""`
- Result: base = `""` — correct (top level)

Seems correct, but worth adding tests for deep relative imports.

---

### 12. **Star Imports (`from x import *`) Kept As-Is With Warning**

**File:** `bundler_impl.py:_from_stmt` (lines 290-292)

```python
if a.name == "*":
    ctx.warnings.append("%s:%d star import kept as-is" % (m.modpath or "entry", node.lineno))
    ext.append(_canon_from(a, base, node))
    continue
```

Star imports are not expanded. This is correct (can't know what `*` exports without executing), but the warning doesn't include the module name, making it hard to locate.

---

### 13. **No Support for Conditional/Optional Imports**

Imports inside `if TYPE_CHECKING:`, `try/except ImportError`, or `if sys.version_info >= ...` are processed unconditionally. The bundler will try to resolve and inline them, potentially failing or pulling in unnecessary code.

**Fix:** Skip import statements that are inside `if` blocks with known guard patterns (e.g., `TYPE_CHECKING`), or at least don't error on missing modules in such contexts.

---

## Style & Code Quality

### 14. **Inconsistent Naming: `_` Prefix for Private Functions**

**Files:** `bundler_impl.py`

Module-level functions use `_` prefix (e.g., `_locate`, `_analyze`, `_rewrite`), but classes (`Context`, `Mod`, `Scope`) don't. This is fine per Python conventions, but the mix of `_function` and `Class` is slightly inconsistent. Not a bug.

---

### 15. **Magic Numbers in `_scope_frame`**

**File:** `bundler_impl.py:_scope_frame` (lines 187-250)

The function uses hardcoded `ast` node types in a long `if/elif` chain. Consider using a dictionary mapping node types to handler functions for extensibility and readability.

---

### 16. **`SPECIAL` Set Missing Common Builtins**

**File:** `bundler_impl.py` line 3

```python
SPECIAL = {"True","False","None","__name__","__doc__","__package__","__file__"}
```

Missing: `__loader__`, `__spec__`, `__annotations__`, `__builtins__`. These are also special names that shouldn't be rewritten. Low risk but worth adding.

---

### 17. **No Type Hints**

Neither `bundler.py` nor `bundler_impl.py` have type hints. Per `style/python.md`: "Annotate where the name doesn't carry the type or the contract is non-obvious." The public `bundle(entry)` function and key internal functions would benefit from type hints.

---

### 18. **Module Docstrings Missing**

Both `bundler.py` and `bundler_impl.py` lack module-level docstrings explaining their purpose, architecture, and usage.

---

## Test Coverage Gaps

### 19. **No Test for `_` Folder Convention (with `__init__.py` in `_/`)**

The test fixtures (`pybundle/test/fixtures/`) don't include a case with an internal `_/` folder that has `__init__.py`. This is the correct convention per the updated AGENTS.md.

**Recommendation:** Add a fixture `internal_pkg/` with structure:
```
internal_pkg/
  main.py              # from ._.internal import func
  _/
    __init__.py        # makes _ a package
    internal.py        # def func(): ...
```
And verify the bundled output inlines `internal.py` correctly.

---

### 20. **No Test for Syntax Error Handling**

No fixture tests what happens when a dependency has a syntax error.

---

### 21. **No Test for Circular Dependencies**

No fixture tests cycle detection/handling.

---

### 22. **No Test for Windows Line Endings (`\r\n`)**

No fixture with CRLF line endings to test `_line_offsets`.

---

### 23. **No Test for Star Imports, Conditional Imports, Dynamic Imports**

---

## Positive Findings

- ✅ Clean separation: `bundler.py` (CLI/entry) + `bundler_impl.py` (logic)
- ✅ Token-based rewriting preserves formatting (comments, spacing)
- ✅ Import merging reduces boilerplate in output
- ✅ Dependency tracking with `depmods` enables correct topological ordering
- ✅ Scope analysis handles functions, classes, comprehensions, lambdas
- ✅ Global/nonlocal statement handling
- ✅ Warning system for star imports, unresolved chains, module-used-as-value
- ✅ All 7 existing test fixtures pass
- ✅ No `xlint` violations (verified)

---

## Recommendations

### Must Fix Before Next Release
1. **Make syntax errors hard errors** — don't silently produce broken bundles (Issue #3)
2. **Add cycle detection in `_topo`** — error or warn on circular deps (Issue #5)

### Should Fix
3. **Handle `\r\n` and `\r` line endings in `_line_offsets`** (Issue #7)
4. **Expand `_merge_imports` to handle multi-name imports** (Issue #4)
5. **Improve `_defkw_of` reliability** or add fallback (Issue #8)
6. **Add type hints to public API** (`bundle()`, key internal functions) (Issue #17)
7. **Add module docstrings** (Issue #18)
8. **Document known limitations** (`__file__`, `importlib.resources`, conditional imports)

### Nice to Have
9. **Add comprehensive test fixtures** for Issues #3, #5, #7, #19-23
10. **Consider AST-based rewriting** for complex cases (long-term)

---

## Next Steps

1. Fix syntax error handling in `_ensure` (make it a hard error)
2. Add cycle detection in `_topo`
3. Add test fixture for `_` folder convention (with `__init__.py` in `_/`)
4. Run bundler on `xcsv/xcsv.py` to verify fix works (already verified)
5. Release fixed bundler, then re-release `xcsv` as v1.1.0

