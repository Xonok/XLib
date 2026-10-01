# Project rules

These rules apply to all code written in this repository. AI assistants must follow them.

`.agents/agent-notes-<id>.md` is a per-agent, git-ignored file for session state. `.agents/shared-notes.md` is a shared, cross-agent file for user preferences and cross-cutting context. Both survive `/new`.

Multiple agents may work in this repo at once. Coordinate through `tools/agent-coord.py`: claim files before editing, release when done, `status` to see who holds what. Claim fails if the other agent holds the same path.

## Git access

**Agents use read-only git commands only** (`status`, `log`, `show`, `diff`, `ls-files`, `reflog`, ...). Commands that change the repository — `commit`, `add`, `push`, `pull`, `merge`, `rebase`, etc. — are reserved for the human. If a lasting git change is needed, ask the human.

## Working tree

Don't change files that carry uncommitted changes you did not make. Before your first edit, run `python3 tools/agent-coord.py check-clean <path>` — `clean` means proceed, `dirty` means stop and name the blocked file. A file you created yourself earlier in the session is yours to keep editing. The human can override by explicit instruction.

## Paths in tracked files

A tracked file is versioned *and* synced between machines, so it must not carry one machine's layout. Name a path relative to its repo, or point at the Agents workspace's `.agents/machine-info.md`, which is gitignored precisely so it can hold machine-specific locations. The exceptions are files whose subject *is* a location — a setup walkthrough's `scp` example, a plan about another host — a path quoted as evidence, and `personal/<person>/HISTORY.md`, which is per-person and exempt. xlint ticket `7HP67R2` will flag the rest.

## Pointers

Rules are split across files. Read the relevant one before work on that topic:

| File | What it covers |
|------|---------------|
| `doc/development.md` | The process: plan → spec → tests → implementation → review, and who owns each stage |
| `doc/library-structure.md` | Reference: library layout, release naming, import resolution, bundler name prefixing |
| `doc/style/architecture.md` | A/B/C/D placement, leaf modules, fork control, handed-in IO |
| `doc/style/common.md` | Maps, guard-first failures, return docs, single-pass, compatibility |
| `doc/style/python.md` | Formatting, imports, naming, type hints, declarative style |
| `doc/style/js.md` | The same, for JavaScript |
| `doc/style/markdown.md` | Markdown formatting (indentation) |
| `doc/plans/*.md` | Cross-cutting design docs, roadmap, pipeline maps; index in `doc/plans/README.md` |
| `<library>/SPEC.md` | Library map: modules, data flow, invariants, decisions |
| `personal/<person>/STATUS.md` (tracked); root `STATUS.md` is a per-person symlink (gitignored, created by `agent-coord.py personal init`). Claim/update the `personal/<person>/...` path; claims resolve symlinks by realpath. |
| `personal/<person>/HISTORY.md` (tracked) — the append-only record of what happened and when. STATUS.md states the present and only the present; anything worth reading in six weeks goes in HISTORY.md instead. Claim before appending. |

## State files and history

`STATUS.md` states the present: current state, current blockers, current next action. No dated retrospective narrative, no "previously", no "this was wrong because", no superseded states, no "Recently done" section — all of that is `HISTORY.md`. A one-line pointer (`(why: HISTORY.md 2026-09-27)`) is allowed when the reason is load-bearing *right now*.

Finished items are appended to `HISTORY.md` and the status file's open list simply loses them. History is append-only: entries are never rewritten or removed without the human's sign-off, and a correction is a new entry naming the one it supersedes. The Agents workspace holds the full policy and the entry format; see its `plans/history-files.md`.

## Versioning

Libraries are versioned `<library>_<major>_<minor>_<revision>.py`. Bump **revision** by default — bugfixes only, no features, no API change. **Minor** for additions that don't break previous users. **Major** only to drop deprecated code, and only with both breaking changes and time since the last major. Cosmetic fixes need no bump. Deprecations are marked in version terms and dropped after exactly 2 major versions.

## Development approach

- Each library has its own dev folder with one entry point; dev folders are **not packages** (no `__init__.py`).
- **Libraries never use versionless imports**, even in development — always an explicit released version (`from xlib import libraryname_5_9_27 as ...`). Tests are the exception: a test in a dev folder imports the library under development unversioned, because testing the code being developed is the point.
- A library pins its requirements as versioned imports, and is never released unless all of them are already released.
- Every versioned library keeps a `VERSIONS.md` in its dev folder: newest first, one entry per release, noting what changed. Tools and scripts that aren't versioned don't need one.

## Code structure

- The entry file holds **only the public interface**, and the public API is *defined* there — never imported from an internal module and re-exported, because the bundler would prefix the name out from under its callers. Internals go in separate files (`<libraryname>_tok.py`).
- No `__init__.py` at a library root. Internal subfolders (e.g. `xcsv/_/`) may have one if they're packages.

## Library structure

How a library is laid out, how a release is named and resolved, and what the bundler does to names: `doc/library-structure.md`.

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
