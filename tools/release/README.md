# Release script: purpose and scope

This is the release script. It creates versioned copies of development libraries.

## Purpose

It makes a versioned copy of a library's development folder, producing a single
self-contained file in `xlib/` (named `libraryname_major_minor_revision.py`) that
users can import either unversioned (`from xlib import libraryname`) or explicitly
(`from xlib import libraryname_5_9_27`).

It is a script you run, not a library you import. It is never released as a
versioned file in `xlib/`.

## What the version numbers mean

Versions are named `major_minor_revision`:

- **Major**: primarily a chance to drop deprecated code. Gated behind enough
	breaking changes AND enough time since the previous major. Rare, by design.
- **Minor**: can add things, but must not break anything for previous users.
- **Revision**: bugfixes (or attempts at such). Fix bugs only; don't add features
	or change the API. This is the default bump.

A library's first release is always `1_0_0`; later versions are read from the
latest existing release in `xlib/`.

## How it works

It calls the bundler (`tools/pybundle/bundler.py`) to pack the dev folder's modules into
a single file. The bundler inlines internal modules (e.g. `csv_tok.py`) and renames
their functions with a module prefix (e.g. `tokenize` becomes `csv_tok_tokenize`).

It does **not** resolve imports. Cross-library dependencies must already be written
as versioned imports (`from xlib import somelib_5_9_27`) in the dev library's own
source; the bundler and release script leave those lines untouched. Import resolution
is a manual, per-library step done during development, not something the release
script does.

## Scope: no code fixes, no edits to the bundled output

The release script provides versioning only. It makes **no edits** to the file the
bundler produces: no import rewriting, no post-processing, no patching. The bundled
output is written to `xlib/` unchanged.

If the bundled output needs to change, fix the dev library or the bundler instead.
Historical `xlib/` files are never edited or deleted once released; a bug in a
released version is fixed by releasing a new revision.

## Never run this to "check" something

`release.py <library>` always writes: it computes `next_version()` from the latest
release in `xlib/` and writes the bundled output to that new path unconditionally
— there is no dry-run and no check-only mode (the only flags are `--minor`,
`--major`, `--force`). A stray verification run therefore leaves a real released
file behind; that has happened before, and the accidental revision had to be
deleted again as a test artifact. Inspect the bundler directly instead:
`python3 tools/pybundle/bundler.py <dev-folder>`.

## Future work

Carried over from `doc/plans/release-script.md` when the plan was deleted on
2026-09-30 (the work landed; the residue did not, so it lives here).

- **Export** function: folds in any `xlib` libraries used, for use outside the
	walled garden (the readme's "Export script"). Offered by the script, not
	implemented.
- **Publish-dependencies** script: each project runs one to publish its
	dependencies for `xlib` to use. What makes it knowable when an old release can
	be dropped out of `xlib/` and moved elsewhere — releases are generally not
	deleted, for legacy reasons.
- **Bundler code reuse**: the bundler's import-walking, inlining and path
	resolution could split out into a library other things use. This script is the
	first consumer that forces an API surface, so it becomes a real option now
	that the script exists.
- **Folder layout**: reorganize if the number of per-tool folders makes the tree
	cluttered.
