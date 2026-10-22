# Project rules

These rules apply to all code written in this repository. AI assistants must follow them.

`.agents/agent-notes-<id>.md` is a per-agent, git-ignored file for session state. `.agents/shared-notes.md` is a shared, cross-agent file for user preferences and cross-cutting context. Both survive `/new`.

Multiple agents may work in this repo at once. **A worktree per ticket is the boundary** — each agent works in its own checkout, so two agents cannot edit one file in one place. Before a first edit, run `python3 tools/agent-coord.py check-clean <path>` — `clean` means proceed, `dirty` means stop and name the blocked file. **There is no file-claim mechanism**: the one this repository had until 2026-10-21 keyed claims by absolute path, which a worktree changes without changing the file, so one file had two claim keys that could not collide, and nothing checked a claim at commit time, so it protected nothing the filesystem was not already protecting.

**Testing**: the repository's testing solution is `xtest` (`dev/xtest/`), and
standardising on it means eventually using only xtest. Two rules: **rewrite to
xtest if it gets in the way** — when a test needs something xtest cannot do,
xtest grows — and **always write new tests with xtest**. Never start a new
`unittest` suite here. `doc/development.md` has the detail.

**Merging**: the human reviews anything that could break something. A change that breaks nothing — documentation, comments, formatting — may be merged without review: open the PR, merge it, and say so on the ticket. (Human, 2026-10-19: *"For things that don't break anything, you can merge without my review."*)

**For the model benchmark, "breaks nothing" includes changing the grades.** (Human, 2026-10-20: *"Changing grades based on current knowledge is fine and doesn't need a PR. A breaking change for benchmarking would be changing previous measurement results after the fact. Adjusting judgements as more results come in is fine."*) So a fix to a gate, a repair to the harness mapping or a new episode may be merged without review — it changes what the grades *will* be, not what they *were*. **What would break is rewriting a measurement already recorded**: the traces and the ledger rows are the record, corrections are new records beside old ones, and a row that turns out to have been an artefact stays on disk with its disposition stated.

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
| `doc/style/html.md` | The same, for HTML |
| `doc/style/markdown.md` | Markdown formatting (indentation) |
| `doc/style/prose.md` | How to explain technical things so the human can check them |
| `doc/plans/*.md` | Cross-cutting design docs, roadmap, pipeline maps; index in `doc/plans/README.md` |
| `<library>/SPEC.md` | Library map: modules, data flow, invariants, decisions |
| `personal/<person>/STATUS.md` (tracked); root `STATUS.md` is a per-person symlink (gitignored, created by `agent-coord.py personal init`). **Written by the secretary at merge time, not carried on feature branches** — a Done ticket does not carry the state files. |
| `personal/<person>/HISTORY.md` (tracked) — the append-only record of what happened and when. STATUS.md states the present and only the present; anything worth reading in six weeks goes in HISTORY.md instead. **Also written by the secretary at merge time**, for the same reason. |

The following rules live in dedicated docs files and are also linked from the table above:

| File | What it covers |
|------|---------------|
| `doc/epiq-workflow.md` | Epiq board mechanics: per-actor writes, **sync twice — a sync that reports `skipped` has not drained anything**, stranded events |
| `doc/working-tree.md` | Check-clean before editing, don't touch others' uncommitted changes; **a worktree per ticket is the boundary, and the file-claim mechanism is gone**; **`git checkout` is banned** — use `git switch` / `git restore`, and prefer a worktree to switching at all. **`git reset --hard` and `git reset --merge` are banned**; plain `git reset` is allowed but it resets the index, so it silently unstages another agent's work |
| `doc/paths-in-tracked-files.md` | No machine-specific paths in tracked files; use repo-relative or `.agents/machine-info.md` |
| `doc/personal-data.md` | No personal identifiers in tracked files or board text — no private projects, no other people's names, nothing that only makes sense on this machine; the values live outside the repository, and xlint checks the tracked files against the list there |
| `doc/state-files-history.md` | STATUS.md vs HISTORY.md; append-only history policy; **who writes them, and when — the secretary, at merge time** |
| `doc/versioning.md` | Library versioning scheme: revision/minor/major bumps, deprecation timeline |
| `doc/development-approach.md` | Dev folders, versioned imports, VERSIONS.md |
| `doc/code-structure.md` | Entry file = public API only; internals in separate files; no `__init__.py` at library root |
| `doc/subagent-dispatch.md` | Which worker for which task category |
| `doc/human-feedback.md` | Correct the human directly when they're wrong |
| `doc/rule-change-news.md` | Run `agent-coord.py news` at session start |
| `doc/houserules.md` | taskview description length limit (3–4 lines) |
