<!-- spec-origin: ai -->
> **AI-written spec.** Authored by an AI agent, not by the human.

# Pybundle

**Pybundle** combines python code defined *within a folder* into a single file.
Files outside the root folder are never inlined.

## Provenance

Derived from `DRAFT.md`, which holds the human's statement of intent. Every
decision below cites the section of that draft it comes from, so the derivation is
visible rather than asserted — check a decision against the draft, and check the
draft against the discussion it records.

Three of the draft's own sections are superseded by later answers recorded in its
*Open questions*, and this spec follows the later answer. They are listed under
*Superseded draft text* so the disagreement stays visible instead of being quietly
resolved.

`SPEC_old.md` documents the 5-phase bundler this replaces and is not a source for
this spec. `SPEC_new.md` is the human's earlier handwritten attempt.

## Goal

A bundler simple enough that an agent can edit it safely. The rewrite exists
because the previous implementation's complexity stopped that, so **structure is a
requirement here, not an implementation preference.** A spec that described the
right behaviour while leaving structure open would reproduce the failure.

Concretely: no parse tree, no shared mutable state, and a small set of functions
each of which can be validated without reading the rest of the codebase.

## Requirements

### R1 — Inlining

1. The bundler takes a python file to start from. Its parent directory is the
	**root folder**.
2. A file is **local** if it is in the root folder or one of its subfolders.
	Local files are inlined; everything else is left as a normal import.
3. In each file, initially the root file, every import is checked and inlined if
	it is local.
4. **A file's imports are fully processed before that file's own code is
	translated and written.** This keeps each input file as one contiguous block,
	so the start and end comments delimit something real.
5. Non-local imports stay as close to where they were as possible.
6. Each file is processed once. A second reference to an already-handled file is
	dropped with an informative message. This is also what handles circular
	imports: there is no error for them, and code depending on them may break.
7. The root file's modpath is in the handled set before the loop starts, so a
	module importing the root does not break — the import is dropped by the
	ordinary already-handled rule and the root's code is emitted once, last.

*Draft: The loop, Main and the piping.*

### R2 — Output format

A single file containing all inlined files, ordered as python would run them:
imported code first, then the importing file's own code.

Each file's block is bounded by two comments carrying its location, written with
ordinary file path logic — a directory component carries a leading `/`, and a file
directly in the root folder carries none.

	## server.py
	## /server/Command/api.py

The start comment begins with `##`. The end comment is the same string beginning
with `##!`. The root file is not special and gets the same pair as everything else.

Every inlined file emits its block after its imports have been placed, which is
what makes the block contiguous.

*Draft: Output format, The loop.*

### R3 — Name translation

Every processed file has its global names prefixed with its path relative to the
root folder. `/py/command/api.py` under a root in `/` contributes the prefix
`py__command__api__`; `server.py` in the root folder contributes `server__`.

A module's name is always treated as its full modpath. `from . import api` in
`/py/command/map.py` behaves as `py.command.api`, so the reference `api.run()`
becomes `py__command__api__run()`.

Leading underscores move in front of the prefix, so a name that was private in its
own file still reads as private in the bundle:

	_foo -> _helper__foo
	__foo -> _helper____foo

**The root file's own global names are not translated.** This exception is
specific to the root file, not to files in the root folder: `helper.py` and
`client.py` are translated even though they sit beside the root. Names the root
imports *are* translated — only the root's own definitions are exempt.

*Draft: Name translation, Translating global names.*

### R4 — Scope

Translation is scope-aware. A name defined inside a function or class blocks
translation of that name within it, so shadowing does not break. Class bodies
follow the same rule as functions.

A `global` name refers to module level, so it is translated with the file's own
prefix and does not block. A `nonlocal` name belongs to an enclosing function, so
it is not translated and does block.

*Draft: Scope.*

### R5 — Output destination

The destination is **anything file-like** — stdout, a file, a pipe to another
program, an in-memory buffer. One code path; only the sink differs. The output is
identical byte for byte whichever sink is used, and the run does the same work and
raises the same errors either way.

**The bundler never closes a sink it did not open.**

*Draft: Not yet in the draft (sink), Q9, `YEBP3QB`.*

### R6 — Structure

1. **No parse tree.** Import detection, scope detection and definition scanning
	are all statement-based. `ast` is not used. `tokenize` is: lexing is not
	parsing, and it is what makes statement handling correct rather than
	approximate.
2. **State is piped, never global.** There is no shared context object.
3. **Nothing imports the entry file.** The bundler's own modules do not import
	`bundler.py`; `main` wires them together. The bundler must still *handle* a
	module importing the root, which R1.7 covers.

*Draft: No parse tree, Piped state, Main and the piping.*

## Technical decisions

### D1 — Statements, not lines

A **statement** is the unit of processing, taken from the tokenizer's logical-line
boundaries rather than from raw physical lines.

This is a correctness requirement, not a convenience. A dict literal spanning
several lines has continuation lines that look like they sit inside a block by
indentation alone; treating them that way records the entries as local
definitions, which silently blocks translations with no error. A multi-line
string containing a line starting with `def` looks like a function definition.

`tokenize` already computes both correctly: it emits `NEWLINE` only at a real
statement end and `NL` inside brackets, and a multi-line string is a single token.
Indentation is taken from the first physical line of the statement.

### D2 — Scope blocks by indentation

A `def` or `class` statement opens a block. The block runs until a statement
indents less than the opener. Nested blocks stack.

The binding forms recognised inside a block, because each one defines a name that
must block translation: plain assignment, augmented assignment, annotated
assignment, `for` targets, `with ... as`, `except ... as`, walrus (`:=`), the
`def` name, parameters, function-local `import`, plus `global` and `nonlocal`
which behave differently as described in R4.

### D3 — The root exception is the empty prefix

A non-root file's prefix is never empty, because every file has a basename. So an
empty prefix identifies the root uniquely, and translating a name with an empty
prefix returns it unchanged.

The exception is therefore one expression, evaluated in the loop and nowhere else:

	prefix = "" if modpath == entry else flatten(relative_path(modpath))

