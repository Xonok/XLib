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

It calls the bundler (`pybundle/bundler.py`) to pack the dev folder's modules into
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
