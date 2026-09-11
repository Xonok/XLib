# pybundle Code Review

**Date:** 2026-09-11
**Content Hash:** 23efebb3 (pybundle/ dev folder, all files incl. tests)
**Reviewed:** `pybundle/pybundle.py`, `pybundle/bundler_impl.py`, `pybundle/test/`, SPEC.md, BUG_FIX_SPEC.md, VERSIONS.md, plans/bundler.md, release/release.py
**Compared against:** AGENTS.md, style/common.md, style/python.md, style/architecture.md, pybundle/SPEC.md
**Independent verification:** all bug claims below were re-run and confirmed by a second reviewer pass (worker-nemotron-ultra) on 2026-09-11.

---

## Verdict: NOT ready for release

The 10-fixture suite passes and the module structure is sound, but six correctness bugs survive the previous reviews — several of them silent (bundled output runs, prints wrong results). Two of them hit the most common packaging pattern in Python (re-exports through `__init__.py` / `from mod import name`), so they will bite real libraries, including this repo's own. There is also a version-history/documentation integrity problem (VERSIONS.md claims four released versions; none exist in `xlib/`).

---

## Blocking bugs (fix before release)

### 1. Re-exported names fold to the wrong mangled name (silent NameError)

**Files:** `pybundle/bundler_impl.py:786-788` (`_fold`), `:302-325` (`_from_stmt`), `:178-183` (`_analyze` namespace)

**Repro** (all three files in one dir):

```python
# sub.py
val = 42
# mod.py
from sub import val
# main.py
import mod
print(mod.val)
```

Original prints `42`. Bundled output:

```python
############   from file: sub.py   ############

sub_val = 42
############   from file: main.py   ############

print(mod_val)
```

`mod_val` is undefined → NameError. Same failure for the standard `__init__.py` re-export:

```python
# pkg/__init__.py
from .core import run
# pkg/core.py
def run(): return 9
# main.py
import pkg
print(pkg.run())
```

→ bundled as `pkg_run()`, real definition is `pkg_core_run()` → NameError.

