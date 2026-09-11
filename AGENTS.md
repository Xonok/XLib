# Project rules

These rules apply to all code written in this repository. AI assistants must follow them.

`.agents/agent-notes-<id>.md` is a per-agent, git-ignored file for session state. `.agents/shared-notes.md` is a shared, cross-agent file for user preferences and cross-cutting context. Both survive `/new`.

Multiple agents may work in this repo at once. Coordinate through `tools/agent-coord.py`: claim files before editing, release when done, `status` to see who holds what. Claim fails if the other agent holds the same path.

## Git access

**Agents use read-only git commands only** (`status`, `log`, `show`, `diff`, `ls-files`, `reflog`, ...). Commands that change the repository — `commit`, `add`, `push`, `pull`, `merge`, `rebase`, etc. — are reserved for the human. If a lasting git change is needed, ask the human.

## Working tree

Don't change files that carry uncommitted changes you did not make. Before your first edit, run `python3 tools/agent-coord.py check-clean <path>` — `clean` means proceed, `dirty` means stop and name the blocked file. A file you created yourself earlier in the session is yours to keep editing. The human can override by explicit instruction.

## Pointers

Rules are split across files. Read the relevant one before work on that topic:

| File | What it covers |
|------|---------------|
| `style/architecture.md` | A/B/C/D placement, leaf modules, fork control, handed-in IO |
| `style/common.md` | Maps, guard-first failures, return docs, single-pass, compatibility |
| `style/python.md` | Formatting, imports, naming, type hints, declarative style |
| `style/markdown.md` | Markdown formatting (indentation) |
| `plans/*.md` | Cross-cutting design docs, roadmap, pipeline maps |
| `<library>/SPEC.md` | Library map: modules, data flow, invariants, decisions |
| `STATUS.md` | Master status — what exists / is in progress / is done. Claim before editing. |

## Versioning

Libraries are versioned as `libraryname_major_minor_revision.py` (e.g. `net5_27_105.py`).

- **Major**: drop deprecated code. Requires breaking changes AND time since last major. Rare.
- **Minor**: additions only; must not break previous users. "Breaking" = any change a user would need to adapt to.
- **Revision**: bugfixes only. Don't add features or change the API.
- Cosmetic issues are not bugs; fix without bumping.
- Default bump is revision. `--minor`/`--major` reset trailing numbers.
- First release is `1_0_0`; later versions read from latest in `xlib/`.
- Deprecations are marked in version terms; dropped after exactly 2 major versions.

## Development approach

- Each library is developed in its own folder with one entry point (`<libraryname>.py`). Dev folders are **not packages** (no `__init__.py`); import via `from libraryname.libraryname import ...`.
- Versioned releases import either unversioned (`from xlib import libraryname`) or explicitly (`from xlib import libraryname_5_9_27`). `xlib/__init__.py` resolves unversioned imports via `xlib_pins.py` or latest on disk.
- **Libraries never use versionless imports**, even in development. Always import explicit released versions (`from xlib import libraryname_5_9_27 as ...`).
- Each library pins its requirements as versioned imports in the dev folder. A library is never released unless all requirements are already released.

## Version history

Every versioned library keeps a `VERSIONS.md` in its dev folder: newest first, one entry per release, noting what changed. Tools and scripts that aren't versioned don't need one.

## Code structure

- Each library has a `<libraryname>.py` entry file containing only the public interface. Internal helpers go in separate files (e.g., `<libraryname>_tok.py`).
- The library root must not contain `__init__.py`. Internal subfolders (e.g., `xcsv/_/`) may have one if they're packages.

### Bundler and the public API

The bundler packs a library into one file and prefixes internal function names (e.g. `tokenize` in `csv_tok.py` becomes `csv_tok_tokenize`). Because of this:

- **Public API must be defined in the entry file**, not imported-and-re-exported. Use a thin wrapper:
  ```python
  from ._.csv_tok import tokenize as _tokenize

  def tokenize(line):
      """Split a CSV line (with // comments and quoting) into cells."""
      return _tokenize(line)
  ```
- Relative imports between a library's own modules are handled by the bundler.

## Subagent dispatch

Use `python3 tools/agent-coord.py dispatch <category>` to get the correct worker:

| Category | Worker | Use for |
|----------|--------|---------|
| `coding` | `worker-north-mini-code` | Implementation |
| `reasoning` | `worker-nemotron-ultra` | Deep analysis, architecture |
| `bulk` | `worker-nemotron-lightning` | Speed-critical, repetitive |
| `general` | `worker-ling` | Text, agentic tasks |

Main model (big-pickle) does planning, clarification, and assumption-auditing directly — do not dispatch these. Dispatch non-trivial work; do simple edits directly. Never re-add `worker-muse-spark` (Meta trains on prompts).

## Human feedback

If the human is wrong about a fact, assumption, or direction, say so directly.

## Rule-change news

Run `python3 tools/agent-coord.py news` at session start and before first subagent dispatch. It reports changed rule files and marks them seen. Prefer to mechanize rules (tool checks, bundle-time checks) over prose; use news for changes you can't mechanize.

## Module format

Module format and project rules (versioning, API/internal split, bundler behavior, tooling) are rule content and live in this file.