No other function knows the root exists. This matters because the exception is
**per file identity, not per location** — a sibling in the root folder is
translated, so "is this the root?" cannot be answered from the path alone. It is a
fact `main` supplies and pipes down.

### D4 — The function set

Each function answers a short description of *what*, so an agent can validate one
without the rest of the codebase. A function that only makes sense in combination
with others does not qualify.

| Function | Answers | File |
|---|---|---|
| `statements(text)` | what does this text consist of? | `bundler_source.py` |
| `imports(statements, modpath, root)` | what do these imports bind, and where does it live now? | `bundler_imports.py` |
| `renamed(name, prefix)` | what is this name called in the bundle? | `bundler_names.py` |
| `translate(statements, renames)` | what does this file look like with its names moved? | `bundler_names.py` |
| `inline(modpath, out, seen, entry)` | the loop | `bundler.py` |
| `main(entry, out)` | the setup and the piping | `bundler.py` |

`statements` is computed once per file by `inline` and handed to both `imports`
and `translate`, so nothing is computed twice and the two leaves do not depend on
each other. `translate` calls the block scan internally — passing it in made the
signature a description of how rather than of what.

`renamed(name, prefix)` is the only pure function and carries the underscore rule,
so it is the one most worth testing on its own.

### D5 — Call graph

```python
main(entry_path, out)
    root = dirname(entry_path)
    seen = {entry_modpath}
    inline(entry_modpath, out, seen, entry_modpath)

inline(modpath, out, seen, entry)   # recurses; the only control flow below main
    seen.add(modpath)
    stmts = statements(read(modpath))
    for stmt in stmts where stmt is an import:
        for local, bound_name in imports(stmts, modpath, root):
            if local.modpath not in seen:
                inline(local.modpath, out, seen, entry)
    prefix = "" if modpath == entry else flatten(relative(modpath))
    renames = {own globals -> renamed(name, prefix)} ∪
              {imported names -> renamed(name, their prefix)}
    out.write(start_comment)
    out.write(translate(stmts, renames))
    out.write(end_comment)
```

`renamed(name, "")` is the identity, which is the whole of the root exception.
The own-globals half of `renames` is empty for the root, because every entry would
map a name to itself.

### D6 — Imports

An import statement resolves to zero or more **local** targets, each with a modpath
and the name it binds, or to a **non-local** result that is left in place.

Relative imports resolve against the importing file's modpath, following ordinary
python rules. The root file may not use them. A module path is derived literally
from the file path, so `__init__.py` contributes `__init__` as an ordinary path
component and needs no special case; importing a folder imports its `__init__.py`.

`import x as y` binds the same names `import x` would, so `y.count` and `x.count`
reach the same place.

### D7 — Staging

The bundler is not a library and carries no versions, so stages are notes rather
than numbers.

**Supported from the start:** module imports, relative imports, `__init__.py`,
`import as`, `global` and `nonlocal`, file-like sinks.

**Planned for a later stage:** name imports (`from x import name`) and star imports
(`from x import *`) — neither is supported initially. `from xlib import blah`, and
a generic "also treat that folder as root".

**Excluded on purpose:** dynamic imports (`__import__`, `importlib`); detecting
whether a circular import would cause real issues; detecting or fixing name
collisions between globals of different files.

The third list exists so that readding an excluded feature is a decision rather
than drift. The second list exists so that a planned change is not mistaken for
one.

## Edge cases

**Conditional imports.** All imports are handled as if at the top of the file, so
an indented import is hoisted with the rest. A `pass` statement is left where the
import was. The bundler does not analyse why an import is indented. `if False:
import blah` will import `blah`; behaviour depending on it is not supported, and
`importlib` is the way around it.

**Circular imports.** Handled by R1.6. No error.

**Name collisions.** Between globals of different files, assumed not to happen and
neither detected nor fixed. Putting `__` in front of a name is not a pattern
anyone writes by hand, and a collision may be avoided anyway by the prefix rule
moving extra underscores to the front.

**Errors in source.** Only errors that affect the bundler are relevant. Problems
in the code being bundled are not supported.

## Errors

Ordinary errors — file not found, permission denied — pass through and are not
listed.

**IMPORT_FILE_NOT_FOUND** — a file was not found and it is definitely not a
global, for example from a relative import. Suspected globals do not raise it.

**RELATIVE_IMPORT_IN_ROOT** — the root file used a relative import, which python
does not allow.

**NOT_A_MODULE** — an import of a specific name, which is a later-stage feature.
Reported rather than silently treated as a missing file.

## Command line

```
--in <path>  root file path
--out <path>  bundled result path, or - for stdout

```

Both are required, and no other arguments are accepted; otherwise usage is
printed. Exit code is 0 on success and 1 on any error.

`main` does the transformations the core does not: `--out -` or an absent output
becomes `sys.stdout`, and a path becomes an opened file. The core takes the
file-like object and never opens or closes it itself.

## Superseded draft text

The draft carries three statements that its own later answers contradict. This spec
follows the later answer in each case.

| Draft text | Superseded by |
|---|---|
| **IMPORT_AS** — "Will exist for as long as 'import as' is not supported." | `import as` is required, because it has to define a name in the importing file. Q22 |
| **Future development / Import as** — "Not supported initially." | Same. D7, D6 |
| **Control flow** — `main`, `file.process`, `file.inline`, `import.resolve` | D4's function set, which answers the same questions in six functions across four files |

`file.process` has no successor: its work — setting up state and calling the
per-file function — is what `main` does.

## Terms

**root** — the file path first passed to the program.

**root folder** — the parent folder of the root.

**modpath** — a project's module path, derived literally from the file path.

**local** — inside the root folder or one of its subfolders.

**statement** — one logical line, from the tokenizer's boundaries.

**prefix** — a file's modpath relative to the root folder, flattened with `__`.
Empty for the root.

## Decisions — test pass 1

Added 2026-10-15, from `doc/reviews/pybundle-tests-pass1.md`, which derived 65 tests
from this spec and found twelve places where a test could not be written without a
decision the spec did not contain. Those places are F1–F12 in that review; they are
cited here by the same numbers so the two documents can be read against each other.