**Root cause:** `_from_stmt` records the re-export in `bindmap["val"] = ("name", "sub_val")` (the *defining* module's prefix), and `_analyze` collapses that into `namespace["val"] = "value"`, throwing the mangled target away. `_fold` then reconstructs the name from the *accessed* module's prefix: `return prefix + "_" + seg` (`bundler_impl.py:787-788`), producing `mod_val` / `pkg_run` instead of `sub_val` / `pkg_core_run`.

**Fix direction:** `_fold` should consult `cur.bindmap.get(seg)` first — if it's `("name", mangled)`, return `mangled`; only reconstruct `prefix + "_" + seg` when the name is a plain top-level def (in `cur.topvals`) with no binding.

**Test gap:** no fixture covers re-exports. Add one (`from sub import val; mod.val` and `pkg/__init__.py` re-export) — this is the repo's own xcsv/xschema pattern.

---

### 2. try/except import-fallback variables get mangled as module-level (UnboundLocalError)

**Files:** `pybundle/bundler_impl.py:475-478` (`_resolve`), `:508-510` (`_name_ref` store mangling)

**Repro** (`helper.py` is an internal module):

```python
# helper.py
def load():
    try:
        import json
    except ImportError:
        json = None
    return json
# main.py
import helper
print(helper.load() is not None)
```

Original prints `True`. Bundled:

```python
def helper_load():
    try:
        import json
    except ImportError:
        helper_json = None
    return helper_json
```

→ `UnboundLocalError: cannot access local variable 'helper_json'` (json *does* import, so the except never assigns, and the mangled `helper_json` was never bound; even if it were, it's the wrong scope).

**Root cause:** `_resolve` treats a name that is both in a function's `imports` and `locals` as never-shadowed (`line 476: if name not in f.imports`). The escape exists so *loads* of an imported name resolve to the module binding — but it also applies to *stores*. The `except`-branch `json = None` is a rebinding of a function-local, and giving it an un-shadowed store makes `_name_ref` mangle it as a module-level name (`store and m.flat` branch), which is wrong the moment the name is also an import.

This is the single most common import idiom in Python (optional-dependency fallback). At module level in a non-entry module the same corruption occurs (`try: import json / except ImportError: json = None` → `helper_json = None`).

**Fix direction:** store contexts to an imported name inside a function scope must be treated as shadowed (local rebinding), or `_name_ref` must check whether any enclosing scope declares the name before applying the module-level store mangling. Loads keep resolving through the binding.

---

### 3. Internal imports kept inside try/except are broken at runtime; nested modules defeat the 1_0_3 removal

**Files:** `pybundle/bundler_impl.py:816-865` (`_remove_internal_try_except`, membership test at line 851), `:543-613` (`_rewrite_import_module`), `pybundle/pybundle.py:66-67`

**Repro A (nested module — 1_0_3's own feature fails):**

```python
# main.py
try:
    from pkg.mod import x
except ImportError:
    from pkg.mod import x
print(x)
```

with `pkg/__init__.py` empty and `pkg/mod.py` = `x = 5`. Bundled output keeps the try/except with `from pkg_mod import x` → `ModuleNotFoundError: No module named 'pkg_mod'` at runtime. The top-level variant (`from helper import x`) is removed correctly.

**Root cause:** there is a name-space mismatch. `_rewrite_import_module` rewrites the internal module name to its *flat* prefix (`pkg_mod`), but `_remove_internal_try_except` checks `modpart not in depmods`, and `depmods` is keyed by *modpath* (`pkg.mod`). Flat == modpath only for top-level modules, so the block survives for anything nested — with a now-unimportable rewritten import inside it.

**Repro B (except branch with code — silently wrong output):**

```python
try:
    from helper import x
except ImportError:
    x = 99
print(x)
```

Original prints `1` (import succeeds); bundle prints `99` — the kept import can never succeed in a bundle (helper is inlined as `helper_x`, not a module), so the except branch executes. No warning is emitted.

**Note:** any internal import that remains in the output (inside try/except, or inside any block that defeats the removal) is dead weight that always raises ImportError at runtime. The rewrite to the flat name cannot make it importable. These cases need — at minimum — a warning; ideally the removal logic should only ever strip an entry try/except whose imports are all internal AND resolvable to a modpath.

---

### 4. `except*` (TryStar) produces invalid output

**File:** `pybundle/bundler_impl.py:257-277` (`_resolve_imports_walk`)

**Repro:**

```python
try:
    import helper
except* ImportError:
    raise
print('done')
```

Bundled output:

```python
try:
except* ImportError:
    raise
print('done')
```

→ `IndentationError: expected an indented block after 'try' statement`. The `try_stack` mechanism only special-cases `ast.Try` (line 260); `ast.TryStar` (Python 3.11 `except*`) falls into the generic child walk with no try context, so `_put_statement` sees `in_try=False`, top-level position (col 0), marks the import strip, and empties the `try:` body.

Python 3.11+ will be the floor for bundled code sooner rather than later; this is a real breakage, not a theoretical one.

---

### 5. Conditional imports silently change side-effect semantics

**File:** `pybundle/bundler_impl.py:338-345` (`_put_statement`), `pybundle/pybundle.py:40-41` (unconditional dep emission)

**Repro:**

```python
# helper.py
print('SIDE')
x = 1
# main.py
if False:
    import helper
    print(helper.x)
else:
    print('skip')
```

Original prints `skip`. Bundle prints `SIDE\nskip` — `helper`'s module-level code executes unconditionally because the import is stripped (`local_hit or toplev` — a block-nested internal import is stripped, contradicting SPEC.md line 31 "Only module-level imports are stripped") and the module is hoisted into the emitted set regardless of the condition.

The import itself cannot survive in a bundle (no runtime module object), so *some* divergence is unavoidable — but it must be warned about and documented, not silent. This also conflicts with SPEC.md:31, which claims block/function imports are preserved (they are stripped whenever they resolve locally).

---

### 6. Module-as-value through a chain fails silently (warning only fires for length-1 chains)

**Files:** `pybundle/bundler_impl.py:736-741` (warning gate `len(chain) <= 1`), `:780-814` (`_fold`)

**Repro A:** `main.py` = `import pkg\ns = pkg.sub\nprint(s.x)` with `pkg/__init__.py` = `from . import sub` and `pkg/sub.py` = `x = 7`. Bundled: `s = pkg_sub` → `NameError: name 'pkg_sub' is not defined` (pkg.sub is a module; there is no runtime object). No warning — the `module used as value` warning only fires when the chain has a single element (`import pkg; x = pkg`).

**Repro B:** `cfg.py` = `import json\nCONFIG = {'a': 1}` and `main.py` = `import cfg\nprint(cfg.CONFIG['a'])\nprint(cfg.json is not None)`. `cfg.json` bails as an unresolved chain (legitimately warned), but the reference is left as `cfg.json` while `import cfg` was stripped → NameError. The warning exists; the failure mode is not cleaned up.

**Fix direction:** `_fold` should warn when the terminal segment resolves to a module (module-as-value, any chain length), and module-attribute chains that bail should be reported clearly as unsupported — the current leave-in-place is a guaranteed NameError.

---

## Non-blocking issues

### 7. Every non-entry module is analyzed twice → duplicate warnings, duplicate work

**Files:** `pybundle/bundler_impl.py:155` (`_analyze` inside `_ensure`), `pybundle/pybundle.py:38` (`_analyze` inside `dfs`)

Verified: a dependency containing `from b import *` emits `star import kept as-is` *twice*. `imports_at`/`bindmap`/`depmods` are idempotent overwrites, but `ctx.warnings.append` is not, and the second full AST walk is wasted. Guard `_analyze` with an `analyzed` flag on `Mod` (or only analyze in one place).

### 8. Dead code

`pybundle/pybundle.py:46-48`:

```python
if body.strip() == "" and mod is not m:
    # skip empty non-entry bodies; still record emitted
    pass
```

The `pass` branch is a no-op; the real empty-body check happens later (line 63-64). Remove it.

### 9. `_fold` alias branch is convoluted

`pybundle/bundler_impl.py:790-807`: the "alias to module" branch does `ctx.mods.get(target_mod.modpath)` and then an identity-scan loop over `ctx.mods.values()` to find a Mod it already holds. `target_mod` **is** the cached `Mod` (everything comes from `_ensure`'s cache); `child = target_mod` suffices. The lookup loop is dead complexity.

### 10. Shebang / encoding header of the entry is dropped

The assembled output starts with the first dependency's `from file:` marker; the entry's `#!/usr/bin/env python3` line and any `# -*- coding: -*-` comment are lost. For library release output this is fine; for executable entry scripts it breaks direct execution. Consider hoisting the entry's leading comments to the top of the bundle. (Tested: shebang lost, output still runs because the test invokes `python3` explicitly.)

### 11. Class `__name__` / `__qualname__` change is an undocumented side effect

`mod.C` becomes `mod_C`, so `obj.__class__.__name__` prints `mod_C`. Inherent to the mangling scheme; should be listed in SPEC's Known Limitations so nobody "discovers" it.

### 12. pybundle does not use the `_` subfolder convention for its own internals

**Files:** `pybundle/pybundle.py`, `pybundle/bundler_impl.py`

pybundle exists to support the repo's internal-folder convention: `_locate` (`bundler_impl.py:93-98`) special-cases a `_` segment as a library-private traversable folder (no `__init__.py` required), and xcsv structures its internals as `xcsv/_/`. Yet pybundle's own dev folder keeps both source files at the root — `pybundle.py` (entry) + `bundler_impl.py` (all internals, see 13). AGENTS.md permits a root-level `*_impl.py` ("internal helpers go in separate files (e.g., `<libraryname>_tok.py`)"), so this is a consistency/structural note rather than a rule violation — but the tool that implements the convention would be the best reference example of it, and it isn't. The bundled output is unaffected (module identity is by modpath, not folder layout).

### 13. All internals live in one 865-line file; split by functionality

**File:** `pybundle/bundler_impl.py`

`bundler_impl.py` mixes five concern areas in a single file, each with its own data-flow contract on `Context`/`Mod`:

- **locating** — `_locate`, `_ensure`, `_ensure_prefixes` (87-166)
- **analyzing / import resolution** — `_analyze`, `_scope_frame`, `_resolve_imports_walk`, `_import_stmt`, `_from_stmt`, `_base_of`, `_put_statement`, `_canon_import`, `_canon_from` (170-355)
- **classifying / scope** — `_params_of`, `_classify`, `_walk`, `_global_stmt`, `_strip_selfalias`, `_resolve`, `_name_ref`, `_defkw_of` (359-539)
- **rewriting** — `_on`, `_strip_stmt`, `_rewrite`, `_gather_chain`, `_fold` (615-814)
- **try/except import stripping** — `_rewrite_import_module`, `_remove_internal_try_except` (543-613, 816-865)

Recommendation: split into `pybundle/_/` modules (e.g. `_/locate.py`, `_/analyze.py`, `_/classify.py`, `_/rewrite.py`), matching the internal-split rule and how the libraries the bundler consumes are laid out. This needs no bundler-side change — `_locate` already handles `_` segments and the `rel`/`pep420_implicit` fixtures prove relative subpackage imports bundle correctly. Splitting is also the natural home for the bug-3 fix (`_remove_internal_try_except` and `_rewrite_import_module` are both token/line-munging, distinct in kind from the AST work around them).

---

## Documentation / process integrity

### 14. VERSIONS.md claims releases that do not exist — and pybundle should not be versioned at all

`pybundle/VERSIONS.md` lists `1_0_0` (2026-09-10) through `1_0_3` (2026-09-11). There is **no `xlib/pybundle_*.py`** (repo-root `xlib/` holds xconf, xcsv, xschema, xtest only; `git log` shows no pybundle release ever landed). Writing entries for versions that were never released (a) is fiction, and (b) will collide with `release/release.py`, which derives the next version from the latest file in `xlib/` — the first real release would be `1_0_0` while VERSIONS.md already claims `1_0_3`.

Beyond the fiction problem, pybundle is a **tool, not a released library** — and per AGENTS.md it must not be versioned at all. It is run via CLI (`python3 pybundle/pybundle.py`) and invoked by `release/release.py` at build time; no released library imports it as a runtime dependency. AGENTS.md ("Tooling") states tools "are not released as versioned files in the `xlib` folder", and "Anything that does not get a version (tools, scripts) does not need a version history either — no versions, no version history." So the correct fix is not "release it so VERSIONS.md becomes true" — it is to **delete `pybundle/VERSIONS.md`** and keep pybundle unversioned like xlint. Version-flavoured language elsewhere (`1_0_1`–`1_0_3` in SPEC.md, the ongoing-reference entries in this review) should be read as plain change-log dates, not releases. (release/release.py's `getattr(lib_module, "bundle")` mechanism could technically release pybundle — see 17 — but it should never be asked to.)

### 15. SPEC.md is substantially out of date with the code

Specifics (SPEC.md line numbers):
- Line 14, 118-120: entry file named `pybundle/bundler.py`; it is `pybundle/pybundle.py` (bundler.py was deleted). Line 120 also claims `pybundle/__init__.py` re-exports `bundler` — the dev folder must not contain `__init__.py` (AGENTS.md), and it doesn't.
- Lines 74, 81-87, 97, 106: describe the `_merge_imports` hoisted-preamble design and its regex limits — that code was removed in 1_0_3; imports are now emitted per-module (`pybundle.py:50-62`).
- Lines 89-93, 101-108: describe `_topo` and the "single-pass redesign" as open design questions — the redesign is implemented; `_topo` is gone.
- Line 110 (Known Limitation 6): modules with SyntaxError get `tree=None` and are emitted as opaque text — contradicted by line 23 and the code (`bundler_impl.py:151-154` raises hard). Limitation 1's regex discussion references removed `_MERGE_*` code.
- Line 31: "Only module-level imports are stripped; imports inside functions/classes are preserved" — false; internal imports at any nesting (functions, `if`, `for`) are stripped (see bug 5).
- Line 149: "All 7 fixtures" — there are 10.

The spec-stays-current-with-code rule (style/common.md, AGENTS.md) was not observed for the 1_0_1–1_0_3 fixes.

### 16. SPEC.md is over the map length target

185 lines against "aim for well under 100" (style/common.md). Phase-by-phase detail plus data structures plus fixture list — trim to the map + invariants + decisions.

### 17. SPEC "Release Integration" section is wrong about release.py

SPEC.md:134-136 says `release/release.py` calls `bundler.bundle(str(entry))`. The actual mechanism (`release/release.py:71-73`) is:

```python
lib_module = importlib.import_module(f"{library}.{library}")
bundle_fn = getattr(lib_module, "bundle")
```

`getattr` on the *library's own module* — only pybundle has a `bundle` function. Verified: `hasattr(importlib.import_module('xcsv.xcsv'), 'bundle')` is `False`, so `release.py xcsv` (and every other library) crashes with AttributeError. Either release.py must import the bundler explicitly, or the SPEC's claim must change. (release.py is a separate WIP, but the SPEC must not describe a mechanism the repo doesn't have.)

### 18. STATUS.md / plans drift (out of reviewer scope to fix; noted)

- STATUS.md:56 still lists "single-pass redesign still open" — implemented 2026-09-10.
- plans/bundler.md:1 header says `pybundle/bundler.py`; plans/bundler.md:174-175 says `pybundle/__init__.py` re-exports `bundler` — contradicts AGENTS.md (no `__init__.py` in dev folders).
- STATUS.md is dirty (uncommitted changes not mine), so I did not update it.

---

## Evaluation: why the single-pass redesign is not shorter

The single-pass redesign was billed as "easier than the previous approach", and it is — for the part it touched. But that part was always a small minority of the code, and the file has grown since, so the metric everyone actually notices (line count) went the wrong way.

**The numbers (this repo's own history):**

| State | bundler entry | impl | total |
|---|---|---|---|
| previous committed (`HEAD`, pre-redesign) | `bundler.py` 69 | `bundler_impl.py` 722 | 791 |
| current | `pybundle.py` 99 | `bundler_impl.py` 865 | 964 |

**+173 lines net.** The two subsystems the redesign removed and what replaced them:

- `_topo` (~18 lines) → DFS post-order in `bundle()` (~15 lines): no net win. The cycle guard even grew (a `visit_stack` + warning path, `pybundle.py:24,32-34`) for the 1_0_3 cycle-reporting fix.
- `_merge_imports` + `_MERGE_IMPORT`/`_MERGE_FROM` regexes (~30 lines) → per-module `ext_lines` harvesting (`pybundle.py:50-59`, ~10 lines): the one real saving, ~20 lines.

Orchestration + assembly — the only code the redesign rewrote — saved roughly **25-45 lines, 3-5% of the file**. Everything else is why there is no shrinkage:

1. **The rewrite engine was never in scope.** `_rewrite` (token walk), `_scope_frame`/`_walk`/`_resolve` (scope analysis), `_fold`/`_gather_chain` (chain folding) existed before the redesign and still exist; together they are ~430 of the 865 lines, and they are orthogonal to single- vs multi-pass ordering. "Easier" was a claim about control flow, and the control flow was already the small part.

2. **Every bug fix is additive, and the fixes outsized the redesign's savings.** Each new behaviour is a new explicit case-branch in the engine:
   - `_rewrite_import_module` (543-613): ~70 lines — rewriting non-stripped imports inside try/except (1_0_2/1_0_3).
   - `_remove_internal_try_except` (816-865): ~50 lines — stripping internal-only try/except blocks (1_0_3). Note what this is: a **line-based re-implementation of string-munging** — precisely the category of code the single-pass AST redesign was supposed to eliminate — and it is buggy (bug 3: nested modules defeat it; the membership test keys on flat names against a modpath-keyed dict).
   - `_resolve_imports_walk` + `try_stack` (~+20 lines) for import-stripping inside try/except.
   - `SPECIAL` set growth, `_strip_selfalias` bindmap registration, `_fold`'s alias branch, `_name_ref` store handling, `_import_stmt`/`_from_stmt` prefix machinery, cycle-path tracking: together ~+50.
   - The two try/except fixes alone (`_rewrite_import_module` + `_remove_internal_try_except` + the `_resolve` escape) added ~140 lines — the try/except problem domain went from "not handled" to "handled by ~145 lines across two mechanisms (AST walk *and* line parser)".

3. **The redesign also created new bookkeeping the old code lacked:** per-module import emission needs `imports_at` keyed by `(lineno, col_offset)` and the `(strip, ext)` tuple protocol (`_put_statement`, `_canon_import`/`_canon_from`), and the entry file grew 69 → 99 lines (ext harvesting, cycle reporting, the `_remove_internal_try_except` call, argparse).

4. **Single-pass is not a size strategy, it is a correctness strategy.** The current review's bugs 1-6 are all name-resolution/rewrite corner cases (re-exports, try/except fallback, `except*`, conditional imports, module-as-value) — none of them orchestration bugs. The redesign made the ordering trivial and that *is* the win; it never promised the file would shrink, and the 6 remaining bugs show the residual cost (the engine) is where the invariants actually live.

**Where real shrinkage would come from, if it is wanted:** not the orchestration (already single-pass) but the engine — resolve and emit at the AST level per statement and delete both token/line-munging subsystems (`_rewrite_import_module` + `_remove_internal_try_except`, ~120 lines), or hard-contract the unsupported patterns (try/except-import fallback, re-exports) to fail loudly instead of being handled, dropping their handlers entirely. Until then, "not shorter" is the expected outcome: the redesign bought maintainable ordering, bug-fixing bought correctness, and both were paid for in lines.

---

## Style compliance

- ✅ Tabs, single-line imports, comma-joined stdlib imports (`import argparse,ast,os,sys`) — but a blank line separates the stdlib import from the try-import block (python.md: "no blank lines between imports") — trivial.
- ✅ Public API type hints now present (`bundle(entry: str) -> str`, `main() -> None`).
- ✅ Guard-first structure, `(result, error)`-free single-purpose helpers, no class-wrapping of procedural code.
- ✅ `xlint` clean on the whole folder.
- ✅ CRLF normalization verified working (`_read_text`), bundle output runs with LF.

## Tests

- ✅ 10/10 fixtures pass and each bundled output runs with identical stdout (verified again this review).
- ✅ Self-bundle: pybundle bundles itself, `py_compile` clean, entry try/except removed, `--help` works.
- ❌ Coverage gaps that allowed bugs 1-5 through: no re-export fixture, no try/except-fallback fixture, no conditional-import fixture, no `except*` fixture, no duplicate-warning check. The comparison harness only checks stdout equality — fine — but the fixture set must include the common patterns above.

---

## Recommendation

1. Fix bugs 1 and 2 first — they break common, everyday packaging patterns and fail silently.
2. Fix 3-6 (at minimum: warn loudly and document; ideally handle correctly).
3. Fix 7-11 while in there (small).
4. Delete `pybundle/VERSIONS.md` — pybundle is a tool, not a released library (AGENTS.md Tooling: no versions, no version history for tools). Do not "release it to make the history true".
5. Sync SPEC.md and plans/bundler.md with the implemented design (drop the `1_0_x` language — they are dates, not releases).
6. Consider the structural items 12-13 (use `_/` internally; split `bundler_impl.py` by functionality) — natural fit while fixing bug 3, since both fixes touch the same two munging subsystems.
7. Add the missing fixtures (re-exports, try/except fallback, conditional imports, `except*`), then run `release/release.py` for the *libraries* (xcsv/xschema) that genuinely need a release — pybundle does not.

The suite passing is not evidence here: the 6 blocking bugs all produce *successful* runs with wrong output or crashes on patterns no fixture exercises.

**Approval: not granted for this state.**