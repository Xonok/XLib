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

Basis: `master` at `b7211a2` (2026-10-01). **xlint reports clean over the whole
repo, and that is narrower than it reads** — it skips every directory named
`test`, so 109 violations in tool tests are invisible to it (epi `AK633QC`).
**The release script cannot release anything** (`1ZY2Q5Q`) and **195 epiq events
are stranded, 13 of them issue creations** — both found 2026-10-01, neither
previously recorded. Read Blocked before trusting a release or the board.
**Two tickets await review** — `3EEXMRK` (bbprs `BLOCKED ON YOU` false positive,
both ways it lied, plus that tool's first test suite) on PR #21, and `FZDMC84` on
PR #23. Before them, twelve tickets of the epiq workflow and the 2026-09-30/10-01
doc and state work are on `master` as a flat rebase sequence, all closed, and
`XRVB0W5` merged as `b7211a2`. `doc/development.md` is the canonical process
document — plan → spec → tests → implementation → review, each stage entered on
the human's call.

- **Technical explanations have a rule file.** `doc/style/prose.md` — cite
	identifiers, trace rather than summarize, mark inference, state what would
	falsify the answer. Landed as `KDX7KWJ` because ordinary AI prose reads fine
	but a technical one loses the chain and comes back as word salad; the rules
	make the explanation checkable against the artifact instead. Explanation work
	goes to a step-by-step reasoning model — the small workers narrate a
	conclusion rather than deriving one.

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
| **epiq boards** | secretary | XLib 30 open (23 Todo, 1 In progress, 6 Done), Agents 18 open (15 Todo, 1 In progress, 2 Done); the 2026-09-30 reshuffle put every ticket on the board of the repo its change lands in | both boards |
| **xAudit tool** | — | Decided, not started | `doc/plans/xaudit.md` |
| **taskview periodic time refresh** | — | Planned only | `doc/plans/taskview-time-refresh.md` |

### Merging

The human's decision of 2026-09-30: every piece of work goes on its own
feature branch, one commit per ticket, ref-prefixed, and **nothing merges
before the human reviews it**. Agents move finished tickets to Done themselves;
after the human has approved a ticket an agent may merge it to master, delete
the branch, and close the ticket (epiq `H2NC2A2`).

**The queue is empty.** Twelve tickets have been through the whole loop and
`master` carries them as a flat rebase sequence with no merge commits —
`0J8YBYH` (the workflow itself), `KDX7KWJ` (prose rules), plus the 2026-09-30
doc and state work. Every commit subject opens with its ticket ref, which is what
keeps the commit↔ticket linking readable (why: `HISTORY.md` 2026-10-01, the
`9R0H6SA` entry).

`gh` 2.102.0 is installed at `/usr/local/bin/gh` — official release binary, no
apt source added — and is authenticated against `Xonok` with `repo` scope. An
agent opens and merges pull requests; the human reviews. `epiq_issue_stats
<ref>` gives per-ticket size, self-churn and test lines — read it before the
diff.

**The subject format is `<REF> ` — ref, then a space.** `REF: ` does not link:
the matcher is `subject.toUpperCase().startsWith(ref + " ")`. All seven were
committed the git way first and read as zero commits; epiq's own skill never
states the separator. A rebase merge preserves it; a merge commit would bury
it under a refless subject.

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

- **Work on a branch is not live until it merges.** Established by `HC1ZJK6`:
	the `worker-ling` → `worker-longcat` fix for `dispatch general` arrived as an
	uncommitted working-tree edit, and moving it onto a branch — which the
	workflow requires — took it out of the checkout, leaving the pin broken and
	`dispatch general` still answering "Upstream request failed". Now merged and
	verified live, but the shape of the problem is general: **anything repairing
	a running thing is unfixed for the whole review window**, which is correct
	for review and wrong for a fix. Worth deciding whether an infra repair may
	land ahead of review.
- **195 epiq events are unsynced and machine-local, and the loss is selective.**
	Measured 2026-10-01: **XLib 454 committed / 60 pending**, **Agents 113 / 135**.
	`mechanic` and `paul` have **no committed event log at all** — only
	`~pending` files, last touched 2026-09-29 — so survival depends on which actor
	authored an event. `epiq_sync` returns success with every flag false, so it
	reads as done and does nothing. **13 issue creations are stranded** (6 XLib, 7
	Agents), which means a fresh clone gets lane-moves, comments and tags pointing
	at tickets that do not exist there. **`FZDMC84`, the ticket about this, is
	itself stranded.** Mechanism — each actor writes to its own
	`<actorId>~pending*.jsonl` and only drains when a process running *as that
	actor* syncs, so an exited actor never drains. `AZHG0FK` closed this as
	accepted risk on 2026-09-29; the orphan-creation finding is worse than that
	assumed. **Anything that leans on the board being durable rests on this.**
- **`.work/` is gitignored now, and the convention travels** — **fixed
	2026-10-01** as `b7211a2` (epiq `XRVB0W5`, PR #24, merged and closed). Both
	halves of the finding below are done: `.gitignore` carries `.work/`, so
	`git add .` no longer stages a worktree as an embedded-repo gitlink, and the
	rule itself moved from gitignored `.agents/shared-notes.md` into `AGENTS.md`
	next to the branch-per-ticket rule. **Corrected 2026-10-01**: when this was
	first written it read *`.work/` is not gitignored, and it holds two live
	worktrees* — true an hour earlier, and the reason the fix landed inside the
	same session rather than after it.
- **`VERSIONS.md` entries should cite the release's epiq ref where one exists**
	(human, 2026-10-01; epiq `NCPBQ3W`). **Libraries only** — no tool has a
	`VERSIONS.md`, by standing rule. Forward, not retrofit: no release commit has
	ever carried a ref, so all six existing entries stay as they are and the first
	entry that can cite one is the next release. Mechanizable — each released file
	has exactly one adding commit, so the ref is findable via
	`git log --diff-filter=A`, and the check should validate against **git rather
	than the board**, since the board is not durable.
- **`tools/release/release.py` cannot release anything.** It resolves the dev
	folder at `ROOT / <library>`; the folders moved under `dev/` in `da1d163`
	(2026-09-17) and the script was not updated, so every library fails with an
	error naming a path that does not exist. Found 2026-10-01. All six releases in
	`xlib/` predate the move, and nothing tests the path. The safe inspection route
	the README offers in its place is broken too: `bundler.py <dev-folder>` raises
	`IsADirectoryError`, because `bundle()` takes the entry **file**. Fixing this
	first is also what gives the pybundle rewrite a path to be tested through
	(epiq `1ZY2Q5Q`).
- **pybundle agent work is blocked on the human's spec.** The new spec is being
	written **outside the repository** and there is no `PLAN.md`, so no step of the
	process is delegatable yet. The `SPEC.md` in the tree is `<!-- spec-origin:
	ai -->` and describes the bundler being replaced, not the replacement. The
	human's reasons for the rewrite — pybundle is a tool and carries no versions;
	its earlier releases were removed before ever being committed; the last agent
	on it went in circles on the complexity — are in epiq `6MFX0Z1` (why:
	HISTORY.md 2026-09-30 for the original block).
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
- **The stranded-events fix is a known small job, and is not this board's to
	decide.** The events exist and are well-formed — 13 of the 195 are just
	`add.issue` events in the wrong file. Caveat: `mechanic`'s and `paul`'s 39
	XLib events only drain if those identities run again. Filed as `FZDMC84`.
- **`check-clean` answers `clean` for every file in a worktree**, which is worse
	than refusing it. A worktree's `.git` is a *file*, so `nearest_git` walks past
	it to the parent repo and the check reads the wrong status — verified by
	dirtying a worktree file and being told `clean`. **Corrected 2026-10-01**: an
	earlier line here said `check-clean` *refuses* worktree paths with "paths span
	multiple repos". It does not; that error needs two different repos in one
	call, and `.opencode/agent/` never triggers it because `abspath` does not
	follow the symlink. Filed as `8FVW49J`.
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
- **pybundle's missing versions are a ruling, not an oversight** (human,
	2026-10-01). pybundle is an XLib tool, is not meant to have versions, and
	**did have releases that were deliberately removed before ever being
	committed**. So `doc/reviews/pybundle-23efebb3.md` §14 reading the
	`1_0_0`–`1_0_3` entries in the old `VERSIONS.md` as "fiction" drew the wrong
	inference from a right observation — the releases were real, then removed. The
	review files stay as they are; what was corrected is the reading of them, now
	in epiq `6MFX0Z1`.

## Open questions for the human

1. `dev/xprod/` — SPEC.md + VERSIONS.md, or fold into another library? Parked as
	your manual work, epiq `DCF9EHW`.
2. **Drain the 195 stranded epiq events before anything leans on the board.**
	The mechanism is understood as of 2026-10-01 — each actor drains only its own
	log, so an exited actor's writes never land — but the drain itself is not done,
	and `FZDMC84` is itself one of the stranded tickets. Asked 2026-10-01; the
	human's answer pending.
3. **Should `release.py` tag or commit a release?** It currently does neither,
	there are zero tags in the repo, and the README's scope section may mean that
	is deliberate. If deliberate it should be written down; if not it belongs in
	`1ZY2Q5Q`. Related: `Z491RDN`'s "entry written when the change reaches master"
	has no tooling behind it.
4. **PR #1 and PR #11 both rewrite STATUS.md.** They merge clean, but they are
	both state-file rewrites and one supersedes the other — the two-board split
	in #11 postdates everything in #1. Worth deciding which lands first rather
	than discovering it at merge time.
5. **Should `doc/style/prose.md` bind dispatched workers too?** The rule file
	is reachable through `AGENTS.md`, which every agent reads, but a subagent
	runs from its own prompt in `.opencode/agent/` and does not necessarily get
	`AGENTS.md` in context. If the prose rules are meant to apply to worker
	output too, that needs a mechanism; today they bind the agents that read the
	repo rules. `KDX7KWJ` closed without deciding it.

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