Per the process in epiq `6MFX0Z1`, this is an appended section and **nothing above it
was edited.** Several decisions change what an earlier section says — the function
set gains a function, an error is retired, two requirement sentences are reworded.
Rather than edit those sections in place, each decision below names the lines it
supersedes and **restates the corrected text**, so this section is readable on its own
and an agent implementing from it has one place to read. Folding this section back
into the body is a consolidation pass for later, after implementation settles.

### What supersedes what

| Section above | Changed by | Effect |
|---|---|---|
| D4 — the function set | F7.1 | six functions become seven; `cli` added, `inline` and `translate` signatures change |
| D5 — call graph | F4, F5 | restated in full below |
| D6 — Imports | F8 | relative-import restriction and the return shape are decided; name imports become supported |
| D7 — Staging | F8 | name imports and star imports are supported from the start; the staging list is empty |
| R3 — Name translation | F12 | the last sentence is reworded; it means the names a file imports, not only module names |
| R5 — Output destination | F9 | diagnostics are named alongside the sink, and go to stderr |
| Errors | F6, F8 | `RELATIVE_IMPORT_IN_ROOT` gains a home; `NOT_A_MODULE` is **retired** |
| Command line | F7 | restated in full below |
| Draft *Key constraints* | F11 | constraint 3 becomes R7 |

### D8 — Removal of inlined import statements (F4)

**Every local import statement is removed from a file's block before it is written.
Every non-local one stays where it was (R1.5).**

The rule is uniform and does not depend on which files have been handled already.
R1.6's "a second reference is dropped" follows from it rather than being a second
rule: the first reference's statement is removed by the same rule that removes the
second's.

A statement with both local and non-local targets keeps the non-local ones and loses
the local ones, so `import helper, os` becomes `import os`. A statement whose targets
are all local is removed entirely.

To make this possible, `imports` returns **one entry per import statement, in source
order**, rather than a flat list of resolved targets. Each entry carries the statement,
what kind of import it is, its targets — each target a modpath, `None` when the target
is non-local, and the name it binds — and whether the statement was relative.

This replaces D6's "zero or more **local** targets, each with a modpath and the name it
binds, **or** to a **non-local** result that is left in place", which described two
return shapes and said nothing about which statement produced what. Without that link
a specific line cannot be deleted, and `import helper, os` cannot be expressed at all.

`translate` performs the removal, so it takes the per-statement result as a third
parameter. This supersedes D4's description of `translate`, which said it only moved
names: it also drops the statements of imports that were inlined, and — see D9 — emits
the statements a name import needs.

### D9 — Name imports and star imports (F8, F12)

**Every import binds local names**, because that is what python does, not something
this tool invents:

- `import x` binds the name `x`.
- `import x as y` binds `y` instead, and `y` reaches the same place `x` would.
- `from x import *` binds the whole namespace of the target, exactly as
	`from x import name` binds one name.

Two consequences follow, and they are the whole of this decision.

**A name imported into a file becomes that file's global**, so R3's prefix applies to
it. A file A doing `from helper import count` binds `A__count`; the root doing the same
binds `helper__count`, because the root's own prefix is empty (D3). The statement is
rewritten to bind the prefixed name:

- **local module** — the module is inlined as an ordinary import would be, and the
	importing file gains a rebinding: `count = helper__count`.
- **non-local module** — the statement stays, with the bound name aliased:
	`from pathlib import join as A__join`.

**A star import of a local module works**, by the same mechanism applied to every
global the inlined module defines: `from helper import *` in A emits one rebinding per
global of `helper`. The globals a module defines are already known to the loop, so this
costs nothing that is not already being computed.

> **Stated divergence:** rebindings are emitted for the inlined module's **defined**
> globals only. Real `from x import *` also re-exports whatever `x` itself imported. The
> bundler does not do that, and a star import therefore does not carry through a
> module's own imports. This is a limit, like the name-collision exclusion in D7, and
> not an oversight.

**A star import of a non-local module is left in place and warns.** The names it binds
are not known and cannot be translated, so the invariant R3 rests on — that a name a
file binds is renamed to `<prefix><name>` — cannot be enforced for them. The names
land at the bundle's top level unreferenced-but-correct, which is why the import itself
usually works.

It breaks in exactly one way: **a name bound by a star import cannot be reached through
the module that imported it.** Another file doing `import A` and then `A.foo()` expects
`A__foo`, which nothing defines. There is no rewrite that fixes this, because the two
other spellings are both unavailable — `from A import foo` and `from A import *` name a
*local* module and are supported by rebinding, not by referencing the module — and the
only spelling that does work is using the bare leaked name at bundle top level, which
relies on no two modules star-importing a collision.

So: **a warning on stderr, and the behaviour is assumed correct.** It is correct
whenever the file that star-imports is the only file that uses those names, which is the
common case. The remaining case is not worth supporting, because making it correct
requires reading through import lines that would otherwise be left alone — the analysis
this rewrite exists to remove, for a construct that pollutes a namespace so heavily that
collisions become practically inevitable once it is used more than once or twice.

**D7's staging list is now empty.** Name imports and star imports are supported from the
start. D7's third list — dynamic imports, circular-import problem detection, name
collision detection — is unchanged and still stands.

### D10 — The root exception, restated (F12)

R3's closing sentence reads "Names the root imports *are* translated — only the root's
own definitions are exempt." It is reworded, because under D9 it was true of more than
module names and could be read as meaning only those:

> **The names a file imports carry the prefix of the file they came from.** The root's
> own definitions are exempt: an empty prefix translates a name to itself. So a root
> doing `import helper` binds `helper__count` for a count defined in `helper`, while a
> `count = 1` of its own stays `count`.

The exception remains per file identity, not per location (D3), and a sibling in the
root folder is still translated.

### D11 — `inline` takes the root folder (F5)

D4's signature read `inline(modpath, out, seen, entry)`, and D5's body for it read a
file and passed `root` to `imports` — so the signature could not be called as written,
and the spec's one call graph could not be executed.

`root` is not derivable from what `inline` already holds. It is needed to read a file,
to decide locality, and to compute a file's path relative to the root folder; `modpath`
is a module path, not a filesystem path. R6.2 rules out a module-level global, so it has
to be piped.

> **`inline(modpath, root, out, seen, entry)`** — D4's table, corrected.

