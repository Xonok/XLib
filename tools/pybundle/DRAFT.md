# Pybundle rewrite — DRAFT

**A working document, not the spec.** It holds the intent, so a discussion has
something to push against. The spec is derived from this afterwards.

- Everything under **Intent** is yours — carried from `SPEC_new.md` and from what
	you have said in discussion, with wording left as you wrote it. Small edits
	only: headings, tables, list markers. Nothing rephrased.
- Everything under **Open questions** is mine. None of it is decided.

## Intent

### What pybundle is

**Pybundle** combines python code defined *within a folder* into a single file.
It doesn't inline any files that are outside the root folder.

It works by:

1. **Inlining** each import at its first occurrence.
2. **Prefixing** all imported names within the imported file.
3. **Rewriting** imported names with the prefixed versions.

### Rationale

This spec is for rewriting pybundle into a single-pass bundler.
The previous version became impossible for agents to handle due to complexity.
The current document is meant to replace it with a simpler design.

### Key constraints

1. Every file is processed only once and immediately inlined.
2. The combined file preserves original behaviour when possible.
3. Code changes are limited to imported names. Local names are not rewritten.
4. Each inlined file leaves behind a comment with where it came from.

### No parse tree

Avoid the parse tree entirely seems possible, so we should do that until an
unfixable issue arises.

### Output format

A single file that contains all inlined files.
The file ordering is identical to the order python would run them.

Each inlined file additionally gets a comment that outlines where it's from.
The comment states the file location, so it can be understood from the comment
alone.

A key detail is that the file location has to be understandable from the comment,
so if root is in / and a module is in /server/Command/api.py then the start
comment for the latter becomes:

	"## /server/Command/api.py"

If the root is server.py for example, the comment for it becomes:

	"## server.py"

The reason the root file doesn't start with / is that it's in the root folder.
Let's say there are multiple files in the root folder:

	server.py
	helper.py
	client.py

All 3 of them would lack the /, because all of them are directly in the root
folder. The / is specifically to denote a folder. This is essentially just
ordinary file path logic.

There can be multiple imports per line.
In that case the comments are separate for each file.
Each comment is before the inlined file it refers to.

The root file is not special, it gets the same comments.

Each inlined file also gets a comment where the inline ended.
The end comment is identical to the start comment, except it starts with ##!.

### Name translation

Names are translated by taking the full modpath of the file,
then replacing each . in the modpath with `__`

Every module name is treated as if it were the full modpath instead.
For example, when the root is at:

	/server.py

A module at:

	/py/command/api.py

Imported from `/py/command/map.py` as:

	from . import api

Will be handled as if it were imported with:

	import py.command.api

Then, when rewriting a reference to it, it will turn:

	api.run()

Into:

	py__command__api__run()

### Translating global names

Every single file that gets processed needs to have its global names run through
a translator that uses its path relative to the root folder to prepend something
to it.

Now, what is the prefix? It's essentially the file path relative to root folder.
For the server.py example, its contents would have to be prepended with
`server__`.

For readability reasons, a special rule is needed: if the global name starts with
any amount of "_", all those are put before the prefix. This way the output file
still makes it clear which names are meant to be local. All underscore at the
start of the original name go in front of the translated name. It doesn't apply
to root, since it would be a no-op for root.

I initially thought that the root file's paths can be left alone, but that would
break or become inconsistent if there are other files in the root folder.

But wait, there is an issue: the root file actually does need special handling,
because I want the root file(and only the root file) to have its names remain
untranslated. If other files are in the same folder, leaving theirs untranslated
could cause collisions, so this exception needs to be specific to the root file,
not all files in the root folder.

### Scope

In any case, the translation logic does need to be aware of function (and
probably class) scope. The simplest way to do it would be to look for lines where
the non-whitespace part starts with `def`, note its level of indentation and treat
all lines until a less indented statement appears as within the function.

Another complexity with scope: a name defined within a function needs to block
any translation of that same name within the function, since otherwise shadowing
would break.

Classes also follow the rule.

`global` and `nonlocal` are supported. A `global` name refers to module level, so
it is renamed with the file's own prefix and does not block a rename. A `nonlocal`
name belongs to an enclosing function, so it is not renamed and does block one.

