# Project rules

These rules apply to all code written in this repository. AI assistants must follow them.

`.agents/agent-notes-<id>.md` is a per-agent, git-ignored file for session state. `.agents/shared-notes.md` is a shared, cross-agent file for user preferences and cross-cutting context. Both survive `/new`.

Multiple agents may work in this repo at once. Coordinate through `tools/agent-coord.py`: claim files before editing, release when done, `status` to see who holds what. Claim fails if the other agent holds the same path.

## Working on a ticket

The epiq board is where work is planned, tracked and reviewed. The lane says what state a piece of work is in:

- **Todo** — pending.
- **In progress** — the human has ai-ok'd it, meaning it is now clear how to perform.
- **Done** — the agent finished it: branch pushed, pull request open.

A ticket leaves Done when the human has reviewed the work and approved it. Only then may an agent merge it to master, delete the branch, and **close the ticket** — closing is how a ticket leaves the board, and it is the agent's step, not a second approval.

This is one point where the epiq skill differs, and the difference is deliberate: the skill puts a ticket in Done when it merges and closes it at release, because Done is the list the next release ships from. Here **Done means finished and awaiting approval**, so leaving the lane is the review and nothing else is. Closed tickets stay readable, so closing loses no record; what the release-list role is replaced by is `Z491RDN`'s patches file.

Commit under the repo's configured `user.name` / `user.email` and nothing else — no `Co-Authored-By:` line, no tool footer, no `--author` override. The git user is the sole author of every commit an agent writes; attribution belongs on the board, not in the commit.

Read the ticket's `epiq_issue_stats` before reading its diff. Size, file spread, self-churn (how much the piece spent rewriting its own work) and test lines for one ticket, which is a cheaper thing to judge than a diff is to read.

## Git access

Work lands on a **feature branch, one branch per ticket**. Git is where a ticket's change becomes reviewable; the board is what says which ticket.

An agent may `add`, `commit`, `push` a feature branch, and open a pull request for it. An agent may `merge` to master **only after the human has approved that ticket**, and then deletes the branch — as a rebase merge, never a merge commit (`gh pr merge --rebase`), so master stays a flat sequence of ref-prefixed commits and the commit↔ticket link keeps reading.

An agent may amend its own commit on a branch the human has not reviewed yet. It may not rewrite anyone else's commits, and it may not force-push master.

**Never open a stacked pull request.** A PR's base is always `master`. Opening one against another feature branch makes it a claim on that branch's lifetime, and the claim breaks silently: merging the lower PR with `--delete-branch` deletes the base and GitHub auto-closes the upper one — no conflict, no error, nothing said. That happened here to PR #11 (`9R0H6SA`), which was closed as a side effect of merging PR #1 and had to be re-cut and reopened as #12. Worse, the leftover PR then reports `CONFLICTING` / `DIRTY` for a base ref that no longer exists, which reads as a real conflict and sends the next agent to resolve a conflict that is not there.

A ticket that needs another ticket's work re-bases onto master itself: `git rebase origin/master`, resolve, and open its own PR. If the work genuinely cannot be split, branch from master and carry the dependency in a single commit under your own ref — never by stacking, and never by borrowing another ticket's ref.

**Every commit subject opens with its ticket ref followed by a space** — `YM7ESHS drop the dead constant`, not `YM7ESHS: drop the dead constant`. epiq links by `subject.startsWith("<REF> ")`; the colon breaks the match and the ticket reads as untouched work. Getting this wrong is invisible, which is the whole reason to know it by reflex. The ref comes off the MCP response's `ref` field, never derived by hand.

A commit only needs to be on a local branch to be linked — the link reads local branches, so pushing is for the human's review and merging is for the record, not for the link.

## epiq writes are per-actor

`epiq_sync` drains **only the calling actor's own** event log. Every actor writes to its own `~pending*.jsonl` in the state worktree, which `.epiq/events/.gitignore` never commits; the drain happens when a process running *as that actor* syncs.

So an actor whose process has exited strands its writes permanently, and nothing reports it. Two consequences:

- **Sync before the session ends.** A board write that has not been synced is not durable, and `epiq_sync` returning `skipped: true` means *nothing new to commit*, not *nothing to do*.
- **Check for other actors' stranded events** with `python3 tools/epiq-pending.py` (exits 1 if any project has undrained events). It reports stranded events per actor and, more importantly, board nodes that committed events reference but whose creation was never committed — a clone cannot resolve those. Run it when a board state looks wrong, when `epiq_sync` skips unexpectedly, or at session start.

Draining another actor's events needs a session that assumes that identity, which rewrites who the drain is attributed to. Ask the human before doing it.

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
| `doc/style/prose.md` | How to explain technical things so the human can check them |
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
| `general` | `worker-longcat` | Text, agentic tasks |

Main model (big-pickle) does planning, clarification, and assumption-auditing directly — do not dispatch these. Dispatch non-trivial work; do simple edits directly. Never re-add `worker-muse-spark` (Meta trains on prompts).

## Human feedback

If the human is wrong about a fact, assumption, or direction, say so directly.

## Rule-change news

Run `python3 tools/agent-coord.py news` at session start and before first subagent dispatch. It reports changed rule files and marks them seen. Prefer to mechanize rules (tool checks, bundle-time checks) over prose; use news for changes you can't mechanize.
