# Project rules

These rules apply to all code written in this repository. AI assistants must follow them.

`.agents/agent-notes-<id>.md` in this repo is a per-agent, git-ignored file that holds current state and gotchas that don't belong in the standing rules. It doesn't exist on a fresh clone; create your own near the start of a session, seeded from the reasonable initial rules below, and read it before starting work on later sessions.

Multiple opencode agents may work in this repo at once (generally two). They coordinate through `tools/agent-coord.py`:

- `python3 tools/agent-coord.py id` prints your agent id (`a1` or `a2`, auto-assigned; override with `OPENCODE_AGENT_ID`). Ids are workspace-qualified: `XLib/a1` here means slot `a1` in this repo's workspace, distinct from `Agents/a1` in the `/storage/Agents` control-panel workspace. Your session notes live in this workspace's `.agents/agent-notes-<id>.md`, not a shared file. `workspace` prints which workspace the coordinator thinks you are in; `note` prints your notes path.
- Claim a file before editing it, release it when done:
  - `python3 tools/agent-coord.py claim <paths...>` before the first edit to a file.
  - `python3 tools/agent-coord.py release <paths...>` once an edit is finished and saved.
  - `python3 tools/agent-coord.py release-all` to drop all your claims (also on session end).
  - `python3 tools/agent-coord.py status` to see who holds what.
  A claim fails with exit 1 if the other agent holds the same path, so a conflicting file is simply not yours to touch right now. Use `claim --force` only to clear a stale claim from a dead session.
- Read anything freely; only writes need claims. Don't edit files another agent holds.

## Git access

**Agents are only allowed to use read-only git commands** (`status`, `log`, `show`, `diff`, `ls-files`, `reflog`, ...). Any command that changes the repository in a lasting manner — `commit`, `add`, `mv`, `rm`, `reset`, `checkout`, `restore`, `clean`, `stash`, `switch`, `pull`, `push`, `merge`, `rebase`, `tag`, and the like — is reserved for the human. A `git clean` can destroy untracked work; never run it, not even "just to tidy up". If a lasting git change is needed, say so and ask the human to run it.

## Working tree

Don't change files that carry uncommitted changes you did not make yourself. That state is someone's work-in-progress — the human's or another agent's — and editing it blurs the commit and risks overwriting it.

- Before your first edit to a file, run `python3 tools/agent-coord.py check-clean <path>`. Exit 0 with `clean` means proceed. `dirty <path>` with exit 1 means the file has uncommitted changes: do not edit it — say you are blocked by that and name the file.
- Untracked files count as dirty: a file you did not create that the check reports is not yours to edit either.
- A file you created or modified yourself earlier in this session is your own work-in-progress; you may keep editing it. That is the "you made them" exception.
- Run the check over the whole repo before starting a task to get the baseline of what is off-limits: `python3 tools/agent-coord.py check-clean .` reports every dirty file.
- The human can override: if you are explicitly asked to work on a dirty file, the human owns the commit and has decided — proceed as told.

## Session lifecycle

Context is re-sent on every turn, so a long session grows steadily more expensive and increases the chance of hitting model rate limits. Reset it whenever the old context stops paying for itself.

- When a task finishes, check whether the next task still needs any of this session's context:
  - If not, the cheapest state is a fresh one: say so explicitly so the user can start a new session (`/new` or `/clear`), which reloads base rules and the agent file from scratch.
  - If some carryover matters (decisions, half-done files, open questions), `/compact` instead.
- Anything the next session will need belongs in `.agents/agent-notes-<id>.md`, not in the conversation. The notes file survives `/new`; the conversation does not. Write it down before recommending a reset.
- Sessions whose only remaining value is "I remember what happened earlier, but it's no longer needed" are dead weight. Suggest a reset rather than dragging the history along.

## Pointers

Rules are split across files so this file stays small and only the rules you need are loaded at a time. Read the pointed file before work that hits that topic:

- `style/architecture.md` — how the system is put together: A/B/C/D placement, leaf modules, fork control, handed-in IO.
- `style/common.md` — language-independent legibility code rules: maps/orchestration, guard-first failures, return documentation, single-pass structure, cross-platform compatibility, the legibility pass.
- `style/python.md` — Python-specific formatting, imports, naming, type hints, section titles, declarative style.
- `style/js.md` — JavaScript rules. Empty; only add rules when JS work appears in this repo.
- `plans/*.md` — cross-cutting and roadmap design docs (multi-library, or
  redesigns still in progress); `plans/bundler.md` is the exemplar for the map
  style.
- `<library>/SPEC.md` — a built library's map: current module structure, data
  flow, invariants, design decisions, plus a "Planned changes" section only
  when future work exists. Read a library's spec before working on it.

Module format and project rules (versioning, API/internal split, bundler behavior, tooling) are rule content and live in this file.

## Versioning

Libraries are versioned. A versioned file is named `libraryname_major_minor_revision.py` (e.g. `net5_27_105.py`).