### The loop

The overall flow of the bundler should be like this:

- It takes in a python file to start from.
- In each file(initially the root file) it checks whether each import is
	local(i.e. in the same folder or its subfolders) and inlines it if it is.
- Once a file's imports are fully processed, the actual code of that file is
	translated and written to the output.

For now let's just get the basic loop right.

Non-local imports should remain as close to where they were as possible.
The reason for handling imports first is to keep each input file separate in the
output. Then it's possible to show with comments where each inline started and
ended.

The same import is never inlined or processed twice. This also cuts out circular
import issues. In ordinary cases, python import ordering is perfectly clear about
which file runs first. An import in python is literally just running the file
after all, so `import a,b,c` just means "run a, then b, then c".

### Main and the piping

There is a main function that handles the initial setup - taking in the first
file, taking its directory as the root path, setting up whatever variables need
to be set up, piping together whatever files the bundler is made of.

The piping is relevant because nothing in the library's own modules is allowed to
import the root file according to XLib rules. While the bundler needs to support
doing so, it shouldn't itself be written that way.

Main needs to handle as much as it can of the plumbing, but fundamentally there
needs to be a per-file function that can call itself. Split their
responsibilities according to that.

Use piping, not globals.

### Control flow

**main**() -> int_result
Processes commandline parameters to decide what to do.
The arguments are:

	--in	root file path
	--out	bundled result path

Explanation:
Gives an error when either of the parameters is missing,
or when there are extra parameters provided.
Otherwise calls *file.process*
Returns 0 on a success, 1 on any error.
Providing the wrong parameters prints usage instructions.
Example usage:

	python3 pybundle.py --in /path/to/root.py --out /path/to/bundle.py

**file.process**(fpath_in,fpath_out) -> int_result
Sets up the shared state used for the process.
Calls *file.inline* on the root file.

**file.inline**(modpath,file_out,modules) -> None
*modpath* is the path of the imported file.
*file_out* is the handle of the output file being written to.
*modules* is a list of all currently inlined modpaths.

First adds the modpath of the current file to modules.
Then finds and handles all import lines in order. For each import line:

- *import.resolve* to find out modpaths
- *file.inline* to process them.

Then goes line by line and translates names. Is aware of function scope.
Inlines imports and keeps track of what has been inlined in the current file.
Rewrites global and imported names.

**import.resolve**(line_import,modpath_source,modules) -> modpath[],import_line
Takes an import line and the module path of the file it was in.
If the import line contains " as ", throw the *IMPORT_AS* error.
If an import is already in modules, drop it and print an informative message.
Returns 2 values:

- modpaths - A list of module paths resolved relative to root. (this is *not* modules)
- import_line - the remaining import line without the resolved modules, or None

### Piped state

Get rid of shared state and just pipe in the appropriate state.
Some piped state will have to be mutable - the list of all handled imports for
example. Since the actual list or dict for it can be added to, this is not hard
to achieve.

### Edge cases

**Relative imports**
Handled in import.resolve.
The current file's module path is provided.
Replace the last part of the module path with the file's name.
Follow the ordinary python rules - root file is not allowed to have them.

**`__init__.py`**
Match python behaviour.
Trying to import a folder actually imports that folder's `__init__.py`
If the import is:

	from example.path.here import blah

The prefix would be:

	example__path__here____init____blah

**Circular imports**
Each file is inlined immediately.
Further imports of the same file are dropped.
Code that depends on circular imports is allowed to break.
Detecting whether a circular import would cause real issues is out of scope.
Therefore there will be no errors for them.

**Conditional imports**
All imports are handled as if they were at the top of the file.
When an import is indented, a pass statement will remain where it was.
Indented imports will not be analyzed to figure out why they're indented.
This will import blah:

	if False: import blah

Any complex behaviour depending on it will not be supported.
You can use importlib to bypass this issue if needed.

**Dynamic imports**
For example: `__import__` and importlib
Will not be supported.

**Name collisions**
Assumed to not happen.
Will not be detected or fixed when they do.

**Errors in source**
The only relevant errors are those that affect the bundler itself.
Will not be supported otherwise.

