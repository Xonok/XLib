# Bundler review notes (pybundle/bundler.py)

Living notes for the review + redesign discussion of the pybundle bundler
(`pybundle/bundler.py`, AI-generated, ~870 lines). The human reviewed roughly
the first third, annotating with `#X:` and `%category` markers. This file is
the shared brain for that discussion. It gets adjusted as the discussion
progresses; the actual fix is a separate agent task once the design is agreed.

Status: review ~1/3 done (user), design discussion ongoing, fix not started.

## What the bundler does (one sentence)

Turns a multi-file Python project into a single self-contained `.py`, by
name-mangling every module's top-level names with a flat (dots→underscores)
prefix and rewriting references to those mangled names, then printing
imported modules in dependency order before the entry file.

## Pipeline map (high-level; "the map")

The whole thing is five phases, run from `Bundler.bundle(entry)`:

1. **Locate** (`locate`, `ensure`).
   `bundle` sets `root` to the entry's directory and registers the entry as
   module `""`. `ensure(dotted)` turns a dotted name into a real file under
   `root` (`pkg.mod` → `pkg/mod.py` or a package's `__init__.py`), creating a
   `Mod` per module and caching it in `self.mods`. Packages get the special
   treatment (`is_pkg`, dotted path = package path).

2. **Analyze** (`analyze`).
   For each `Mod`: read the text, build three parallel views (raw text, line
   start-offsets from `line_lengths`, tokens from `tokenize`, AST from `ast`),
   then:
   - `scope_frame`: which names are locals / globals / nonlocals / imports at
     each scope (imports tracked as their own category).
   - `resolve_imports` → `import_stmt` / `from_stmt`: walk ALL imports
     anywhere in the tree (nested ones included), resolve them locally where
     possible, record bindings (`bindmap`: name → `("mod", Module)` or
     `("name", "<flat>_<name>")`), record `depmods` (each module this one
     depends on), and mark each import statement as strip-or-keep
     (`imports_at`).
   - Build `namespace`: classify every module-level binding as `"mod"` or
     `"value"`, using both the imports and the top-level assignments.

3. **Classify** (`classify` / `walk`).
   One AST walk with an explicit scope stack (functions, lambdas,
   comprehensions, classes; `global`/`nonlocal` handled). For every name
   reference:
   - `resolve` walks the scope stack to find whether the name is shadowed,
     then which binding it hits.
   - `name_ref` records the final mangled replacement for each reference
     position (`ownrefs`), plus the mangled assignment at top-level
     definitions (`x = ...` becomes `<flat>_x = ...`).
   - `strip_selfalias` kills `x = modulename` aliases (the value becomes the
     module's own mangled name).
   - `global_stmt` rewrites `global x` to the mangled name where `x` is a
     module-level value.
   - `defkw_of` maps `def`/`class` keyword positions to their mangled names.
   - `toplvl_deps` (per module, run later from `bundle`): top-level
     references that *reach a module* (e.g. `a.b` at top level) add a
     `refdep` so the referenced module gets bundled even if it wasn't
     imported by name.

4. **Rewrite** (`rewrite`).
   Reconstruct the source text by walking the token stream and applying
   replacement spans (`(start, end, newtext)`): strip imports that are local
   or top-level (they'll be hoisted), strip self-aliases, replace `def`/`class`
   names, `global` names, and every `ownrefs` position, and fold attribute
   chains (`a.b.c` on a module → mangled flat name via `fold`/`gather_chain`).

5. **Order & assemble** (`topo`, `bundle`).
   Collect every module's stripped external imports into a merged preamble
   (`merge_imports`), then print each dependency module (body = `rewrite`
   output) in `topo()` order, then the entry last.

Key mechanism: **name mangling is the whole trick.** Every top-level name in
module `a.b` is renamed to `a_b_<name>` at its definition site (`name_ref`
records the assignment as `"x", flat + "_" + name`), and every reference to
it, from any module, is rewritten to the same mangled name. Since all modules
run in one file, later modules can refer to earlier modules' mangled
top-level names directly. Names that must survive mangling (or escape it) are
the ones in `SPECIAL`.

## The user's annotations, summarized (with %category)

Grouped by category. These are observations, not yet all agreed as problems.

### %structure
- The file does too many things; could be split into parts,
  possibly some in a separate library.
- `Bundler` is a class around basically procedural code — this is arguably an
  antipattern: state comes in through attributes instead of function args,
  making it opaque.

### %naming
- `line_lengths` — misnamed: it returns line *start offsets*, not lengths.
- `_PLAIN_FROM` / `_PLAIN_IMPORT` — "plain" is unclear.
- `target_names` — unclear that it means "collect store-target names".
- `Frame` — sounds like a frame, behaves like a scope.

### %bug
- `line_lengths` has no Windows (CRLF) support. NOTE (agent): latent, not
  live — its only consumers (`on`, `strip_stmt`) are fed token positions,
  never `\r`, so CRLF never surfaces today.

### %question
- Import regexes: do they support commas / whitespace? They don't — they
  match a single no-`as` name; anything else (`import a,b`, `import a as b`)
  falls through and is kept verbatim instead of merged.
- Purpose of `merge_imports`: see discussion log.
- Is `Frame` a scope? Yes (locals/globals/nonlocals/imports per scope level).
- What is `entry`? The entry module (`Mod("", entry)`), excluded from its own
  topo sort, seeds the ordering.
- Why three (actually four) parallel representations of the file? text + line
  offsets + tokens + AST; `rewrite` needs all of them in sync.

### %consider
- `Mod` could be a simple dataclass; dot-path handling has simpler options.
- The class-antipattern point (see %structure).

### %informative
- `setdefault` both sets and gets; the add-to-list pattern.
- The tuple-comparison in `token_index_at`.

### %guard / %dont-pass-nulls
- `ensure`'s non-null guard might belong in the caller.
- Reverse the `if m is None` structure for an early return.

## Agreed issues (fixer checklist)

- [ ] **Drop `refdeps` entirely** (analysis: redundant — see discussion log
  entry dated 2026-09-06). Empirically: disabling `toplvl_deps` produces
  byte-identical output on all 7 fixtures. Mechanically, every module that
  could become a `refdep` owner must already be in `self.mods`, and every
  module in `self.mods` was `ensure`d from an import statement and recorded
  in that module's `depmods`. So `refdeps ⊆ ∪depmods` by construction —
  presence never changes. The only thing it can change is *layout order*
  (visiting a module earlier pulls its subtree earlier; still a valid topo
  order, never a correctness issue). Single-pass design: pure import-driven
  DFS is sufficient.
- [ ] **`fold`/`gather_chain` disk-child descent is half-broken.** `fold`
  (bundler.py:780-786) will descend *textually* into a disk child that was
  never `ensure`d (`child is None`, `disk_child` True), appending the mangled
  prefix without updating `cur` — then classifies the next segment against
  the wrong module's namespace → `unresolved chain` warning, reference left
  in place. Confirmed empirically (`import a` + top-level `print(a.b.x)`
  with a sibling `b.py`: warns "unresolved chain", bundles no `b`). Either
  ensure the child or bail; the half-descent is dead intent.

Discussion log items waiting on resolution:

1. **Import ordering: explicit vs implicit.** The bundler currently orders
   output *explicitly*, in a separate `topo()` pass over collected
   `depmods ∪ refdeps`, after resolution and rewriting. Resolution itself is
   already depth-first (imports pull modules in recursively via `ensure`).
   Open: can ordering + resolution + emission collapse into one depth-first
   loop (user's proposed design)? See discussion log.

2. **`merge_imports` necessity.** User reads it as gratuitous — it just
   reformats the preamble. Actual role: dedup identical lines + collapse
   `import a` + `import b` into `import a,b` for the hoisted preamble.
   User accepts import *unpacking* is useful, but says it's not the only way
   to achieve it. Open: keep, drop, or replace.

3. **"Map" as a writing standard.** User: "A map of sorts should become a part
   of how code is written — high-level description of how things work." The
   pipeline map above is a draft of what such a map would look like for this
   file. Open: where it lives (module docstring / header comment / separate
   plans doc), and whether it becomes a rule in AGENTS.md.

4. **Single-pass rewrite design.** User sketched it; evaluate against the
   current five-phase design. See discussion log.

## Discussion log

### 2026-09-06 — Import order: does the bundler do it implicitly or explicitly?

User's proposed model: "If you start with the first import and process it
depth first, you should reach whatever should be the very first inlined module
in the output file. Except for circular imports, this should avoid the need
for explicit ordering."

Verdict (agent analysis):

- **Resolution is already depth-first.** `ensure`/`analyze`/`resolve_imports`
  pull modules in recursively in import order; cycles are absorbed by the
  `self.mods` cache. So "process the first import depth-first" is what already
  happens *during analysis*.
- **Print/emit order is NOT implicit.** It is a separate, explicit pass:
  `topo()` walks `depmods ∪ refdeps` (DFS post-order) after everything has
  been analyzed and rewritten. So the user is right that ordering is
  currently *explicit* — it is recomputed from stored dependency maps instead
  of falling out of the traversal that loads modules.
- **The single-loop design is viable and would work.** For acyclic import
  graphs, depth-first with post-order emission IS a topological order, so a
  loop that does "resolve imports; when a module finishes resolving (all its
  deps done), emit it" produces correct layout with no separate sort. The
  cycle guard must be an explicit in-progress set, not (only) the cache.
- **Caveats the single-pass design must absorb:**
  1. ~~`refdeps`~~ — **RESOLVED: redundant.** See "Agreed issues". A pure
     import-driven DFS is sufficient; `refdeps` never changes which modules
     appear. (Initial concern about top-level `a.b` disk-submodule pulls was
     tested and disproved: the fold's disk-child descent can't classify past
     a non-`ensure`d module, so it yields an `unresolved chain` warning, not
     a new module.)
  2. When a dependency is fully analyzed before the current module is
     rewritten, cross-module name translation is safe-by-construction
     (matches user's "every module is resolved by the time I need to
     translate names coming from it"). Post-order guarantees it.
  3. Hoisted imports preamble: current design strips imports out of bodies
     and emits one merged preamble. Single-pass needs a home for stripped
     imports (per-module inline, or global merge, or dissolve into mangles).

### 2026-09-06 — merge_imports critique

User: "merge_imports seems gratuitous to me because it produces essentially
the same file again. While the import unpacking is useful, it is by no means
the only way of achieving it."

Verdict: confirmed it only serves the hoisted preamble — dedup + collapse of
plain imports + group `from X import Y,Z`. It is presentation, not semantics.
The `%question` regex limitation (single no-`as` name) means it silently
leaves multi-name / aliased imports verbatim anyway. Candidate replacements:
(a) keep per-module import lines in each section, no global merge; (b) emit
imports straight with per-module dedup; (c) dissolve imports into the mangling
(not possible for external modules — they must stay real imports).

### 2026-09-06 — User's proposed rewrite (for evaluation)

If I were to write the bundler myself:
1. Process the entry file's imports depth-first → right ordering implicitly,
   with a circular-import check to stop the loop.
2. For each file, analyze scope and translate any usage of imports using the
   full modulepath relative to root.
3. Print the current file into output, then go to the next.

Should achieve: single loop; correct ordering implicitly; each module resolved
or rejected before names from it are translated; no complex parallel
representations.

Open analysis points for this design (see first log entry): the refdeps gap,
cycle-guard semantics, and where stripped imports go. The "flat mangled name"
scheme (dots→underscores) means "translate usage of imports using the full
modulepath" == replace `pkg.mod.thing` with `pkg_mod_thing`, which only needs
the referred module's *flat name + namespace*, i.e. analysis-time data.