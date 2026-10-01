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

Basis: `master` at `9ffa237` (2026-10-01). xlint clean over the whole repo.
**Nine branches are open and awaiting the human's review, and `master` did
move** — `0J8YBYH` landed the epiq workflow rules after this Snapshot was first
written, so its own "has not moved" claim was already stale. The branches carry
the 2026-09-30 doc and state work and are the merge queue — see *Awaiting
review* below. `doc/development.md` is the canonical process document — plan →
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
- **There are two epiq boards, one per repo, and 16 tickets moved between them
	on 2026-09-30.** The filing rule is that a ticket belongs on the board of the
	repo where its change lands, because that is the only board whose state
	branch can see the commit. See Pointers for the full rule and `58MXTGY` for
	the ref map.

## In progress

| Item | Who | Done | Where |
|------|-----|------|-------|
| **pybundle rewrite** | human (spec) | Spec not written yet; the agent pass is blocked on it | epiq `6MFX0Z1`, `YEBP3QB` |
| **modelbench** | — | Under active work (commits 2026-09-28/29 replaced the results catalogue with `ledger.py`); two questions left | `tools/modelbench/`, taskview #61, #63 |
| **epiq boards** | secretary | XLib 29 open (20 Todo, 9 In progress), Agents 18 open (15 Todo, 1 In progress, 2 Done); the 2026-09-30 reshuffle put every ticket on the board of the repo its change lands in | both boards |
| **xAudit tool** | — | Decided, not started | `doc/plans/xaudit.md` |
| **taskview periodic time refresh** | — | Planned only | `doc/plans/taskview-time-refresh.md` |

### Awaiting review — the merge queue

The human's decision of 2026-09-30: every piece of work goes on its own
feature branch, one commit per ticket, ref-prefixed, and **nothing merges
before the human reviews it**. Agents move finished tickets to Done themselves;
an agent may merge to master and delete the branch only after the human has
approved the ticket.

| Branch | Ticket | Size | What |
|--------|--------|------|------|
| `ym7eshs-drop-rotation-cursor` | `YM7ESHS` | 1 file, −1 | dead `ROTATION_CURSOR` constant |
| `9w4yrc6-oc-agent-validate-name` | `9W4YRC6` | 1 file, +26 | `oc-agent` validates the agent name |
| `j3kk7hd-xlint-plan-status` | `J3KK7HD` | 1 file, +5/−2 | xlint plan status corrected |
| `tvjcmtf-doc-pointer-repair` | `TVJCMTF` | 4 files, +19/−10 | pointers broken by the `doc/` move |
| `k1mx4tb-library-structure-doc` | `K1MX4TB` | 2 files, +145/−40 | library-structure doc out of AGENTS.md |
| `wkq371w-status-present-only` | `WKQ371W` | 5 files, +207/−145 | this file, plus the drift rulings |
| `vg87t14-delete-realized-plans` | `VG87T14` | 12 files, +53/−734 | eight realized plans deleted |
| `h2nc2a2-closing-after-merge` | `H2NC2A2` | 1 file, +2/−2 | say that leaving Done means closing |
| `hc1zjk6-dispatch-general-longcat` | `HC1ZJK6` | 3 files, +8/−73 | dispatch `general` to `worker-longcat` |

`gh` 2.102.0 is installed at `/usr/local/bin/gh` — official release binary, no
apt source added — and is authenticated against `Xonok` with `repo` scope. An
agent opens and merges pull requests; the human reviews. `epiq_issue_stats
<ref>` gives per-ticket size, self-churn and test lines — read it before the
diff.

**The subject format is `<REF> ` — ref, then a space.** `REF: ` does not link:
the matcher is `subject.toUpperCase().startsWith(ref + " ")`. All seven were
committed the git way first and read as zero commits; epiq's own skill never
states the separator.

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
- **The `Q397WZG` / `9J30DNW` duplicate is resolved by relocation, not by a
	merge.** Both asked which worker the coding route should name, in two
	different lanes; both are closed and refiled on the Agents board as
	`G8B6T7V` and `P1H7VM4`, where the work lands. One decision, one board.
- **epiq pending events**: ~60 events sit in four `~pending.jsonl` files and are
	committed only when that actor's own process syncs. Accepted risk, closed as
	`AZHG0FK` on 2026-09-29; the residual loss window is a worktree prune.
- **Per-ticket branching needs one fix before agents work in worktrees.**
	`.agents/` is gitignored, so a new worktree has no `claims.json` and
	`check-clean` reads the shared index — claims must resolve to the main
	checkout. Confirmed 2026-10-01: `claim` accepts a worktree path, and
	`check-clean` then refuses the same path with "paths span multiple repos".
- **The agent-file zero-stats problem was solved by filing, not by tooling.**
	`.opencode/agent/` is a symlink into the Agents repo, so an agent-file ticket
	filed on this board reads as zero commits however it is committed. 16 of them
	were refiled on 2026-09-30, which fixes the 16. What is left is that nothing
	stops the next agent filing one here again — the open half of `58MXTGY`, and
	the reason the filing rule is written into Pointers rather than left implicit.
- **Task scheduling**: 4 high-importance tasks have no due date at all (#52, #61,
	#63, #75), and everything due today has by now gone overdue — 10 open tasks
	are past due, and that number moves hourly. The store is the record; see
	`TASKS.md` for this workspace's two.

## Settled — not to be reopened without cause

- **The board is the unit of work.** The human's ruling, 2026-09-30: one ticket
	per independent piece, its own feature branch, one commit per ticket,
	subject opening with the ticket ref. **Todo** is pending, **In progress**
	means the human has ai-ok'd it, **Done** means the agent finished it. Agents
	move their own tickets to Done. A ticket leaves Done when the human reviews
	and approves it — only then may an agent merge it to master and delete the
	branch. This overrides the epiq skill on two points: Done is not "merged",
	and the merge is the agent's action once approval is given.
- **Two tracks for development** (human, 2026-09-30). Feature work keeps the
	spec pipeline; anything whose goal, scope and acceptance fit in a ticket
	description runs as a ticket-is-the-spec, which is the default. The spec
	pipeline is not abolished — it is pipelined through epiq as separate commits
	and tickets. Neither track is written into `AGENTS.md` yet: epiq `0J8YBYH`.
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
	`~/.local/share/taskview/tasks.csv`, epiq refs on either board. A taskview id
	and an epiq ref look alike and are different things.
- **Which board a ref sits on decides whether its commit can link.** XLib work →
	the XLib board. Anything touching `.opencode/agent/`, either `AGENTS.md`,
	`plans/`, `library/`, `.taskview.yaml` or `personal/` → the Agents board. The
	two are separate epiq projects with separate state branches, so a ticket
	cannot be *moved* between them: relocating means close-and-refile, and **the
	ref changes**. Set 2026-09-30; the full old→new map is on `58MXTGY`.
- Shared user context and per-agent state: `.agents/` in the Agents workspace.
- Reviews: `doc/reviews/` (read its README first). Audits: `doc/audits/`.