Batching `root` and `entry` into a small record was rejected: it reads better at five
parameters and is the context object R6.2 exists to remove.

### D12 — The function set, restated (F4, F7.1)

D4's table is superseded by this one. It answers the same question — what each function
is for — and adds the seventh function the command line needs.

| Function | Answers | File |
|---|---|---|
| `statements(text)` | what does this text consist of? | `bundler_source.py` |
| `imports(statements, modpath, root)` | what does each import bind, where does it live, and is what it names local? | `bundler_imports.py` |
| `renamed(name, prefix)` | what is this name called in the bundle? | `bundler_names.py` |
| `translate(statements, renames, resolved)` | what does this file look like once its inlined imports are gone and its names moved? | `bundler_names.py` |
| `inline(modpath, root, out, seen, entry)` | the loop | `bundler.py` |
| `main(entry, out)` | the setup and the piping | `bundler.py` |
| `cli(argv)` | what did the arguments say, and what should the program do about it? | `bundler_cli.py` |

The call graph, corrected in full:

```python
main(entry_path, out)
    root = dirname(entry_path)
    seen = {entry_modpath}
    inline(entry_modpath, root, out, seen, entry_modpath)

cli(argv) -> int
    parse argv; on anything unrecognised, print usage and return 1
    out = sys.stdout if --out is - else open(path, "w")
    try:
        main(entry_path, out)
    except <bundler errors> as e:
        print(e, file=sys.stderr); return 1
    finally:
        out.close() if cli opened it
    return 0

inline(modpath, root, out, seen, entry)   # recurses; the only control flow below main
    seen.add(modpath)
    stmts = statements(read(join(root, modpath)))
    resolved = imports(stmts, modpath, root)
    for target in resolved that is local:
        if target.modpath not in seen:
            inline(target.modpath, root, out, seen, entry)   # returns its globals
    prefix = "" if modpath == entry else flatten(relative(modpath))
    renames = {own globals -> renamed(name, prefix)} u
              {imported names -> renamed(name, their prefix)}
    out.write(start_comment)
    out.write(translate(stmts, renames, resolved))
    out.write(end_comment)
```

`inline` returns the global names it defined, which is what lets a star import rebind
them (D9). `renames` keeps its two halves precisely so they do not collide: a name the
file both imports and defines is a collision, and D7 excludes detecting those.

### D13 — Command line, restated (F7)

Three problems were folded into one section above, and they are answered separately.

**The command line has a home.** `main` was named for two different functions: D5's,
which takes a file-like sink, and the *Command line* section, which also turns a path
into an opened file. It cannot be both, because `inline` writes to `out`. So there are
two, and `cli(argv) -> int` is the new one:

- `main(entry, out)` is unchanged and still takes a file-like. This is what R5 requires.
- `cli(argv)` parses argv, opens and closes the sink, calls `main`, and turns an
	unrecognised argument, a missing file, or a bundler error into exit code 1.

This is what R5's "the bundler never closes a sink it did not open" is for. Before this,
the rule had nothing to distinguish: `cli` closes what it opened, and `main` never closes
anything.

**Nothing parsed argv, printed usage, or returned an exit code.** The draft's superseded
`main() -> int` did all three and D4's table replaced it without naming a successor.
`cli` is the successor. A `__main__` block calls it.

**`--out` was both required and allowed to be absent.** One of the two sentences was
unreachable. It is settled as:

```
--in <path>   root file path, required
--out <path>  bundled result path, required; - for stdout
```

Both flags are required, `-` means stdout, and the absent-output sentence is deleted.
`--out -` opens nothing; the sink is `sys.stdout` itself, and `main` never closes it.

### D14 — Diagnostics (F9)

R1.6 requires an "informative message" when a second reference to a file is dropped,
without saying where it goes. It cannot go to the sink: a message written to stdout
would corrupt the bundle whenever the sink *is* stdout, which R5's byte-for-byte
identity forbids.

**Every diagnostic and warning the bundler produces goes to stderr, and none reaches
the sink.** Three of them exist:

- a dropped second reference to an already-handled file (R1.6)
- a star import of a non-local module (D9)
- usage, when the arguments are not understood (D13)

### D15 — Errors, restated (F6, F8)

**`RELATIVE_IMPORT_IN_ROOT` now has a home.** It is the one error above with no function
able to raise it: `imports` receives the root *folder* and never the entry, and D3 is
explicit that "is this the root?" is per file identity and cannot be answered from the
path. Only `inline` knows `entry`.

It is raised there, using the relative flag D8 already puts in `imports`'s return:

```python
if modpath == entry and any(entry.is_relative for entry in resolved):
    raise RELATIVE_IMPORT_IN_ROOT
```

Adding `entry` to `imports`' signature was rejected — every caller would thread a
parameter that one check uses.

**`NOT_A_MODULE` is retired.** It existed because `from x import name` was a later-stage
feature that had to be *reported* rather than silently treated as a missing file. D9
supports name imports instead, by rebinding the name (D6's phrasing above is
superseded: the "or" it described described two return shapes, and there is one). The
error has no remaining case and is removed from the Errors section.

`IMPORT_FILE_NOT_FOUND` is unchanged, including its rule that suspected globals do not
raise it.

### D16 — The leaves' return shapes (F1, F2, F3)

**`statements(text)`** returns a list of statements, each carrying its text and its
indentation, because D1 and D2 both depend on the latter. The container is a
cross-module contract — `inline` hands the same value to `imports` and `translate` — so
it is fixed here rather than left to each implementer. **Line numbers are not carried**:
nothing in this spec needs them, and a shape that grows is harder to keep an agent
honest against.

**`translate(statements, renames, resolved)`** returns a single string. Statements are
joined with newlines and **no trailing newline is added**; `inline` composes the comment
lines and the separators around it. D5's `out.write(translate(...))` is a string write.

**`imports(statements, modpath, root)`** returns the per-statement list D8 specifies.
The remaining ambiguity — whether a non-local statement yields an entry or nothing — is
resolved by the choice of shape: **every import statement yields an entry**, and what
happens to it is decided by the table in D9.

### D17 — Bare module references (F10)