### Errors

Will pass on ordinary errors like "file not found" or permission errors.
**They will not be listed here.**

This section describes errors specific to pybundle.

**IMPORT_FILE_NOT_FOUND**
When a file isn't found and it's definitely not a global.
For example, from a relative import.
Suspected globals don't throw an error.

**RELATIVE_IMPORT_IN_ROOT**
Python doesn't allow those.
If the bundler encounters them, it should throw an error.

**IMPORT_AS**
Will exist for as long as "import as" is not supported.
Resolver throws this errors when it encounters " as ".

### Future development

**Import as**
Not supported initially.
Code that uses "import as" will throw *IMPORT_AS*

**Name imports**
Python allows importing modules, but also names from within modules.
For example, you can import a specific function or variable.
Initially not supported. Support can be added later if needed.
For now, any code with name imports will fail with: "import file not found"

**from xlib import blah**
Will be supported as an option eventually.
When it is, XLib imports will be possible to inline.
Perhaps this will be a generic "also treat that folder as root" logic.

**Anything we won't support**
Things that weren't supported initially can be supported later.
Tracking down bugs is hard and pybundle should help when possible.
However, pybundle should first of all be a tool for bundling.
Trying to catch every single issue is not practical at first.

### Import as

Not supported initially.
Code that uses "import as" will throw *IMPORT_AS*

This is superseded: `import as` needs to define a name in the file it's
importing to. See *Import as* below and Q22.

### Test cases

TODO

### Terms

**root path**(root)
The file path that is first passed to the program.

**root folder**
The parent folder of the root path.

**module path**(modpath)
Project-local path that python uses to identify modules.
Each file's path is literally derived from its file path, so `__init__.py` does
not require special handling.

### NOTES

Make AI produce a call graph when making other specs. For each stage, talk what
happens and what errors can come up.

## What this draft has to settle

By the end of the discussion:

- The call graph is clear.
- Which function goes in which file.
- Data formats, as far as they affect the result of the bundler's actual running.
- Features to support or not support.
- How each feature is supported logically.

## Not yet in the draft

**The output sink.** Settled on `YEBP3QB` (2026-09-29) and absent from
`SPEC_new.md` entirely: the destination is anything file-like — stdout, a file, a
pipe. One code path, only the sink differs, output identical byte for byte, and
the bundler must not close a sink it did not open. It needs a home in *Control
flow*, because at library level the destination is a file object — if the core
takes a path and a flag, the capability is only faked at the edges. Q9.

**Deliberate feature losses as a list.** `6MFX0Z1` concern 2: without one, every
readdition is drift back toward the current complexity, decided by nobody. Q8.

## Open questions

### Q1 — SETTLED

The translation logic does need to be aware of function (and probably class)
scope. Blocks are found by looking for lines whose non-whitespace part starts with
`def`, noting the indentation level and treating every line until a less indented
statement as inside the function.

So this is indentation-based scope detection, not the AST scope engine the old
bundler has. `_scope_frame` and `_walk` exist to resolve per-scope bindings with
`global`/`nonlocal`; this does not need those.

A name defined within a function blocks translation of that name within the
function, so shadowing does not break.

### Q2 — SETTLED

All global names are prefixed, not just functions. The rule is stated generally as
"every single file that gets processed needs to have its global names run through
a translator".

The prefix is the file path relative to the root folder, so `server.py` in the
root folder contributes `server__`.

Two exceptions are recorded under *Translating global names*: the root file's own
names are not translated at all, and leading underscores move in front of the
prefix.

### Q3 — SETTLED

#### What a function is here

Being a leaf node means a function has to be simple to use in practice too. A
function is an interface that turns a complex description of "how" into a short
description of "what". Functions that only make sense when combined in complex
ways do not qualify.

Functions are named by the concern of the file they end up in. Submodules should
avoid needing each other as much as reasonable, without duplicating work.

#### The set

| Function | What it answers | File |
|---|---|---|
| `statements(text)` | what does this text consist of? | `bundler_source.py` |
| `imports(statements, modpath, root)` | what do these imports bind, and where does it live now? | `bundler_imports.py` |
| `renamed(name, prefix)` | what is this name called in the bundle? | `bundler_names.py` |
| `translate(statements, renames)` | what does this file look like with its names moved? | `bundler_names.py` |
| `inline(modpath, out, seen, entry)` | the loop | `bundler.py` |
| `main(entry, out)` | public API — the setup and the piping | `bundler.py` |

