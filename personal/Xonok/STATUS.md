# XLib STATUS — master file

The current picture of this workspace: what exists, what is being worked on, what
is blocked, and what needs a decision. Present tense only — anything worth
reading in six weeks is in `HISTORY.md`. Details live behind the pointers at the
bottom; this file stays a summary.

## Convention (all agents)

- Update this file when you start or finish something, or when your progress
	estimate changes. One line per work item: what, who, % done, where to look.
- Claim `STATUS.md` before editing (`python3 tools/agent-coord.py claim
	STATUS.md`), release when done.
- Finished items are appended to `HISTORY.md`, not moved to a "Recently done"
	section here. The open list simply loses them. History is append-only:
	nothing is rewritten or removed without the human's sign-off.
- The % done number is **your own estimate of how done you think it is** — rough
	is fine, stale is not.
- Keep the Snapshot date current. It is the basis of the file, not a log.

## Snapshot

Basis: `master` at `49a9ca5` (2026-09-30). xlint clean over the whole repo. The
pointer and state-file fixes made on 2026-09-30 are still uncommitted, human
commit pending. `doc/development.md` is the canonical process document — plan →
spec → tests → implementation → review, each stage entered on the human's call.

- Libraries: `dev/` holds xconf, xcsv, xprod, xschema, xtest. `xlib/` holds
	xconf `1_0_0`, xcsv `1_0_0`/`1_0_1`/`1_1_0`, xschema `1_0_0`, xtest `1_0_0`.
	xprod is unreleased.
- SPEC.md exists for xconf, xcsv, xschema, xtest and for the marduk, pybundle
	and taskview tools. `dev/xprod/` has only a README.md.
- Nothing under `.opencode/` is tracked: `.opencode/agent` is a gitignored
	symlink into the Agents workspace (the single canonical agent set), and
	`.opencode/opencode.jsonc` and `node_modules` are ignored too. There is no
	coordinator agent file — planning and assumption-auditing belong to the main
	model.
- Live coordination state: `python3 tools/agent-coord.py status` (claims) /
	`news` (changed rule files).

## In progress

| Item | Who | Done | Where |
|------|-----|------|-------|
| **pybundle rewrite** | human (spec) | Spec not written yet; the agent pass is blocked on it | epiq `6MFX0Z1`, `YEBP3QB` |
| **modelbench** | — | Under active work (commits 2026-09-28/29 replaced the results catalogue with `ledger.py`); two questions left | `tools/modelbench/`, taskview #61, #63 |
| **epiq board** | secretary | 43 tickets open (34 Todo, 9 In progress), **0 assigned**; filing and hygiene done, implementation not started | epiq board |
| **xAudit tool** | — | Decided, not started | `doc/plans/xaudit.md` |
| **taskview periodic time refresh** | — | Planned only | `doc/plans/taskview-time-refresh.md` |

### pybundle — read this before trusting the reviews

The bundler in the tree is the five-phase implementation in
`tools/pybundle/bundler.py` + `bundler_impl.py`, and `tools/pybundle/SPEC.md`
describes that code. Seven fixtures, all passing.

A single-pass redesign was attempted on top of it and abandoned: the code's
complexity was the blocker, not the design. **The human is writing a new spec
from scratch** (epiq `6MFX0Z1`, plus the stdout constraint in `YEBP3QB`); the
rewrite follows that spec.

Two consequences for anyone reading the workspace:

- The four `doc/reviews/pybundle-*.md` reviews that approved the redesign review
	files which are not in the tree (`pybundle.py`, `BUG_FIX_SPEC.md`,
	`VERSIONS.md`, three fixtures that were never added). They are the record of
	a real attempt, not a verdict on the code that exists.
- `tools/pybundle/_/` is an empty directory left from that attempt.

## Blocked / needs attention

- **pybundle agent work is blocked on the human's spec.** Nothing should be
	started against the current bundler's structure until it lands (why:
	HISTORY.md 2026-09-30).
- **`dev/xprod/` has no SPEC.md and no VERSIONS.md** — the only dev library
	missing both. Manual work for the human, parked on purpose; recorded as epiq
	`DCF9EHW` so the gap stays visible and does not become a quiet exception.
- **`dev/xconf/`, `dev/xcsv/`, `dev/xschema/`, `dev/xtest/` use `tests/`.** The
	ruling is `test/`, recorded in `doc/development.md`; the rename is epiq
	`2VD2XZC`.
- **`tools/tool_schema_cache.py:14`** names this machine's absolute path in a
	tracked file, which AGENTS.md forbids. The linter check that would catch this
	is epiq `7HP67R2` (Todo).
- **epiq `Q397WZG` (Todo) and `9J30DNW` (In progress)** look like the same
	problem — the coding worker's model pin — filed twice in different lanes.
	Merge or split them.
- **epiq pending events**: ~60 events sit in four `~pending.jsonl` files and are
	committed only when that actor's own process syncs. Accepted risk, closed as
	`AZHG0FK` on 2026-09-29; the residual loss window is a worktree prune.
- **Task scheduling**: 4 high-importance tasks have no due date at all (#52, #61,
	#63, #75), and everything due today has by now gone overdue — 10 open tasks
	are past due, and that number moves hourly. The store is the record; see
	`TASKS.md` for this workspace's two.

## Settled — not to be reopened without cause

- **`tools/tmux-xlib.sh` killing the session is intended**, on start and on exit.
	The problem it will cause is known and recorded: once the launcher works from
	more than one repo, the default session name and the kill can no longer be the
	same string. Constraint and a suggested shape are on epiq `8VX1HVE`.
- **Versionless imports in dev-folder tests are correct** — a test imports the
	code being developed. AGENTS.md says so explicitly now; the old wording read
	as a blanket ban.
- **The four `doc/reviews/pybundle-*.md` files and the empty `tools/pybundle/_/`
	stay.** The facts are written down in `doc/reviews/README.md` and here; the
	ruling was to note them and leave the files in place.

## Open questions for the human

1. `dev/xprod/` — SPEC.md + VERSIONS.md, or fold into another library? Parked as
	your manual work, epiq `DCF9EHW`.

## Pointers

- Process: `doc/development.md`. Code rules: `AGENTS.md` + `doc/style/*.md`.
	Library structure and conventions: `doc/library-structure.md`. Library maps:
	`<library>/SPEC.md`. Plans: `doc/plans/README.md`.
- Tasks: `TASKS.md` (this workspace), taskview ids in
	`~/.local/share/taskview/tasks.csv`, epiq refs on the board. A taskview id and
	an epiq ref look alike and are different things.
- Shared user context and per-agent state: `.agents/` in the Agents workspace.
- Reviews: `doc/reviews/` (read its README first). Audits: `doc/audits/`.
