# pybundle Spec

## Overview

**pybundle** turns a multi-file Python project into a single self-contained `.py` file. It does this by:

1. **Name-mangling** every module's top-level names with a flat prefix (dots → underscores)
2. **Rewriting** all references to those mangled names
3. **Hoisting** imports into a preamble, ordered by dependency
4. **Printing** each module's body with file markers, ending with the entry file

## Pipeline (5 Phases)

The bundler operates in five sequential phases, orchestrated by `bundle(entry)` in `pybundle/bundler.py`. Shared state (`root`, `mods`, `entry`, `warnings`) lives on a `Context` passed as the first argument to every phase helper.

### 1. Locate (`_locate`, `_ensure`, `_ensure_prefixes`)

- `bundle` sets `root` to the entry's directory and registers the entry as module `""` (empty modpath).
- `_ensure(ctx, dotted)` turns a dotted name into a real file under `root` (`pkg.mod` → `pkg/mod.py` or a package's `__init__.py`), creating a `Mod` per module and caching it in `ctx.mods`.
- Packages get special treatment (`is_pkg`, dotted path = package path).
- `_ensure_prefixes(ctx, dotted)` ensures all parent packages are loaded first (e.g., importing `pkg.mod` loads `pkg` then `pkg.mod`). This guarantees package `__init__.py` code runs before submodules.
- If a module cannot be located, it is recorded as an external import and kept (canonicalized).
- **SyntaxError handling**: `ast.parse` is wrapped in try/except; on failure, `m.tree = None` and `_analyze` returns early. The module is treated as opaque — its text is emitted as-is without name mangling.

### 2. Analyze (`_analyze`)

For each `Mod`:
- Read the text (binary read, UTF-8 decode with Latin-1 fallback), build four parallel views: raw text, line start-offsets (`line_offsets`), tokens (`tokenize.generate_tokens`), and AST (`ast.parse`).
- `_scope_frame`: determine which names are locals / globals / nonlocals / imports at each scope. Imports are tracked as their own category. Handles all assignment forms: `Assign`, `AnnAssign`, `AugAssign`, `NamedExpr`, `For`/`AsyncFor`, `With`/`AsyncWith`, `ExceptHandler`, plus function/class defs, lambdas, comprehensions.
- `_resolve_imports` → `_import_stmt` / `_from_stmt`: walk **all** imports anywhere in the tree (nested ones included), resolve them locally where possible, record bindings (`bindmap`: name → `("mod", Module)` or `("name", "<flat>_<name>)"`), record `depmods` (each module this one depends on, including package prefixes via `_ensure_prefixes`), and mark each import statement as strip-or-keep (`imports_at`).
  - Strip decision: `strip = local_hit or toplev` where `toplev = node.col_offset == 0`. **Only module-level imports are stripped**; imports inside functions/classes are preserved in the module body.
  - External imports are **canonicalized** via `_canon_import`/`_canon_from` (preserving aliases, not verbatim).
- Build `namespace`: classify every module-level binding as `"mod"` or `"value"`, using both the imports and the top-level assignments.

### 3. Classify (`_classify` / `_walk`)

One AST walk with an explicit scope stack (functions, lambdas, comprehensions, classes; `global`/`nonlocal` handled). Scope kinds: `"func"`, `"lambda"`, `"comp"` (comprehensions), `"class"`. Each `Scope` carries `locals`, `globals`, `nonlocals`, `imports`.

For every name reference (`ast.Name`):

- `_resolve` walks the scope stack (reversed) to find whether the name is shadowed, then which binding it hits.
  - Function/lambda/comprehension scopes: `globals` passes through; `nonlocals`/`locals` (if not in `imports`) shadows.
  - Class scope: shadows only if the current node IS the class body (`stack[-1] is f`).
- `_name_ref` records the final mangled replacement for each reference position (`ownrefs`):
  - If binding is `("mod", Module)`:
    - If `store` and module has `flat` prefix: record `("x", "<flat>_<name>")` and add to `topvals` (module assigned to a name).
    - Else: record `("M", target_module)` for chain folding.
  - If binding is `("name", mangled)`: record `("x", mangled)`.
  - If no binding and `store` and `m.flat`: record `("x", "<flat>_<name>")` and add to `topvals` (top-level definition).
- `_strip_selfalias` kills `x = modulename` aliases **only when the RHS resolves to a `("mod", ...)` binding**. The alias statement is marked for stripping (`strips_at`); the name `x` gets the module's own mangled name.
- `_global_stmt` rewrites `global x` to the mangled name where `x` is a module-level value. Builds `m.globals_at[lineno][name] = mangled_name` for the rewrite phase.
- `_defkw_of` maps `def`/`class` **keyword token positions** to their mangled names. Scans **tokens** (not AST) for `NAME` tokens `"def"`/`"class"` followed by a `NAME`; matches against module-level defs/classes in `topvals`.

**Core mechanism: name mangling.** Every top-level name in module `a.b` is renamed to `a_b_<name>` at its definition site (recorded in `ownrefs` as `("x", flat + "_" + name)`), and every reference to it, from any module, is rewritten to the same mangled name. The entry module has `modpath = ""` → `flat = ""` → **no prefix** (e.g., `run` not `_run`). Names in `SPECIAL` (`True`, `False`, `None`, `__name__`, `__doc__`, `__package__`, `__file__`) survive mangling unchanged.

### 4. Rewrite (`_rewrite`)

Reconstruct the source text by walking the token stream and applying replacement spans (`(start, end, newtext)`). Token positions `(lineno, col_offset)` are converted to character offsets via `_on(m, start, end)` using `line_offsets`.

- Strip imports marked `strip=True` in `imports_at` (local or top-level) via `_strip_stmt`. Finds statement end by tracking paren depth and `NEWLINE`/`;` tokens.
- Strip self-aliases marked in `strips_at`.
- `def`/`class` keywords: when token is `def`/`class`, sets `pending = (next_token_index, mangled_name)` to replace the following identifier.
- `global` statements: uses `globals_at` map to rewrite each name token.
- Every `ownrefs` position: if `("x", mangled)` → replace token; if `("M", module)` → gather chain via `_gather_chain` and fold via `_fold`.
- `_gather_chain`: collects consecutive `NAME . NAME . NAME` tokens.
- `_fold(ctx, target_module, chain)`: iterates chain segments:
  - If `cur.namespace.get(seg) == "value"` → return `prefix_seg` (mangled value).
  - Else → lookup child module in `ctx.mods.get(cur.modpath + "." + seg)`; if **not found, bail (return `None`)** — the disk-child fix. If found, descend, extend prefix, continue.
  - On success returns `(mangled_text, consumed_count, owner_module)`.
- Replacements sorted by start offset, applied to original text.

### 5. Order & Assemble (`_topo`, `_bundle`)

- Collect every module's stripped external imports into a merged preamble via `_merge_imports` (dedup + collapse `import a` + `import b` into `import a,b`, group `from X import Y,Z`).
- `_topo(ctx)` walks `ctx.entry.depmods.values()` via DFS post-order with cycle detection (`visiting` set). Each module visited after all its dependencies. The entry module is excluded from its own topo sort.
- Print each dependency module (body = `_rewrite` output) in `_topo()` order, then the entry last.
- Each module body prefixed with `############   from file: <rel>   ############`.
- Entry file's body appended last (leading newline stripped if preamble exists).
- Warnings printed to stderr: star imports, module used as value, unresolved chains.

## Import Handling

- **Plain imports** (`import x`): stripped from module bodies if local or top-level, collected, and merged in the preamble via `_merge_imports`. Regex `_MERGE_IMPORT` matches `^import ([A-Za-z_][A-Za-z0-9_]*)$` — **single name, no alias**. Multi-name imports like `import a, b` and aliased imports `import a as b` fall through and are kept verbatim (in canonical form) in the module body.
- **From imports** (`from x import y`): stripped from module bodies if local or top-level. Regex `_MERGE_FROM` matches `^from ([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*) import ([A-Za-z_][A-Za-z0-9_]*)$` — **single name, no alias**. Star imports (`*`) are kept as-is with a warning. Multi-name / aliased from-imports fall through.
- **Relative imports** (e.g., `from . import y`): stripped and hoisted; base package computed by `_base_of` from current module's `modpath` and `node.level`.
- **Package prefixes**: `_ensure_prefixes` loads all parent packages, adding them to `depmods` so they appear before submodules.
- Non-matching imports are canonicalized (via `_canon_import`/`_canon_from`) and kept in the module body before stripping decision.

## Topological Ordering

`_topo(ctx)` walks `ctx.entry.depmods.values()` via DFS post-order with `visiting` set for cycle detection. Each module visited after all its dependencies (recorded in `depmods`). Result is a valid topological order where dependencies always appear before dependents.

**Note:** `refdeps` was dropped entirely (see Agreed Issues). Presence never changes which modules appear — `refdeps ⊆ ∪depmods` by construction.

## Known Limitations / Open Issues

1. **Import regex limitation**: `_MERGE_IMPORT` and `_MERGE_FROM` only match single-name imports without `as`. `import a, b` and `import a as b` fall through and are kept verbatim (canonicalized).

2. **CRLF line endings**: `line_offsets` has no Windows (CRLF) support, but this is latent — consumers receive token positions, not raw `\r` bytes.

3. **Single-pass redesign**: Currently a five-phase pipeline. A single-pass depth-first design is viable for acyclic import graphs (post-order emission IS a topological order), but would need to handle:
   - The hoisted imports preamble (where do stripped imports go?)
   - Cycle detection (explicit in-progress set)
   - Per-module inline imports vs global merge

4. **`merge_imports` necessity**: Currently serves the hoisted preamble — dedup + collapse of plain imports + group `from X import Y,Z`. It is presentation, not semantics. Open question: keep, drop, or replace with per-module dedup.

5. **Entry module exclusion**: The entry module (`Mod("", entry)`) is excluded from its own topo sort, seeding the ordering. This is intentional but could be clarified in the design.

6. **Syntax errors in dependencies**: Modules with `SyntaxError` get `tree = None`, are not analyzed, and their text is emitted as-is (no mangling). This allows bundling projects with broken non-entry modules but may produce incorrect cross-references.

7. **Dynamic imports**: `importlib.import_module`, `__import__`, etc. are not analyzed and will not be mangled. They remain as runtime imports.

## API Structure

Per AGENTS.md, the public API split is:

- **`pybundle/bundler.py`**: Public API only — `bundle(entry)` and `main()`. No internal classes/functions.
- **`pybundle/bundler_impl.py`**: All internals — `Context`, `Mod`, `Scope`, and all `_`-prefixed phases (`_analyze`, `_rewrite`, `_topo`, etc.).
- **`pybundle/__init__.py`** (if it exists): Re-exports `bundler`.

**Public function signatures:**

```python
def bundle(entry: str) -> str:
    """Bundle `entry` (a file path) into one self-contained source string."""
    ...

def main():
    """CLI entry point: bundle the entry script and print/stdout-write the result."""
    ...
```

## Release Integration

The release script (`release/release.py`) calls `bundler.bundle(str(entry))` to produce a versioned file in `xlib/`. The bundled output format matches what the test fixtures expect (module bodies with `############   from file: ...   ############` markers, hoisted imports preamble, mangled name references).

## Test Fixtures

All 7 fixtures must pass:
- `single` — helper module + main, imports hoisted
- `nested` — server package with subpackages, relative imports
- `collision` — two modules with same name `tag`, both bundled correctly
- `alias` — import aliases (`import random as rr`, `connect as link`)
- `rel` — relative package imports (`from . import`, `import pkg.top`)
- `deep` — deeply nested packages (`from db import core`)
- `stdlib` — standard library usage (`from urllib.parse import urlparse`, `import math as m`)

All tests currently pass.

## Key Data Structures

### `Context`
- `root`: project root directory
- `mods`: `modpath → Mod` cache
- `entry`: entry `Mod` (modpath `""`)
- `warnings`: list of warning strings

### `Mod`
- `modpath`: dotted module path (e.g., `"pkg.mod"`, `""` for entry)
- `flat`: `modpath.replace(".", "_")` — mangling prefix
- `file`: absolute file path
- `is_pkg`: `os.path.basename(file) == "__init__.py"`
- `rel`: relative path from `root` (for file markers)
- `text`, `line_offsets`, `tokens`, `tree`: four parallel views
- `topvals`: dict of top-level defined names
- `bindmap`: name → `("mod", Module)` or `("name", "<flat>_<name>")`
- `depmods`: modpath → Module (dependencies, including package prefixes)
- `imports_at`: (lineno, col_offset) → (strip_bool, [canonicalized_external_imports])
- `namespace`: name → `"mod"` or `"value"` (module-level bindings)
- `ownrefs`: (lineno, col_offset) → `("x", mangled)` or `("M", Module)`
- `defkw`: (lineno, col_offset) → mangled_name (for `def`/`class` keywords)
- `strips_at`: (lineno, col_offset) → True (self-alias statements to strip)
- `globals_at`: lineno → {name: mangled_name} (for `global` rewriting)

### `Scope`
- `kind`: `"func"`, `"lambda"`, `"comp"`, `"class"`
- `locals`, `globals`, `nonlocals`, `imports`: name → True sets

## Agreed Issues (Fixed)

- [x] **Drop `refdeps` entirely** — redundant; `depmods` suffices
- [x] **`fold` disk-child bail** — returns `None` instead of half-descent
- [x] **`Bundler` class → free functions** — state on `Context`
- [x] **API/internal split** — `bundler.py` public only, `bundler_impl.py` internals