A module reference used as anything other than the base of an attribute has no rewrite.
The module object exists in the bundle under no name at all, because inlining is done by
prefixing names rather than by constructing an object.

> **A module name used other than as an attribute base is not supported.** The bundler
> does not detect it and does not raise; a bundle referring to one will fail at run time.

`import helper.sub` binds a bare module name and falls under this. It is stated rather
than left implicit because D2 lists function-local `import` as a binding form, and that
form establishes exactly such a name.

### D18 — Non-name text survives unchanged (F11)

The draft's *Key constraints* were never turned into requirements. Three of the four are
already covered — once-only processing is R1.6, the comment marking each inlined file is
R2. Constraint 3 is not, and it is the load-bearing one, because it is what says that
text which is not a name reaches the bundle untouched:

> **R7 — only names are rewritten.** Comments, blank lines, spacing, and the text of
> every expression are carried into the bundle unchanged. The only edits are: a name
> replaced by its bundled name, an import statement of an inlined module removed or
> trimmed, and the statements D9 adds for a name or star import.

Constraint 2 — "the combined file preserves original behaviour when possible" — is not
carried in. It is not testable as written, and R1.6 already says plainly where behaviour
is not preserved: code depending on circular imports may break.

### What the tests must now cover

The existing 65 were derived before these decisions. Most still hold; four changes and a
few additions follow from this section.

- `test_a_name_import_raises` is **wrong and must be replaced.** Name imports are
	supported now. It becomes a test that `from helper import count` produces
	`count = helper__count`, plus the non-local form `from pathlib import join as A__join`.
- Nothing tests the mixed statement `import helper, os`, which D8 now defines.
- Nothing tests a star import of a local module, which D9 now supports.
- Nothing tests a star import of a non-local module warning on stderr, which D9 now
	requires.
- Nothing tests the command line at all, and D13 makes it reachable.
- Nothing tests `inline` directly, and D11 gives it a signature it can be called with.

## Open, and deliberately so

**Two of the review's twelve are settled by accepting a documented limit rather than by
fixing something.** D9's non-local star import is the clearest: the bundler will
sometimes produce a bundle that does not work, and says so on stderr rather than
refusing. If that trade is wrong, the alternative is to raise for every star import,
which is a one-line change to D9 and costs `from pathlib import *`.

**`doc/reviews/pybundle-tests-pass1.md` has one arithmetic problem worth fixing.** Its
summary says six of the twelve flaws are blocking. Nine carry a blocking label in the
body and seven are grouped as such in its own list of what the human has to do. The
count does not reconcile and should not be quoted until it does.

### D19 — Name collisions, restated (extends *Edge cases*)

The *Edge cases* section above says name collisions "between globals of different
files" are assumed not to happen and are neither detected nor fixed. **That names the
wrong surface.** A global a file *defines* is prefixed with that file's prefix, and
prefixes are unique per file because R1.6 processes each file once — so two defined
globals cannot collide. That class is empty by construction.

The names that are **not** prefixed are the ones a file binds through a non-local
import, and every one of them lands in the same namespace, because the bundle is one
file:

- `import math` binds `math`, unprefixed.
- `import cmath as m` in one file and `import math as m` in another both bind `m`.
- a non-local star import binds whatever it brings, unprefixed — the worst case, and
	the one D9 warns about.
- a **root-level** name-import rebinding is unprefixed, because the root's prefix is
	empty. The root doing `from local_func import math` writes `math = local_func__math`,
	which overwrites the `math` another file bound with `import math`.

In a directory of ordinary modules each of those is confined to its own file, and the
names never meet. Bundling puts them all in one, so two files that are entirely
unrelated — they may share nothing but a habit of naming things `math` — now conflict,
and whichever is inlined second wins. Every use of the first one in its own file then
reaches the second one's binding.

**None of that is fixed, and none of it is detected.** It is written down so that it
reads as a decision rather than an oversight, and so that a broken bundle has
somewhere to point:

> **Names bound by non-local imports are not prefixed, and the bundler does not detect
> when two files bind the same one.**

A warning was considered and **declined**. The bundler does see every import statement
in every file it inlines, so collecting the unprefixed bound names and reporting a
duplicate is cheap — the cost is not the collection but the bookkeeping, and the tool's
position is that it is opinionated about what it bundles, not about what it can prove
about the result. The human who ruled on this considered a warning optional and not
necessary; that is the decision, and this is where it is recorded.

