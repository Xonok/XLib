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

It calls the bundler (`tools/pybundle/`) to pack the dev folder's modules into
a single file. The bundler inlines internal modules (e.g. `csv_tok.py`) and renames
their functions with a module prefix (e.g. `tokenize` becomes `csv_tok_tokenize`).

**The bundler works, and the bridge is in this file.** The from-scratch
replacement landed on 2026-10-17 (`ba063b5`, epiq `6MFX0Z1`) after the
five-phase implementation was deleted in `5e87ae8`. It exposes `main(entry, out)`
and takes a file-like sink, so the `bundle(entry) -> str` this script used to call
is bridged here rather than added to the bundler — the spec's seven functions stay
as written, which was the human's ruling on 2026-10-17.

All five libraries in `dev/` bundle and every bundle is xlint-clean, measured
2026-10-17. Nothing has been released since: the last six files in `xlib/` predate
the rewrite.

It does **not** resolve imports. Cross-library dependencies must already be written
as versioned imports (`from xlib import somelib_5_9_27`) in the dev library's own
source; the bundler and release script leave those lines untouched. Import resolution
is a manual, per-library step done during development, not something the release
script does.

## The gate: a bundle must be xlint-clean

Nothing this repository releases may carry a lint finding. The script bundles the
dev folder, runs this repository's own `tools/xlint/xlint.py` over the result, and
**refuses before writing** if anything is reported — the check goes through a
temporary file beside the release target, so a refusal leaves nothing in `xlib/`.

The rule is about *this repository's releases*, not about the bundler. The bundler
adds no findings of its own and passes through whatever the source already had, so
a bundle can legitimately arrive with a finding in it — and one that could bundle a
project this repository's style does not govern could not answer the question of
whether it is correct.

## Scope: no code fixes, no edits to the bundled output

The release script provides versioning only. It makes **no edits** to the file the
bundler produces: no import rewriting, no post-processing, no patching. The bundled
output is written to `xlib/` unchanged. **Checking it is not editing it** — the gate
above reads the result and either writes it or refuses.

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

**That inspection route is currently unavailable, and it was already wrong.**
There is no bundler to run — see *How it works* above. And while one existed, the
invocation shown was wrong: `bundle()` takes the library's entry **file**
(`dev/xcsv/xcsv.py`), not the folder, so passing `dev/xcsv` raised
`IsADirectoryError`. The consequence worth stating plainly is that **there is no
way to look at a bundle without writing one**, which is the hazard this section
exists to warn about.

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
