# pybundle Bundler Review (Updated Dev Version)

**Date:** 2026-09-10 (updated after latest fixes)  
**Reviewed:** `pybundle/bundler.py`, `pybundle/bundler_impl.py`  
**Test suite:** `pybundle/test/test_bundler.py` (10 fixtures, all passing)  
**Compared against:** AGENTS.md, style/common.md, style/python.md, plans/bundler.md, pybundle/SPEC.md, pybundle/BUG_FIX_SPEC.md, pybundle/VERSIONS.md

---

## Executive Summary

**All critical bugs fixed. All 10 test fixtures pass.**

Since my last review, the following fixes have been implemented and verified:

| Bug | Status | Fix Location |
|-----|--------|--------------|
| **Bug 1: Self-alias double-prefix** | ✅ **FIXED** | `_strip_selfalias` registers alias in `bindmap`; `_name_ref` simplified; `_fold` handles module aliases |
| **Bug 2: Entry module fallback** | ✅ **FIXED** | Removed in previous iteration |
| **Bug 3: PEP 420 implicit packages** | ✅ **FIXED** | `_locate` returns directory path; `_ensure` creates synthetic package module |

**Test Results:** 10/10 pass (`alias`, `collision`, `deep`, `entry_only_imports`, `nested`, `pep420_implicit`, `rel`, `self_alias`, `single`, `stdlib`)

---

## Changes Since Last Review

### ✅ Bug 1: Self-Alias — FIXED

**Root cause:** The previous fix in `_name_ref` was incorrectly applying the prefix to the helper module's own definition (`helper_x = 1` → `helper_helper_x = 1`).

**Solution (3-part fix):**

1. **`_strip_selfalias` (lines 471-477)**: Registers the alias in `bindmap` when detecting `x = module`:
   ```python
   m.bindmap[t.id] = bm  # register alias for module reference via assigned name
   ```

2. **`_name_ref` (lines 512-520)**: Simplified — removed the problematic `if store and m.flat:` branch that caused double-prefix. Now all module references get `("M", target)`.

3. **`_fold` (lines 720-738)**: Enhanced to follow module aliases via `bindmap`:
   ```python
   if kind == "mod":
       bm = cur.bindmap.get(seg)
       if bm and bm[0] == "mod":
           # Follow the alias to the target module
           ...
   ```

**Result:** `self_alias` fixture now correctly outputs:
```
############   from file: helper.py   ############
helper_x = 1
############   from file: main.py   ############
print(helper_x)
```

### ✅ Bug 3: PEP 420 — FIXED

**Root cause:** `_locate` detected implicit namespace packages but returned `__init__.py` path which didn't exist.

**Solution (2-part fix):**

1. **`_locate` (lines 121-151)**: Returns directory path for PEP 420 packages:
   ```python
   file_path = os.path.join(dirpath, "__init__.py")
   if not os.path.isfile(file_path) and os.path.isdir(dirpath):
       return ".".join(parts), dirpath  # Return directory, not __init__.py
   ```

2. **`_ensure` (lines 165-191)**: Creates synthetic empty package module for directories:
   ```python
   if os.path.isdir(file):
       m.text = ""
       m.line_offsets = []
       m.tokens = []
       m.tree = ast.parse("")
   ```

**Result:** `pep420_implicit` fixture now correctly outputs:
```
############   from file: namespace/mod.py   ############
namespace_mod_x = 42
############   from file: main.py   ############
print(namespace_mod_x)
```

### ✅ Other Improvements

- **Line ending normalization**: `_read_text` converts `\r\n` and `\r` to `\n`
- **SPECIAL set expanded**: Added `__loader__`, `__spec__`, `__annotations__`, `__builtins__`
- **Module docstrings**: Both files have descriptive docstrings
- **Test assertions corrected**: All 3 new fixtures have proper expectations
- **SPEC.md updated**: Documents single-pass architecture accurately
- **stdlib test fixed**: Split `import json,collections` regex

---

## Test Suite Status

| Fixture | Status | Notes |
|---------|--------|-------|
| `single` | ✅ | Helper module inlined, imports hoisted |
| `nested` | ✅ | Deep package hierarchy, relative imports |
| `collision` | ✅ | Same name `tag` in two modules, both bundled |
| `alias` | ✅ | Import aliases (`import random as rr`, `connect as link`) |
| `rel` | ✅ | Relative package imports (`from . import`, `import pkg.top`) |
| `deep` | ✅ | Deeply nested packages (`from db import core`) |
| `stdlib` | ✅ | Standard library usage preserved |
| `self_alias` | ✅ | **Bug 1 fixed** — module alias works |
| `entry_only_imports` | ✅ | **Bug 2 fixed** — empty entry body |
| `pep420_implicit` | ✅ | **Bug 3 fixed** — implicit namespace packages |

---

## SPEC.md Accuracy

**Accurate and up-to-date** for the single-pass DFS architecture. Key documented items:
- Hard SyntaxError stop (not silent)
- Per-module external imports (no global merge)
- `_merge_imports` removed
- PEP 420 support implemented

---

## Remaining Items (Non-Blocking)

### Should Fix (Before Release)

1. **Cycle detection warning** — `visiting` set silently drops modules in cycles; should warn with cycle path
2. **Dead code removal** — `_merge_imports`, `_topo`, `_MERGE_IMPORT`, `_MERGE_FROM` still in `bundler_impl.py` (not imported but present)
3. **Type hints** — Public API (`bundle()`, `main()`) lacks type annotations

### Nice to Have

4. **Additional test fixtures** for edge cases (syntax errors, circular deps, Windows line endings, star imports, conditional imports)
5. **AST-based rewriting** consideration for complex cases (long-term)

---

## Architecture Summary (Current)

**Single-pass DFS** in `bundler.py:bundle()`:
```
dfs(mod):
  if emitted: return
  if visiting: return  # cycle guard
  visiting.add(mod)
  _analyze(ctx, mod)           # Analyze (locate → scope → imports → classify)
  for dep in mod.depmods:      # Recurse dependencies (post-order)
      dfs(dep)
  visiting.remove(mod)
  emitted.add(mod)
  body = _rewrite(ctx, mod)    # Rewrite with name mangling
  emit with file header + per-module external imports
```

**Key mechanisms:**
- Name mangling: `module.name` → `module_name` (dots → underscores)
- Module aliases: `x = module` → `bindmap["x"] = ("mod", module)` → rewritten as module reference
- PEP 420: Directory with `.py` files = traversable package (synthetic empty module)
- External imports: Stripped from bodies, emitted per-module at section top

---

## Release Readiness

**Ready for v1.0.0 release** pending:
1. Remove dead code (`_merge_imports`, `_topo`, regexes)
2. Add cycle warning (optional but recommended)
3. Add type hints to public API (per style/python.md)

All functional requirements met. The bundler correctly handles:
- Multi-file projects with imports
- Relative and absolute imports
- Module aliases (`x = module`)
- Name collisions across modules
- Deep package hierarchies
- PEP 420 implicit namespace packages
- Standard library imports (preserved)
- Import aliases (`import x as y`)
- Self-aliases stripping

---

## Next Steps

1. **Clean up dead code** in `bundler_impl.py`
2. **Add cycle detection warning** in `bundler.py:dfs`
3. **Add type hints** to `bundle(entry: str) -> str` and `main()`
4. **Run full test suite** one more time
5. **Release pybundle v1.0.0** via `release/release.py`
6. **Re-release dependent libraries** (xcsv, etc.) using new bundler