- Major: primarily an opportunity to drop deprecated code. Gated behind enough breaking changes (dropping deprecated code) AND enough time since the previous major. Rare, by design.
- Minor: can add things, but must not break anything for previous users.
  "Breaking" means: any change whatsoever in project code to keep the same
  behaviour as before. Changing a default is therefore breaking unless it can
  be shown that no caller relies on the old default — and if none can be
  shown, consider requiring the argument instead (a default that nothing can
  be verified to override is a hidden requirement, not a convenience).
- Revision: bugfixes (or attempts at such). Fix bugs only; don't add features or change the API.
- Cosmetic issues that don't change behavior — e.g. a linter flag on the bundled output — are not bugs and do not warrant a release on their own. Fix them without bumping the version when reasonable.
- Default release bump is revision. `--minor` and `--major` bump theirs, resetting the trailing numbers to 0 (minor resets revision; major resets minor and revision).
- A library's first release is always `1_0_0`; later versions are read from the latest existing release in `xlib/`.
- Deprecations are marked in version terms, so that deprecated code can be dropped after exactly 2 major versions.

## Development approach

- Each library is developed in its own folder and has exactly one entry point (`<libraryname>.py`). Dev folders are **not packages** (no `__init__.py`); import the API directly via `from libraryname.libraryname import ...` (e.g., `from csv.csv import tokenize`).
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
- **Dev library folders must not contain `__init__.py`.** Only the `xlib/` releases folder has `__init__.py`. Internal modules go in a subfolder (e.g., `csv/csv/`) so imports like `from .csv.csv_tok import ...` work without a top-level package marker.

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

Four free worker models are available as subagents: `worker-mimo`, `worker-nemotron-lightning`, `worker-nemotron-ultra`, `worker-ling`. The main model (big-pickle / nemotron-3-ultra-free) is the primary rate-limit bottleneck — preserve it by offloading non-trivial work to subagents.

**Rotation is authoritative and stateful.** Run `python3 tools/agent-coord.py rotation --next` to get the model to dispatch now; it atomically returns and advances the shared cursor (`mimo` → `lightning` → `ultra` → `ling` → repeat) so agents don't guess or drift. Always consult it before dispatching a worker.

**Pick the model by the job, not by rote rotation.** Rotation only balances *planning* load; the fit of the model to the work always wins over which turn it is:

- **Coding / implementation** → `worker-mimo`. Strongest coder; use for coding by default.
- **Deep reasoning / long-context analysis / technical architecture** → `worker-nemotron-ultra` (nemotron-3-ultra-free). Best for technical tasks, structured reasoning.
- **Bulk, speed-critical, or repetitive grunt work** → `worker-nemotron-lightning`.
- **General text / agentic tasks in between** → `worker-ling`.

**Main model (big-pickle) strengths**: Best at understanding user intent, tracking implied specifications, and checking its own assumptions for false/untested claims. Use directly for planning, clarification, and assumption-auditing — do NOT dispatch these to workers.

A failed attempt from the wrong model costs more than skipping a rotation turn, but don't force a model onto a job it fits poorly just because it's the nominal default. Match the worker to the task.

**Mandatory dispatch for non-trivial work.** Before starting any non-trivial coding, reasoning, bulk, or general task, run `python3 tools/agent-coord.py dispatch <category>` to get the correct worker, then dispatch via the `task` tool with that `subagent_type`. The main model must NOT do the work itself.

**Never dispatch if not needed**: Simple, single-step tasks (quick edits, simple questions) are faster done directly by the main model than via subagent dispatch overhead.

**Concurrent dispatch**: When dispatching multiple workers simultaneously, assign different models to each.

**Meta exclusion**: `worker-muse-spark` was removed — Meta's Contributor tier trains on user prompts. Do not re-add it.

## Human feedback

**Call out errors.** If the human is wrong about a technical fact, assumption, or direction, say so directly. Do not defer to incorrect premises. Correct mistakes immediately rather than building on them.

## Rule-change news

Guidelines change, and this file (and the files it points at) is only a snapshot at your session start — it can go stale mid-session. `tools/agent-coord.py news` reports which rule files changed since you last looked, keyed to a per-agent read cursor, so you catch up on updates without re-reading everything. It hashes the rule files — `AGENTS.md`, `.opencode/agent/*.md`, `style/*.md` — plus anything else in the rule set.

- Run `python3 tools/agent-coord.py news` at the start of a session and again before your first subagent dispatch. It prints the changed files (or `no new guideline changes`) and marks them seen.
- `news --peek` reports changes without marking them seen (use it to look without committing to having absorbed them). `news --status` just prints `caught up` / `not caught up`.
- When you make a new rule or guideline yourself, tell the other agent to run `news` — do not assume it will read this file unprompted.
- A news notice only *informs*; it does not replace a mechanism. Prefer to mechanize a rule (a `tools/agent-coord.py` command, a bundle-time check) wherever you can, and use news to announce the changes you can't mechanize.