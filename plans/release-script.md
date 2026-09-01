# Release script

Creates versioned bundles in `xlib/` from per-folder dev sources, using the bundler in development (`pybundle/`).

## Goal

`python3 releaser/release.py <library> [--minor|--major]` produces `xlib/<library>_<major>_<minor>_<revision>.py` and nothing else the user has to think about.

## Requirements

- Consume the bundler (whichever of `inliner.py` / `inliner2.py` wins) to pack the library folder into a single file.
- Default bump is revision (bugfix). `--minor` bumps minor, `--major` bumps major and triggers cleanup of deprecated code.
- `--minor` and `--major` are mutually exclusive.
- Read current version from the latest existing release in `xlib/`, or start at 1_0_0.
- Respect library release rules: libraries never depend on unreleased versions of other libraries (AGENTS.md). Should refuse to release if a dependency's pinned/released requirement isn't met.
- xlib_pins compatibility: the release must be importable both unversioned and pinned (`xlib.__init__` already resolves).

## Order

After the bundler is finished. Phase 0 item 2.

## Open questions

- Where does the script live? (like `xlint/` follows the tooling pattern; `xlib` folder itself is for libraries)
- Release metadata: read version "already released" vs storing an explicit version file next to dev sources.
- Does --major confirm interactively?