`statements` is computed once per file by `inline` and passed to both `imports`
and `translate`, so nothing is computed twice and the two leaves do not depend on
each other. `translate` calls `scopes` internally — passing `scopes` in made the
signature a description of how rather than of what, and one justified edge is
better than a four-argument interface.

#### How the root exception is handled

`main` seeds `seen` with the root's modpath. An import of the root file is then
dropped by the ordinary already-inlined rule, its code is emitted once and last,
and nothing breaks when a module imports the root — however that is achieved.

The translation exception is the empty prefix. A non-root file's prefix is never
empty, so `""` identifies the root uniquely and `renamed(name, "")` returns the
name unchanged. No other function knows the root exists:

	prefix = "" if modpath == entry else flatten(relative_path(modpath))

`entry` is the single fact main supplies and passes down.

#### Why statements rather than lines

A statement is what makes line-based processing correct. A dict literal spanning
several lines has continuation lines that look like they sit inside a block by
indentation alone, and getting that wrong records its entries as local
definitions, which silently blocks renames. A multi-line string containing a line
starting with `def` looks like a function definition.

`tokenize` already computes this: it emits `NEWLINE` only at a real statement end
and `NL` inside brackets, and a multi-line string is a single token. Logical
statements come from the tokenizer rather than from guessing at indentation, which
is why lexing is worth having even though parsing is excluded.

#### The one cost of this set

`find_blocks` was the heaviest piece in the first proposal, because finding a
block by indentation and recognising the binding forms inside it are two separate
jobs. Taking statements first makes it one pass: each statement knows its
enclosing blocks by indentation as it goes.

The binding forms it still has to recognise: assignment, augmented assignment,
annotated assignment, `for` targets, `with ... as`, `except ... as`, walrus, the
`def` name, parameters, function-local `import`, plus `global` and `nonlocal`
which are supported and behave differently from the rest — a `global` name is
renamed with the file's own prefix and does not block, a `nonlocal` name is not
renamed and does.

### Q4 — SETTLED by the loop

All imports are processed before any of the file's own code is written, so every
import — indented or not — lands before the body. That is what *Edge cases* means
by "handled as if they were at the top of the file", and it agrees with non-local
imports staying where they were.

*Output format* still says "The file ordering is identical to the order python
would run them", which holds only when imports sit at the top of the source. For
`if False: import blah`, python never runs `blah`; the bundled file does. That
sentence needs to describe what the loop does. Left as written, for you to
reword.

### Q5 — SETTLED, and replaced by a bigger question

`as` is no longer automatically an error: Q19's answer requires `import as` to
define a name in the importing file, so the *IMPORT_AS* error cannot fire on
every `as`.

That supersedes two places in the draft:

- *Errors* — **IMPORT_AS** "Will exist for as long as \"import as\" is not
	supported. Resolver throws this errors when it encounters \" as \"."
- *Future development* — **Import as**: "Not supported initially."

Both now say the opposite of what the design needs. How much of `import as` is
actually supported is Q22.

The existing fixture `test/fixtures/alias/` uses `import random as rr`, where
`random` is a global — that one is left alone and is no longer a problem.

### Q6 — SETTLED: name imports and star imports are staged, not excluded

The handwritten spec is more constrained because the plan was to initially
support as few features as possible. The current attempt does not need to avoid
extra features as much, but implementing in stages is still useful.

**If name imports can be reasonably excluded from the first version, they should
be.** Since star imports are essentially name imports, they can be excluded from
the initial version just the same.

So the initial version supports neither `from x import name` nor `from x import *`. Both
are later-stage, and the draft currently words both as permanent exclusions:

- *Future development* — **Name imports**: "Initially not supported... will fail
	with: \"import file not found\""
- the `__init__.py` section's worked example is itself a name import, so it
	describes later-stage behaviour

