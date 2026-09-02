# Project rules

These rules apply to all code written in this repository. AI assistants must follow them.

`.agents/agent-notes-<id>.md` in this repo is a per-agent, git-ignored file that holds current state and gotchas that don't belong in the standing rules. It doesn't exist on a fresh clone; create your own near the start of a session, seeded from the reasonable initial rules below, and read it before starting work on later sessions.

Multiple opencode agents may work in this repo at once (generally two). They coordinate through `tools/agent-coord.py`:

- `python3 tools/agent-coord.py id` prints your agent id (`a1` or `a2`, auto-assigned; override with `OPENCODE_AGENT_ID`). Your session notes live in `.agents/agent-notes-<id>.md`, not a shared file.
- Claim a file before editing it, release it when done:
  - `python3 tools/agent-coord.py claim <paths...>` before the first edit to a file.
  - `python3 tools/agent-coord.py release <paths...>` once an edit is finished and saved.
  - `python3 tools/agent-coord.py release-all` to drop all your claims (also on session end).
  - `python3 tools/agent-coord.py status` to see who holds what.
  A claim fails with exit 1 if the other agent holds the same path, so a conflicting file is simply not yours to touch right now. Use `claim --force` only to clear a stale claim from a dead session.
- Read anything freely; only writes need claims. Don't edit files another agent holds.

## Session lifecycle

Context is re-sent on every turn, so a long session grows steadily more expensive and increases the chance of hitting model rate limits. Reset it whenever the old context stops paying for itself.

- When a task finishes, check whether the next task still needs any of this session's context:
  - If not, the cheapest state is a fresh one: say so explicitly so the user can start a new session (`/new` or `/clear`), which reloads base rules and the agent file from scratch.
  - If some carryover matters (decisions, half-done files, open questions), `/compact` instead.
- Anything the next session will need belongs in `.agents/agent-notes-<id>.md`, not in the conversation. The notes file survives `/new`; the conversation does not. Write it down before recommending a reset.
- Sessions whose only remaining value is "I remember what happened earlier, but it's no longer needed" are dead weight. Suggest a reset rather than dragging the history along.

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
- Imports go on one line: plain imports are comma-joined (`import argparse,ctypes,os`), `from X import Y` can't share a line with a plain `import Z`, so it naturally stays alone, but multiple things from the same `X` go on one line (`from X import Y,Z`). No space after a comma in an import line; a name containing a dot would need that separation, but dotted names get their own line anyway, so the space never helps. Imports from meaningfully different categories (standard python vs. repo-local) are separated, but without empty lines between them. Avoid wildcard imports, since they're unpredictable.
- Libraries should have a clean split between API code and internal code. The API file (`<libraryname>.py`) contains only the public interface; internal helpers go in separate files (e.g., `<libraryname>_tok.py`, `<libraryname>_ser.py`). This keeps the public surface minimal and makes internal refactoring safer.

## Versioning

Libraries are versioned. A versioned file is named `libraryname_major_minor_revision.py` (e.g. `net5_27_105.py`).

- Major: primarily an opportunity to drop deprecated code. Gated behind enough breaking changes (dropping deprecated code) AND enough time since the previous major. Rare, by design.
- Minor: can add things, but must not break anything for previous users.
- Revision: bugfixes (or attempts at such). Fix bugs only; don't add features or change the API.
- Cosmetic issues that don't change behavior — e.g. a linter flag on the bundled output — are not bugs and do not warrant a release on their own. Fix them without bumping the version when reasonable.
- Default release bump is revision. `--minor` and `--major` bump theirs, resetting the trailing numbers to 0 (minor resets revision; major resets minor and revision).
- A library's first release is always `1_0_0`; later versions are read from the latest existing release in `xlib/`.
- Deprecations are marked in version terms, so that deprecated code can be dropped after exactly 2 major versions.

## Development approach

- Each library is developed in its own folder and has exactly one entry point. That folder can be imported with `from libraryname import libraryname` to get the development version.
- Users should generally not use development versions, but instead versioned releases in the `xlib` folder.
- Versioned releases can be imported either unversioned (`from xlib import libraryname`) or explicitly (`from xlib import libraryname_5_9_27`). `xlib/__init__.py` resolves an unversioned import to a version at runtime:
  - If the project has an `xlib_pins.py` in its working directory declaring `PIN = {"libraryname": "5_9_27"}`, that version is used.
  - Otherwise the latest version on disk is used, and updates to it are immediate (main projects should pin to avoid surprise breakage).
