# Project rules

These rules apply to all code written in this repository. AI assistants must follow them.

`.agents/agent-notes-<id>.md` is a per-agent, git-ignored file for session state. `.agents/shared-notes.md` is a shared, cross-agent file for user preferences and cross-cutting context. Both survive `/new`.

Multiple agents may work in this repo at once. Coordinate through `tools/agent-coord.py`: claim files before editing, release when done, `status` to see who holds what. Claim fails if the other agent holds the same path.

## Pointers

Rules are split across files. Read the relevant one before work on that topic:

| File | What it covers |
|------|---------------|
| `doc/development.md` | The process: plan → spec → tests → implementation → review, and who owns each stage |
| `doc/library-structure.md` | Reference: library layout, release naming, import resolution, bundler name prefixing |
| `doc/tool-schema-cache.md` | Reference: the per-turn tool-schema cache in `tools/tool_schema_cache.py` — unwired, so it is a proposal rather than behaviour |
| `doc/style/architecture.md` | A/B/C/D placement, leaf modules, fork control, handed-in IO |
| `doc/style/common.md` | Maps, guard-first failures, return docs, single-pass, compatibility |
| `doc/style/python.md` | Formatting, imports, naming, type hints, declarative style |
| `doc/style/js.md` | The same, for JavaScript |
| `doc/style/markdown.md` | Markdown formatting (indentation) |
| `doc/style/prose.md` | How to explain technical things so the human can check them |
| `doc/plans/*.md` | Cross-cutting design docs, roadmap, pipeline maps; index in `doc/plans/README.md` |
| `<library>/SPEC.md` | Library map: modules, data flow, invariants, decisions |
| `personal/<person>/STATUS.md` (tracked); root `STATUS.md` is a per-person symlink (gitignored, created by `agent-coord.py personal init`). Claim/update the `personal/<person>/...` path; claims resolve symlinks by realpath. |
| `personal/<person>/HISTORY.md` (tracked) — the append-only record of what happened and when. STATUS.md states the present and only the present; anything worth reading in six weeks goes in HISTORY.md instead. Claim before appending. |

The following rules live in dedicated docs files and are also linked from the table above:

| File | What it covers |
|------|---------------|
| `doc/epiq-workflow.md` | Epiq board mechanics: per-actor writes, syncing, stranded events |
| `doc/working-tree.md` | Check-clean before editing, don't touch others' uncommitted changes |
| `doc/paths-in-tracked-files.md` | No machine-specific paths in tracked files; use repo-relative or `.agents/machine-info.md` |
| `doc/state-files-history.md` | STATUS.md vs HISTORY.md; append-only history policy |
| `doc/versioning.md` | Library versioning scheme: revision/minor/major bumps, deprecation timeline |
| `doc/development-approach.md` | Dev folders, versioned imports, VERSIONS.md |
| `doc/code-structure.md` | Entry file = public API only; internals in separate files; no `__init__.py` at library root |
| `doc/subagent-dispatch.md` | Which worker for which task category |
| `doc/human-feedback.md` | Correct the human directly when they're wrong |
| `doc/rule-change-news.md` | Run `agent-coord.py news` at session start |
| `doc/houserules.md` | taskview description length limit (3–4 lines) |