**Worth knowing before the versions are numbered.** The containment for star
imports still holds whenever they are added: the set of a module's global names is
already computed, because the translator needs it in order to prefix those names.
Resolving one specific name, or all of them, is then a lookup in a set that
already exists.

Staging is the right call regardless. What the spec needs is the stage written
down, so a test knows what it is testing, and so nobody reads "not supported" as
"never". The bundler is not a library and carries no versions, so stages are
noted in prose rather than numbered.

### Q7 — SETTLED

Each file's path is literally derived from its file path. There is one modpath
per file and no special case for `__init__.py`, which contributes `__init__` as
an ordinary path component.

That keeps the `__init__.py` section's worked example correct as written —
`example__path__here____init____blah` is just `example/path/here/__init__.py` with
every separator and the `.py` flattened.

### Q8 — SETTLED

The spec can have whichever lists make sense. The distinction between excluded on
purpose and future work is kept, and features carry a note about which stage their
support should be added at.

Since the bundler is not a library it does not need explicit versioning, so a stage
is a note rather than a number. The shape the spec will take:

1. **What the initial version supports**, each entry noted with its stage.
2. **Planned for a later stage**, so a readdition is not mistaken for scope creep.
3. **Excluded on purpose, and why** — dynamic imports, detecting whether a circular
	import causes real issues, name collision detection.

`6MFX0Z1` concern 2 asks for the third list so each readdition is a decision.
That only works for genuinely excluded things; a staged feature was always going
to be added, and filing it as a loss makes a planned change look like drift.

### Q9 — SETTLED

The core takes whatever can handle the cases needed. If no single option can, there
should be different ways of using the bundler, with main handling the required
transformations.

**A single file-like sink does cover every case that exists**, so the fallback is
not needed:

| Case | Sink |
|---|---|
| stdout | `sys.stdout` |
| a file | `open(path, "w")` |
| a pipe to another program | the pipe's write end |
| returning the text to a caller | `io.StringIO()`, then `.getvalue()` |

The last one is why the library-level shape matters: `release.py:74` calls
`bundler.bundle(str(entry))` and wants the text back. With a file-like core it
passes a `StringIO` and reads it — and the bundler must not close a sink it did
not open.

So the core takes an object with `.write()`, and main does the transformations:
`--out -` or an absent flag becomes `sys.stdout`, a path becomes an opened file.

### Q10 — SETTLED

| File | What it is |
|---|---|---|
| **DRAFT.md** | summary of human intent, lightly edited to flow better |
| **SPEC.md** | technical decisions made based on that intent |
| **SPEC_new.md** | my handwritten attempt at the spec. Has some useful clues at my intent, but might be outdated. Will be deleted once the bundler has an implementation that matches my intent |

The current `SPEC.md` is renamed to `SPEC_old.md` so it survives (Q23), and
`SPEC_new.md` goes when the implementation matches the intent.

`SPEC.md` is AI-written and documents the 5-phase bundler being replaced.
`SPEC_new.md` is this draft's predecessor. Nothing points from one to another and
they disagree.

Proposed flow: `SPEC_new.md` → `DRAFT.md` → derived `SPEC.md`, with the old two
retired. Confirm or say what you want instead.

### Q11 — SETTLED

The spec file is the AI's, but it has to be clearly based on the human's intent in
the draft file.

So SPEC.md is AI-written and carries `<!-- spec-origin: ai -->` per
`doc/development.md`, and it is derived from DRAFT.md rather than written
independently. "Clearly based on" is the part worth respecting: a reader should be
able to trace each technical decision back to the intent it came from, so the
derivation is visible rather than asserted.

### Q12 — SETTLED

The comment states the file location, not the import statement. It has to be
understandable from the comment alone, so it is the path below root, written with
ordinary file path logic: a directory component carries a leading `/`, and a file
directly in the root folder carries none.

	## server.py
	## /server/Command/api.py

So the root is not special and gets the same pair of comments as everything else.
The end comment is identical to the start comment except it starts with `##!`.

The same import is never inlined or processed twice, so a dropped import leaves
nothing behind — no dangling `## /some/path.py` line — and that is also what
handles circular imports.

### Q13 — SETTLED

