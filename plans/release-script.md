# Release script

Creates versioned bundles in `xlib/` from per-folder dev sources, using the bundler in development (`pybundle/bundler.py`). Implemented as `release/release.py`; the notes below describe the current design.

## Goal

`python3 release/release.py <library> [--minor|--major]` produces `xlib/<library>_<major>_<minor>_<revision>.py` and nothing else the user has to think about.

## Form

- `release/release.py` — folder name equals the python file name. It is developed like a library (own folder, same code style) but is never itself released, like `xlint/`. Avoids "doer" names.
- The release script does **not** test behavior of its output. The bundler is required to never change behavior; any case where it does is a bundler bug. So the script's own verification is minimal.

## Requirements

- One entry point per library (the `release/<library>/<library>.py` dev entry).
- Default bump is revision (bugfix). `--minor` bumps minor (and resets revision to 0); `--major` bumps major (and resets minor+revision to 0). `--minor` and `--major` are mutually exclusive.
- Read current version from the latest existing release in `xlib/`, or start at `1_0_0` for the first release (no special tracking needed — the first is always 1_0_0).
- Dependency pinning: each library pins specific public versions of whatever it requires. A library **cannot be released unless all its requirements are already released** — the script refuses otherwise. This means updating one library never forces changes to others; consumers update their pins at their own pace. Libraries never use dev versions of other libraries during development either.

## Major releases

Major is friction, deliberately rare, and is primarily an opportunity to drop deprecated code (feature work generally doesn't need a major). A `--major` release is gated behind **both**:

1. Enough breaking changes — specifically, dropping deprecated code. Deprecations are marked in version terms so they can be dropped after exactly 2 major versions.
2. Enough time having passed since the previous major version.

Mechanics: a `--major` is refused if the previous major release is younger than a minimum age (`_MAJOR_MIN_AGE_MONTHS`). Use `--force` to override the age gate. The exact age threshold is a policy knob set in the script.

## Publish-dependencies script

Each project needs a script it can run to publish its dependencies for xlib to use. This makes it knowable when it is safe to drop an old release out of the `xlib/` folder and move it elsewhere (for legacy reasons, releases are generally not fully deleted). In scope eventually; see Future work.

## Future work

- **Export** function: folds in any xlib libraries used, for use outside the walled garden (readme's "Export script"). Offered by the script but not implemented yet.
- **Publish-dependencies** script (see above).
- **Bundler code reuse**: some of the bundler's pieces (import-walking, inlining, path resolution) could be split out into a library for other things to use. Not valid until the release script exists — the release script is the first consumer that forces an API surface out of the bundler. After it lands, this becomes a real option.
- Reorganize folders if the number of libraries makes the per-tool folders clutter.

## Order

After the bundler is finished. Phase 0 item 2.
