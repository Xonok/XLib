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

	## server.py                 ## /server/Command/api.py

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

	_foo  ->  _helper__foo
	__foo ->  _helper____foo

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

	main(entry_path, out)
	    root   = dirname(entry_path)
	    seen   = {entry_modpath}
	    inline(entry_modpath, out, seen, entry_modpath)

	inline(modpath, out, seen, entry)          # recurses; the only control flow below main
	    seen.add(modpath)
	    stmts = statements(read(modpath))
	    for stmt in stmts where stmt is an import:
	        for local, bound_name in imports(stmts, modpath, root):
	            if local.modpath not in seen:
	                inline(local.modpath, out, seen, entry)
	    prefix   = "" if modpath == entry else flatten(relative(modpath))
	    renames  = {own globals  -> renamed(name, prefix)} ∪
	               {imported names -> renamed(name, their prefix)}
	    out.write(start_comment)
	    out.write(translate(stmts, renames))
	    out.write(end_comment)

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

	--in <path>    root file path
	--out <path>   bundled result path, or - for stdout

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