Get rid of shared state and just pipe in the appropriate state. Some piped state
will have to be mutable — the list of all handled imports for example. Since the
actual list or dict for it can be added to, this is not hard to achieve.

The old section describing `modules` and `root` as process-held state is gone,
replaced by *Piped state*. The old `Context` object is what this removes.

### Q14 — SETTLED

Yes, the `__init__.py` file is fine to treat as an ordinary file in this case.
`from foo import bar` runs `foo/__init__.py` and then `foo/bar.py`, and both
appear as ordinary blocks.

This has a consequence for the `__init__.py` section — see Q7.

### Q15 — SETTLED

Each file's path is literally derived from its file path, so `__init__.py` needs
no special handling.

### Q16 — SETTLED

Avoid the parse tree entirely seems possible, so we should do that until an
unfixable issue arises.

So the definition scan runs on lines, not on the parsed tree, and so do import
detection and scope detection. Every one of the three is line-and-indentation
based. The "until an unfixable issue arises" is the escape hatch: if a case turns
up that genuinely cannot be handled this way, the answer is to change this
decision explicitly, not to quietly reintroduce `ast`.

*Does that rule also rule out `tokenize`?* See Q21 — it matters, because
distinguishing `api.run()` from `x.api` and from the text `api` inside a string is
what tokenizing buys, and it is lexing rather than parsing.

### Q17 — SETTLED

Classes also follow the rule.

`global` and `nonlocal` are supported. A `global` name refers to module level, so
it is renamed with the file's own prefix and does not block a rename. A `nonlocal`
name belongs to an enclosing function, so it is not renamed and does block one. A class body is an indented block found the same
way, its names are not global so they are not prefixed, and a name defined in a
class body blocks translation within that body just as a function-local name
does.

### Q18 — SETTLED

All underscores at the start of the original name go in front of the translated
name. In `helper.py`, whose prefix is `helper__`:

	_foo -> _helper__foo
	__foo -> _helper____foo

It does not apply to root, since it would be a no-op for root.

### Q19 — SETTLED

The names from imports are translated. Only the root file's own definitions are
left alone — so a root doing `from helper import count` gets `helper__count`,
while its own `def run()` stays `def run()`.

Where a root wants to shadow an imported name into a local, that is the root's
own rewriting to do: `import x as y`, or `a = imported_thing`. Not a bundler
concern.

But it carries a consequence: `import as` needs to define a name in the file
it's importing to. That makes `import as` a **required feature**, which
contradicts *Errors* (**IMPORT_AS**) and *Future development* (**Import as**).
See Q5 and Q22.

### Q20 — SETTLED

*Edge cases* keeps its original text unchanged:

	**Name collisions**
	Assumed to not happen.
	Will not be detected or fixed when they do.

With the current structure it is very hard for things in separate files to have
name collisions, since putting `__` in front of a name and importing it from
elsewhere is not a pattern anyone does. Even if they did, the prefix logic might
still avoid a collision by moving the extra underscores to the very start of the
translated name.

The shadowing rule from *Scope* is a different thing and does not contradict
this — it handles a local name inside a function, not two globals.

### Q21 — SETTLED

Tokenize is likely fine. Lexing is not parsing, so the "no parse tree" rule does
not rule it out.

### Q22 — SETTLED, and star imports move to a later stage

Importing a module's internals still rebinds them, so `import helper as h` binds
the same names `import helper` would, and `h.count` and `helper.count` land in the
same place.

**Star imports are a later stage.** Since they are essentially name imports, they
are excluded from the initial version on the same grounds (Q6).

The containment below is kept because it is what makes them cheap when added: a
star import essentially rebinds the whole global namespace, which would normally
force reading every name out of every file. The containment is that this is
already being computed — the translator has to enumerate a file's global names in
order to prefix them, and a star import needs exactly that set. So it is a rename
table with more entries rather than a new mechanism.

That works because imports are inlined before the importing file's body is
translated, so the imported file's globals are already known by the time the star
import's own file needs them.

### Q23 — SETTLED

Rename it to `SPEC_old.md` so it survives. It gets deleted once the new
implementation is good.

It keeps its `<!-- spec-origin: ai -->` marker as the record of the 5-phase bundler
the rewrite replaces.
