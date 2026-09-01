# Project rules

These rules apply to all code written in this repository. AI assistants must follow them.

## Code style

- Code is always indented with tabs.
- Function definitions and calls must remain on one line.
- Use intermediate variables to break up complex logic.
- Prefer concise code, but do not make it complicated just to be concise.
- Don't pad things with extra spaces as a blanket rule.
- Do use spaces to break math into simpler parts.
- Use guard clauses instead of nested `if`s, unless the `if` has branches.
- Code that deals with untrusted input starts with sanity checks. It returns or raises an error when those checks fail.
- No double newlines. A single blank line separates functions; keep related globals together as one block.
- Comments don't explain what code does (the code should make that clear). They explain the "why" when intent isn't obvious from the implementation.
- Splitting parts of a function into descriptively-named helpers helps readability, but weigh that against the extra clutter it adds.

## Versioning

Libraries are versioned. A versioned file is named `libraryname_major_minor_revision.py` (e.g. `net5_27_105.py`).

- Major: breaking changes. When bumped, remove deprecated stuff.
- Minor: can add things, but must not break anything for previous users.
- Revision: bugfixes (or attempts at such). Fix bugs only; don't add features or change the API.

There is currently no versioning script; the bundler needs to exist first. Neither exists yet.

## Development approach

- Each library is developed in its own folder. That folder can be imported with `from libraryname import libraryname` to get the development version.
- Users should generally not use development versions, but instead versioned releases in the `xlib` folder.
- Versioned releases can be imported either unversioned (`from xlib import libraryname`) or explicitly (`from xlib import libraryname_5_9_27`). `xlib/__init__.py` resolves an unversioned import to a version at runtime:
  - If the project has an `xlib_pins.py` in its working directory declaring `PIN = {"libraryname": "5_9_27"}`, that version is used.
  - Otherwise the latest version on disk is used, and updates to it are immediate (main projects should pin to avoid surprise breakage).
- To avoid holding off on major work before a major release, put new functionality behind feature flags or in separate functions. Existing users can then migrate gradually, and a major release is simply the point where old code is omitted from the library.
- Libraries must never use development versions of other libraries, except when that other library has no releases yet.
- When making releases, a library must never depend on an unreleased version of another library.

## Code structure

- Each library has at minimum a `<libraryname>.py` file (replace with the actual library name) where the API functions live.
- For convenience, code may be split out into separate files beyond that, but the intent is that the bundler will eventually pack the entire library into a single versioned file on release.