**One import is the exception, and the exception is not accidental.** A non-local
**name** import is aliased to the importing file's prefixed global — `from pathlib
import join as A__join` — so its bound name cannot collide with anything. A non-local
**module** import is not, because prefixing it means rewriting every use of that name
in the file, including the uses that are not attribute accesses, which is a larger
change than the collision it would prevent. The asymmetry is the price of leaving
non-local module imports exactly as the source wrote them.

## Decisions — 2026-10-15, after test pass 2

Added 2026-10-15, from `doc/reviews/pybundle-tests-pass1-2.md` and from the rulings the
human gave while that pass was under review. Same discipline as the section above:
**append-only, nothing above it was edited**, and each decision below names what it
supersedes and restates the corrected text so this section reads on its own.

**Read D20 first. It reverses D9, which is in this same document and only two hundred
lines up.** An implementer working top to bottom will reach D9 first and build the
mechanism F13 installed — rebindings deleted, uses rewritten — which is no longer the
design. D9 is not wrong by accident; it was correct when written and the ruling moved.

The rulings are recorded verbatim on epiq `S1G5037` (indentation) and `F7KHKM8`
(imports), with the evidence behind each.

### What supersedes what

| Section above | Changed by | Effect |
|---|---|---|
| D2 — Scope blocks by indentation | human, 2026-10-15 | comparison of strings replaced by matching the tokenizer's INDENT/DEDENT; restated in D21 |
| D9 — Name imports and star imports | human, 2026-10-15 | **reversed**; rebindings return for every import, F13 is undone; restated in D20 |
| D13 — Command line | F14 | one clause: `cli` takes argv, not a program name |
| D14 — Diagnostics | human, 2026-10-15 | three diagnostics become four; the fourth is specified in D23 |
| D16 — The leaves' return shapes | F16 | the two field names are fixed; restated in D22 |
| D1 — Statements, not lines | F17 | one clause: empty lines and comment-only lines pass through |
| D19 — Name collisions | human, 2026-10-15 | three of four collision sources are structurally prevented; restated in D24 |
| *Open, and deliberately so* | F-count | the blocking count is six, not nine; the paragraph is corrected in D25 |

### D20 — Every import rebinds (alias form). Supersedes D9; reverses F13.

**Every import statement binds a name, because that is what python does. The bundler
preserves that binding rather than dissolving it.**

The F13 ruling in D9 — *no rebinding; a name imported from a module is reached by
rewriting each use* — is **withdrawn**. The human's reasoning, verbatim: *"every import
in python actually creates a name and I've been trying to avoid turning that into
guaranteed bloat. Essentially, following python behaviour strictly would be the correct
choice and would mean that every import involves a rebind."*

**The mechanism, by case.**

| Import | Emitted |
|---|---|
| `from helper import count`, `helper` local | statement deleted; `A__count = helper__count` |
| `from pathlib import join`, non-local | statement rewritten in place: `from pathlib import join as A__join` |
| `import math`, non-local | `import math as A__math` |
| `from helper import *`, `helper` local | one rebind per **defined** global: `A__count = helper__count`, … |
| `import email.utils` | statement **kept**, then one rebind: `A__email = email` |

**Why the split on the last row.** `import a.b` binds `a`, not `a.b`. `import a.b as X`
binds `X` to `a.b` — a different object — so aliasing it hands the file the leaf and every
`a.something` that reaches past the leaf breaks:

```python
import email.utils                       # binds `email`
email.utils.parseaddr(s)                 # works — email.utils exposes parseaddr
email.message_from_string(s)             # AttributeError under a naive alias
```

The failure is **half-silent**: the leaf use survives by coincidence, so a test written
against it reports green on a file broken for the other. The parent is unreachable from
the child without `sys.modules`, so the statement is kept and one rebind is added. **The
condition is general, not a carve-out for dotted imports: the alias rule applies except
where python binds a name the statement does not spell.**

**A rebind's left-hand side is already prefixed and is not prefixed again.** R3 must skip
these statements. Without the exemption `A__count = helper__count` inside a function is
re-prefixed and breaks; with it, a name imported at function scope stays function-local in
the bundle exactly as it was in the source. This also settles what D2's binding-form list
means: a function-local name import is a **binding**, not a use, and belongs in that list.

**A rebind travels with its import.** R1.4 places each inlined block before the importing
file's own code, so `A__count = helper__count` must be emitted immediately after that
block, not collected and flushed at the end — the right-hand name may not be defined yet.

**A star import gets the same answer as a name import, not a special one.** The human:
*"star imports are just a more concise version of `from x import a,b,c...` (with all names
mentioned). Therefore they should in practice have the same solutions."* This resolves what
the test pass could not: because the rebind is a **statement**, a later definition of the
same name overrides it in source order, which is python's own behaviour. Under F13 — uses
rewritten, nothing emitted — that case had no correct reading at all.

**A name the inlined module does not define now resolves.** `from helper import Path`,
where `Path` is `helper`'s own non-local import, becomes `A__Path = server__Path` because
that import was itself prefixed on the way in. **D9's stated divergence survives unchanged
and stays benign**: a local star import still carries only the module's *defined* globals,
so it does not re-export what the module imported — but an explicit name import reaches it.

**A star import of a non-local module keeps D9's existing treatment** — left in place, on
stderr, behaviour assumed correct. It is the one import shape the alias rule cannot reach,
because the names are not knowable without reading a module the bundler never sees. D24
keeps this as the sole surviving collision source.

**Verified against real python**, all three of the cases the test pass had left open:

| Case | Bundle | Real python |
|---|---|---|
| local star import, then shadowing (`count = 2`) | `2` | `2` |
| `from helper import Path`, `Path` being `helper`'s import | resolves | resolves |
| name import at function scope | `1`, function-local | `1` |

**Accepted cost.** Prefix lengthens **every reference**, not only the import statements.
Across the bundled corpus measured 2026-10-15: **+3% bytes** (1 618 on 44 807), tracking
*reference count* rather than lines, imports, or file size — 0% in a module with 10
imports and 10% in one with 18 references in 832 bytes. That corpus is shallow and
understates it; the human's own case prefixes 4-character names with 13. Recorded as a
cost the design accepts, not an oversight: *"I don't really see a way around it either."*

### D21 — Blocks are tracked by INDENT/DEDENT. Supersedes D2's comparison.

**A block is closed by a DEDENT token, not by a statement that indents less than its
opener.** D2's wording is withdrawn in favour of matching the tokenizer's own
INDENT/DEDENT stream. Verbatim: *"Using the tokenizer's INDENT/DEDENT is a reasonable way
of interpreting my intent. Checking strings exactly is not necessary, or should come with
the understanding that spaces and tabs need different handling."*

The reason is a silent-wrong-answer failure, not a cosmetic one. Python accepts a module
whose functions are indented with different conventions in different blocks, and
`tokenize` reports that structure correctly. But D16's `indent` is a **string**, and in
python `'\t' < '    '` is **True** — tab is 0x09, space is 0x20. So a tab-indented body
under a space-indented opener reads as *less than* the opener, the block closes on its own
first line, and everything inside is recorded as module scope. **R4 then translates names
that are local, and nothing raises.** A wrong bundle is the failure class this tool can
least afford, and it is silent.

D2's **list of binding forms is unchanged**, plus the function-local name import D20 adds.

### D22 — The leaves' return shapes, and three clauses already answered (F14, F16, F17, F18)

**`statements(text)` returns a list of dictionaries.** F16 asked for the field names and
this is the proposal, now fixed:

| Field | Holds |
|---|---|
| `text` | the statement's source text, first line's indentation included, **every line of a multi-line statement**, no trailing newline |
| `indent` | that same leading whitespace **as a string** — the first physical line's, which D1 already states |

Two choices inside that are load-bearing rather than cosmetic. The text carries **every**
line of a multi-line statement, because R7 requires the text to survive unchanged and
joining statements has to be able to put the file back. The indentation is a **string and
not a column count**, which is precisely what makes D21 necessary: a string is comparable
and a count is not, so D21 states which of the two is used and why.

**`indent` is the callee's text as written.** It is carried, never converted — see D23.

**`cli(argv)` takes argv, not a program name** (F14). Verbatim: *"The program name does
not matter to the person running it."* So the call is `cli(sys.argv[1:])` and a test calls
`cli(["--in", p, "--out", "-"])`, which is what `argparse.parse_args` takes. If the
implementation uses `argparse` the choice is made for it and this clause is belt and
braces.

**Empty lines and comment-only lines pass through unchanged** (F17). The rules about what
a statement is exist **so a multi-line statement is not broken apart, not so that anything
is removed.** Without this clause D1 reads as a licence to drop "unnecessary" parts.

**An indented local import leaves a `pass` where it was** (F18, the last shape D8 and the
*Edge cases* section disagreed on). The import is removed and the one-line compound body
keeps its statement.

### D23 — The indentation warning. D14's fourth diagnostic.

D14 says *"Three of them exist"* and enumerates them. **There are four.** The fourth:

- **Anchor** — the convention of the **root file**, or of the **first file that has
	indentation** where the root has none. The human's reason: *"the root file is the most
	likely to match whatever the project conventions are"*, and it is the cheapest option,
	needing no per-file convention.
- **Trigger** — any **code** line whose leading whitespace carries an indentation type
	other than the anchor's. Both types on one line counts.
- **Ignored** — whitespace-only lines. Verbatim: *"they don't affect how python runs in
	any case."* The same reasoning reaches **multi-line string interiors**, which are one
	token to the tokenizer and are not indentation; this is recorded as the same principle
	rather than as a separate ruling, since it was not stated separately.
- **Report** — one entry per offending file, naming that file's **first** offending line.
	Verbatim: *"good enough, since this is generally not the bundler's purpose."*
- **Never refuse.** The bundle is written.

**The anchor is what makes the warning reach the inline hazard**, which is not obvious from
the trigger's wording. A module and its importer can each be internally consistent and
still collide: a tabs-module imported into a space-indented caller is two clean files.
Anchored on the root, the callee disagrees by construction and every one of its lines
trips the warning. **It is a red flag, not a hazard detector** — the human declined the
analysis explicitly: *"we don't try to figure out whether a particular pattern would break
things. It only matters that tabs and spaces are both used... Putting any serious effort
into dealing with cases where spaces and tabs are used in the same project doesn't seem
sensible, because the user can most likely solve this defect."* Over-firing is accepted; a
tabs-module inlined at depth 4 produces a bundle that **runs correctly** and still warns,
and the wording must not claim otherwise.

**Inlining across conventions is not handled.** A tabs-module inlined at depth 8 with a
sibling at column 16 written with spaces raises `TabError` in the consumer's import. The
bundle is written anyway, with the warning above it. This is D9's posture applied to a
second case, and the reason is *not* the same — D9's cause is the bundler's own inlining,
this one's is a defect in the user's source, which is what makes "the user can fix it" an
argument rather than an excuse.

**Calibrated against this repo, so the rule is known to be quiet rather than merely
assumed to be:** across the 21 files under `dev/` that actually get inlined, and across the
six bundles in `xlib/` the old bundler produced, **0 files are reported**. The 7
whitespace-only lines the ignore clause excludes are all bare tabs in `dev/xhttp/_/` and
were the only thing a literal scan would ever have tripped on.

### D24 — Name collisions under aliasing. Supersedes D19's analysis.

D19 lists four sources of collision between unprefixed names. Under D20, **three of them
are structurally prevented** rather than merely unlikely:

- `import math` binding `math` unprefixed — now `A__math`.
- `import cmath as m` and `import math as m` in two files — now `a__m` and `b__m`.
- a **root-level** name-import rebinding, unprefixed because the root's prefix is empty —
	still unprefixed, but nothing else in the bundle is unprefixed any more, so it has
	nothing to collide with.

**The survivor is the non-local star import**, which D9 already warns about separately, and
which no rewrite reaches because the names are not knowable.

**D19's declined warning may therefore be moot.** Its paragraph records that a warning was
considered and declined — *"considered a warning optional and not necessary"* — on the
grounds that the bundler is *"opinionated about what it bundles, not about what it can
prove about the result."* That reasoning was sound when collisions were undetectable in
practice. Most of them are now **prevented by construction**, so there is less to warn
about rather than more. Whether the paragraph stays is editorial, not a decision, and is
left to the implementer with the reasoning attached.

**Why the two-statement form was rejected for non-local imports**, since it looks like the
cautious choice and is not. Keeping `from x import defs` verbatim and appending
`A__defs = defs` does not remove the collision — it **relocates** it, because that import
binds `defs` at top level whether or not anyone rebinds it, and the rebind copies whichever
import won. Measured with two files importing `defs` from different modules: two-statement
yields `A__defs → FROM-Y` and `B__defs → FROM-Y`; alias yields `A__defs → FROM-X` and
`B__defs → FROM-Y`. The split in D20 keeps the two-statement form only where it is needed.

### D25 — The blocking count

`pybundle-tests-pass1.md`'s summary says six of twelve are blocking; nine carry a blocking
label in the body and seven are grouped as such in its own list. The count does not
reconcile. Reconciled in pass 2:

| Group | Flaws | Count |
|---|---|---|
| blocked tests entirely — no test could be written at all | F4, F5, F6, F7, F8, F12 | 6 |
| blocked direct tests only — resolved by a stated workaround, not a decision | F1, F2, F3 | 3 |
| needed no decision to proceed | F9, F10, F11 | 3 |
| | | **12** |

**Six** is the number that describes what actually stopped the work. The *Open, and
deliberately so* paragraph above quotes the unreconciled figure and should be read against
this one.

### What the tests must now cover

The 138 tests committed in `247eaba` were derived against D9 **as it stood before D20**.
Six of them were deleted or rewritten for F13 and return, and every import-shape test
needs re-deriving against the table in D20. The cases the tests must now pin:

- `from helper import count` emits `A__count = helper__count`, and **nothing** rewrites
	the use — the opposite of what `test_a_root_name_import_rewrites_the_use` asserts.
- `from pathlib import join` emits `from pathlib import join as A__join`, replacing the
	test that asserted `pathlib.join`.
- `import email.utils` emits the statement **and** `A__email = email`, and both
	`A__email.utils.parseaddr` and `A__email.message_from_string` resolve.
- a local star import followed by a shadowing definition resolves to the shadow.
- a name import at function scope stays function-local, which is the rebind-LHS exemption.
- the indentation warning fires on the four specified conditions and not on the two
	excluded ones, with the first offending line named per file.

`NOT_A_MODULE` stays retired (D15). `RELATIVE_IMPORT_IN_ROOT` stays in `inline` (D15).

### D26 — A mixed statement's non-local half is aliased too. Supersedes D8's sentence.

**Ruled 2026-10-17.** D8's sentence — *"A statement with both local and non-local
targets keeps the non-local ones and loses the local ones, so `import helper, os`
becomes `import os`"* — was written before D20 and is superseded on its second half.
The rule is now:

> **A statement with both local and non-local targets loses its local targets and
> has its non-local ones rewritten as D20 rewrites a non-local import on its own.**
> So `import helper, os` in `sub/client.py` becomes `import os as sub__client__os`.

The first half of D8's sentence stands unchanged: local targets are dropped, and a
statement whose targets are all local is removed entirely.

D20's table has no row for a mixed statement, which is why the gap survived two
derivation passes — the alias rule reads as applying to an import statement, and
`import helper, os` is two imports sharing one statement. The rule applies to the
statement that is emitted, whatever produced it: `import os as A__os` is a non-local
module import under D20's third row, and sharing a line with a local target changes
neither what python binds nor which file's prefix applies.

**No test changes with this.** Three already assert the reading — the aliased
half, the dropped local half, and the remaining targets in source order — so this
records the decision the tests were already written against.

This settles the mixed statement only. A statement whose targets are *all* local is
D8's other case and is unaffected; the unanswered question of what a plain local
module import emits is F26, still open.

### Decisions — 2026-10-17, the three blocking flaws

Same discipline: **append-only, nothing above was edited**, each decision naming the
flaw it answers and restating the corrected text. These three are the blocking half
of pass 3's flaw list; F27, F28, F30, F31 and F21 are cheap and none blocks.

| Flaw | Question | Ruling |
|---|---|---|
| F25 | does a use of a name-imported name get rewritten? | yes — to the importing file's own prefixed name (D27) |
| F26 | what does a plain local module import emit? | no rebind; the module name is an alias for the prefixed globals (D28) |
| F29 | does the indentation report quote the line or number it? | both, with the file path (D29) |

### D27 — The use is reached through the importing file's own name. Answers F25.

**Ruled 2026-10-17.** The closing bullet of the 2026-10-15 section reads
`from helper import count` emits `A__count = helper__count`, and **nothing rewrites
the use**. **That bullet is superseded**, and with it the reading it forces:

> **A name import binds the importing file's own prefixed name, and a use of that
> name is rewritten to reach it.** `from helper import count` in A emits
> `A__count = helper__count`, and `count` in A becomes `A__count`.

What does *not* happen is F13's withdrawn mechanism: the use is not pointed straight
at the callee's prefixed global `helper__count`. The distinction matters and is the
whole ruling — the use reaches the name **A** owns, not the name **helper** owns.

Taken literally the bullet produces a bundle that raises `NameError`: the rebind
binds `A__count`, and a use of `count` left alone looks for a name nothing in the
bundle defines. It is also the failure this spec can least afford, because it passes
a text-level test — both lines are present, in a plausible order, and only running
the bundle shows the mismatch.

**D20's verified table is what this restores**, and it is the authority: its third
row — *"name import at function scope → `1`, function-local"* — is unreachable
unless the use names the rebind. The bullet and the table disagreed, and only the
table produces a working bundler.

### D28 — A local module import emits no rebind; its name is an alias. Answers F26.

**Ruled 2026-10-17.** D20's table has five rows and **none of them is a plain local
module import**. Its general condition cannot cover the gap, because it makes it
worse: *"the alias rule applies except where python binds a name the statement does
not spell"*, and `import helper` spells `helper`, so the alias rule appears to apply
— while D17 says the module object exists under no name at all.

> **A local module import emits no rebind. Its name is an alias for the callee's
> prefixed globals: the statement is removed (D8) and a use of `helper` reaches
> `helper__`.**

Four shapes follow from that one rule:

| Source | Emitted |
|---|---|
| `import helper`, `helper` local | statement deleted; `helper.run()` → `helper__run()` |
| `import helper as h`, `helper` local | statement deleted; `h.run()` and `helper.run()` both → `helper__run()` |
| `import helper.sub`, `helper` local | statement deleted; binds the bare `helper`, which D17 leaves unsupported |
| `from helper import nested`, `helper` local | D20's first row, unchanged: `A__nested = helper__nested` |

D6's rule that `y.count` and `x.count` reach the same place holds for local imports
too, which is what makes the second row an alias rather than a second name.

**Aliasing a local module is not available as an alternative.** It would mean
binding a module object the bundle never constructs, and keeping the statement would
make python import the file from disk a second time — the exact duplication R1.6
exists to prevent. Nothing to bind is why there is no rebind, and the alias is the
substitute.

### D29 — The indentation report carries the file, the number, and the line. Answers F29.

**Ruled 2026-10-17.** D23 said *"one entry per offending file, naming that file's
first offending line"*, which fixes the content — a file, a line, and which line —
but not the form. All three elements are now required:

> **Each entry carries the offending file's path, the number of that file's first
> offending line, and the text of that line.**

The path is written the way the start comments write it, so R2's rule applies and a
directory component carries a leading `/`. An entry therefore reads like
`/sub/client.py`, line 2, `\tvalue = 1`.

The three existing tests read the report as quoting the line, and that part was
right; the path and the number were simply never specified. Two tests now pin them,
which they could not before the ruling.

### What the tests must now cover

The re-derivation already asserts D27 and D28 — no test changes with either, and the
four F26 shapes are each covered by an existing test. D29 adds two: the report
carries the offending file's path, and it carries the first offending line's number.