- **Libraries never use the versionless import option, not even in development.** A library always imports other libraries' explicit released versions (`from xlib import libraryname_5_9_27 as ...`), both in development and in its released code. Versionless imports are only for throwaway scripts, where "whatever is on disk" is acceptable.
- Each library pins specific public versions of whatever it requires, **manually written as versioned imports in the dev folder**. The release script does not resolve imports for you. A library is never released unless all its requirements are already released, so a release of one library never forces changes to other libraries; consumers update their pins at their own pace. Libraries use public versions of other libraries during development too, never development or unspecified versions.

## Version history

- Every versioned library must keep a version history (`VERSIONS.md`) in its dev folder. One entry per release, newest first, noting what changed in each version. Prepend new entries to it rather than removing older ones.
- This applies to everything in the repository that gets a version. Anything that does not get a version (tools, scripts) does not need a version history either — no versions, no version history.

## Code structure

- Each library has at minimum a `<libraryname>.py` file (replace with the actual library name) where the API functions live.
- Libraries should have a clean split between API code and internal code. The API file (`<libraryname>.py`) contains only the public interface; internal helpers go in separate files (e.g., `<libraryname>_tok.py`). This keeps the public surface minimal and makes internal refactoring safer.

### Bundler and the public API

The bundler (`pybundle/bundler.py`) packs a library into one file and renames internal functions with a module prefix (e.g. `tokenize` in `csv_tok.py` becomes `csv_tok_tokenize`). Because of this:

- **Public API functions must be defined in the entry file** (`<libraryname>.py`), not imported-and-re-exported from an internal module. The bundler does not keep a clean re-exported name; it rewrites the import to the prefixed internal name.
- To give an internal function a clean public name with room for documentation, define a thin wrapper in the entry file that calls the internal one:
  ```python
  from .csv_tok import tokenize as _tokenize

  def tokenize(line):
      """Split a CSV line (with // comments and quoting) into cells."""
      return _tokenize(line)
  ```
  The wrapper keeps the clean public name, carries the docstring, and correctly delegates to the bundled internal function.
- Relative imports between a library's own modules are handled entirely by the bundler; the release script does not need to touch them.

## Tooling

Tools that live in this repo (e.g. `xlint`) follow the same development structure and code style as libraries, but are scripts you run, not things you import. They are not released as versioned files in the `xlib` folder.

- `xlint` is a style checker. Run `python3 xlint/xlint.py <paths>` to check files once; run it with `--no-<check>` to disable an individual check, or `--watch` to keep running and redraw the issue list on change (it rechecks only the files that changed).
- `release/release.py` is the release script: it assigns a version and saves a versioned file in `xlib/`, produced by calling the bundler on the dev folder. It is a thin wrapper around the bundler — it provides versioning, not code fixes, and it makes no edits to the bundler's output. Cross-library dependencies must already be written as versioned imports in the dev library. See `release/README.md`. Developed like a library but never released; owned by `release/`, not `tools/`.
- `tools/tmux-xlib.sh` is an optional launcher that runs `xlint --watch` in one pane, a shell in another, and the `skynet` agent monitor in a third. It lives in `tools/` so others can copy it to their own what-works-for-them location. It takes an optional session name as its first argument (default `xlib`); running it kills any existing session with that name on purpose.
- `tools/skynet.py` is the agent monitor. It reads opencode's message log read-only and shows how work is spread between models (message and token counts per model) plus refusal counts.
- Watcher scripts that stay open in the tmux panes should identify themselves: print `=== <Name> ===` at the top of their output (as `skynet` and `xlint --watch` do), so it's obvious which pane is which.
- A script that monitors AI usage must never itself add to it: it must not call model APIs, only read local state (e.g. opencode's SQLite log).

## Subagent dispatch

Four free worker models are available as subagents: `worker-mimo`, `worker-nemotron-lightning`, `worker-nemotron-ultra`, `worker-ling`. The main model (big-pickle) is the primary rate-limit bottleneck — preserve it by offloading non-trivial work to subagents.

**Rotation order**: `worker-mimo` → `worker-nemotron-lightning` → `worker-nemotron-ultra` → `worker-ling` → repeat. Use the next model in rotation for each new dispatch. This spreads load evenly across all models, maximizing total daily capacity.

**Override rotation when quality matters**: For complex coding tasks (multi-file edits, architectural changes), use `worker-mimo` even if it's not its rotation turn. For complex reasoning (design decisions, long-context analysis), use `worker-nemotron-ultra`. A failed attempt from the wrong model costs more than skipping a rotation.

**Never dispatch if not needed**: Simple, single-step tasks (quick edits, simple questions) are faster done directly by the main model than via subagent dispatch overhead.

**Concurrent dispatch**: When dispatching multiple workers simultaneously, assign different models to each.

**Meta exclusion**: `worker-muse-spark` was removed — Meta's Contributor tier trains on user prompts. Do not re-add it.
