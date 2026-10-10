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

Basis: `master` at `6963c52` (2026-10-08). **xlint reports clean over the whole
repo, and that is narrower than it reads** — it skips every directory named
`test`, so 109 violations in tool tests are invisible to it (epi `AK633QC`).
**The release script cannot release anything** (`1ZY2Q5Q`) — found 2026-10-01,
not previously recorded. Read Blocked before trusting a release. **195 epiq
events were stranded on 2026-10-01, 13 of them issue creations**; the drain ran
on 2026-10-02 and `tools/epiq-pending.py` reports **1 event still stranded**
(a bare `create.contributor` carrying no ticket content), confirmed 2026-10-08.
**The merge queue is empty again.** Four tickets were approved by the human on
2026-10-08 and merged as a flat rebase sequence, no merge commits:
`AFVAWRX` (#26), `3EEXMRK` (#21), `FZDMC84` (#23), `4N5J1AS` (#25). Before them,
six merged on 2026-10-02 — `58MXTGY`, `EY72YA9`, `X06YVNP`, `CMGDFZF`, `0ZSB1DP`,
`PMRBFR3` — and twelve before that. `doc/development.md` is the canonical process
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
	branch can see the commit. See `AGENTS.md` under *Working on a ticket* for
	the rule and `58MXTGY` for the ref map.

## In progress

| Item | Who | Done | Where |
|------|-----|------|-------|
| **pybundle rewrite** | human (spec) | Spec not written yet; the agent pass is blocked on it | epiq `6MFX0Z1`, `YEBP3QB` |
| **modelbench** | — | Under active work (commits 2026-09-28/29 replaced the results catalogue with `ledger.py`); two questions left | `tools/modelbench/`, taskview #61, #63 |
| **epiq boards** | secretary | XLib 31 open (28 Todo, 2 In progress, 1 Done), Agents 18 open (15 Todo, 1 In progress, 2 Done); the 2026-09-30 reshuffle put every ticket on the board of the repo its change lands in | both boards |
| **xAudit tool** | — | Decided, not started | `doc/plans/xaudit.md` |
| **taskview periodic time refresh** | — | Planned only | `doc/plans/taskview-time-refresh.md` |

### Merging

The human's decision of 2026-09-30: every piece of work goes on its own
feature branch, one commit per ticket, ref-prefixed, and **nothing merges
before the human reviews it**. Agents move finished tickets to Done themselves;
after the human has approved a ticket an agent may merge it to master, delete
the branch, and close the ticket (epiq `H2NC2A2`).

**The queue is empty.** The 2026-10-02 run held six and merged them as a flat
rebase sequence, in dependency order and not in approval order: `58MXTGY` (the
filing rule, so it governs the rest), then `EY72YA9` before `X06YVNP` — the
pane-side id prefix was rebased onto the resolver-side commit, because `X06YVNP`'s
own ticket says an id in the pane that nothing can resolve is worse than no id —
then `CMGDFZF` and `0ZSB1DP`, which are independent, then `PMRBFR3` last so the
stricter `.md` rule landed on top of everything the other five wrote. A second
run on 2026-10-08 merged four more — `AFVAWRX`, `3EEXMRK`, `FZDMC84`, `4N5J1AS` —
all approved by the human that morning and all rebased first, because three of
the four rewrote `STATUS.md` from the same old base and conflicted with each
other; oldest basis went first so the newest reconciliation landed last. Every
commit subject opens with its ticket ref, which is what keeps the commit↔ticket
linking readable (why: `HISTORY.md` 2026-10-01, the `9R0H6SA` entry).

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
- **pybundle agent work is blocked on the human's spec, and the spec arrived
	2026-10-08 but is not finished.** `79acddf` brought `tools/pybundle/SPEC_new.md`
	(215 lines) in from outside the repository — a single-pass inliner replacing
	the 5-phase Context-based bundler, and its own commit subject says *"Needs
	more work."* There is still no `PLAN.md`, so no step of the process is
	delegatable yet. The old `tools/pybundle/SPEC.md` (`<!-- spec-origin: ai -->`)
	describes the bundler being replaced, not the replacement, and both files now
	carry a similar name — worth settling which one is `SPEC.md` before an agent
	reads the wrong one. The human's reasons for the rewrite — pybundle is a tool
	and carries no versions; its earlier releases were removed before ever being
	committed; the last agent on it went in circles on the complexity — are in epiq
	`6MFX0Z1` (why: HISTORY.md 2026-09-30 for the original block).
- **`dev/xprod/` has no SPEC.md and no VERSIONS.md** — the only dev library
	missing both. Manual work for the human, parked on purpose; recorded as epiq
	`DCF9EHW` so the gap stays visible and does not become a quiet exception.
- **taskview #96 is ruled and blocked.** The human settled four things on
	2026-10-08: a separate `description` column on `tasks.csv`; exactly 2 tasks in
	full detail with the remaining pane space going to the condensed list; and
	the 2 always being the most urgent by due date (overdue first), regardless of
	day. Blocked on `AQQNPAN` — the CSV header declares 5 columns against 8-field
	rows, so a 9-column writer would land on a file whose header lies — and on
	the human's ruling that every other open taskview ticket lands first. Board:
	epiq `XNTVCEE` (Todo). The `description` field also collides with `E5MH4S2`'s
	open `priority`-column question; both grow the same file.
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
- **A stranded event is invisible on the machine holding it, which is why this
	went unnoticed for three days.** `epiq_issue_get` returned `GBNEWPS` as closed
	with a `Solution:` comment, and `QN1N82Y` as a filed ticket in Todo — both
	sourced from the on-disk pending file, **neither in any committed log**. A
	fresh clone therefore had no `QN1N82Y` at all, and had `GBNEWPS` open in Todo
	with no `Solution:` comment: an implemented, spec-backed xlint rule reading as
	work never started. The detector in `FZDMC84` compares pending against
	committed but cannot tell "this machine can see it" from "this is durable".
- **epiq pending events are drained; `AZHG0FK`'s "accepted risk" ruling is
	over.** 195 events were stranded on 2026-10-01 — XLib 454 committed / 60
	pending, Agents 113 / 135, with `mechanic` and `paul` holding *no* committed
	log at all — and 13 of them were `add.issue`, so a fresh clone got lane-moves
	and comments pointing at tickets that did not exist there. The named
	orphans were `CMGDFZF`, `VTJVHMY` and `QN1N82Y`, all three resolved
	2026-10-02. `epiq_sync` returns success with every flag false, so it reads as
	done and does nothing. The drain ran on 2026-10-02;
	`tools/epiq-pending.py` reports **1 event still stranded** as of 2026-10-08
	(a bare `create.contributor` carrying no ticket content).
	`AZHG0FK` assumed the loss window was a worktree prune — a missing creation
	with committed events referencing it is more severe than that. Draining
	another actor needs a session running as that actor, which `epiq_actor_assume`
	refuses unless the server was launched with that name. The mechanism is
	per-actor and has no fix: each actor writes to
	`.epiq/events/<actorId>~pending*.jsonl`, which `.gitignore` deliberately never
	commits, and `epiq_sync` only ever drains the calling actor's own log.
- **Two worktree hazards, both reproduced 2026-10-08.** `check-clean` answers
	`clean` for a dirty file in a worktree — a worktree's `.git` is a *file*, so
	`nearest_git` walks past it to the parent repo and reads the wrong status
	(`8FVW49J`). And `.agents/` is gitignored, so a fresh worktree has no
	`claims.json` and claims resolve to the main checkout only. **Corrected
	2026-10-08**: an earlier line here said `check-clean` *refuses* worktree paths
	with "paths span multiple repos". It does not; that error needs two different
	repos in one call, and `.opencode/agent/` never triggers it because `abspath`
	does not follow the symlink.
- **The agent-file zero-stats problem is ruled against, not just fixed.**
	`.opencode/agent/` is a symlink into the Agents repo, so an agent-file ticket
	filed on this board reads as zero commits however it is committed; 16 were
	refiled on 2026-09-30, which fixes the 16. The filing rule — file on the board
	of the repo where the change lands, decided by which repo versions the file —
	now lives in `AGENTS.md` under *Working on a ticket*, which is read before a
	ticket is filed rather than after. What it cannot do is catch a ticket filed
	without it: the choice is made through the epiq MCP, not through a repo tool,
	so nothing local can intercept it. That is the one rule here left as prose.
- **The best column alignment in this repo is module-docstring prose, not code.**
	`dev/xcsv/xcsv.py:24-30` and `xlib/xcsv_1_1_0.py:97-103` line up five
	exception names with literal `#` characters **inside a `"""` docstring**,
	where Python sees no comment at all. Found 2026-10-09 while re-measuring the
	alignment ruling, and it is the cause of two wrong figures I reported earlier
	this session: the masking handled single-line strings but not docstrings, so
	those 10 lines were counted as aligned code comments. `doc/style/python.md` has
	no sentence on docstrings — formatting, length, or what belongs in one rather
	than in the SPEC. Same shape as `DDRBHD5`/`BX56XRY`/`13QYCT8`/`KJKEQ01`: a
	convention in wide use with no text behind it. epiq `HRGFRWX` (Todo).
- **Houserule ruled 2026-10-09, second half: alignment counts only at very high
	comment density, and a comment belongs on the line before what it explains.**
	Aligned same-line comments count only where **comment density is very high**;
	inline comments should **usually be avoided** in favour of a preceding line;
	and the single space applies **only to inline comments**, i.e. to those allowed
	to stay inline at all. Such cases are rare because high comment density is
	itself often a violation of *comments are for why, not what or how*.
	**Corrected 2026-10-09, twice.** I first reported all 134 aligned comments as
	violations, then 31-in-9-blocks as legitimate; both were wrong because the
	docstring masking missed. Corrected: **91 lone inline comments** (74 of them
	`def`-line comments owned by `HRCQSV4`, **17** on ordinary code) and **5 real
	blocks** of 2+, not 9 — and **2 of the 5 are already single-spaced and
	compliant**. The ruling's default is existing practice: **528 of 663** tracked
	Python comment lines (79%) already sit on their own line. epiq `BSFQYPF`.
- **Houserule ruled 2026-10-09: spaces are never used for alignment.** Tabs if
	alignment is wanted; avoid alignment where possible. A spilled function
	signature becomes ordinary tab indentation, not columns — `func(` alone,
	arguments one tab deeper, `)` at the `func(`'s own indent — because
	**renaming a parameter breaks a space alignment and cannot break an
	indent**; that fragility is the stated reason. **Not yet written down**:
	`AGENTS.md`'s `## Houserules` (`:137-139`, one entry) and
	`doc/style/python.md` are both untouched, and the `0P2TVAM` precedent put that
	houserule in both files. Measured scope: **369 lines in 47 tracked files** —
	134 `.py` space-aligned comments, 135 Markdown alignment prose/tables,
	100 other (epi `BSFQYPF`; reformat `F8XBH1F`). Two questions the ruling does
	not answer: **comment columns** (the biggest category, and the fragility
	argument applies to them as much as to signatures) and **Markdown tables**,
	where tabs do not render as padding so "use tabs" has no working answer.
	Three xlint tickets now hang off this ruling: `BSFQYPF`, `13QYCT8` (whose
	`code  +#` exemption the ruling deletes — outside data a double space is a
	typo by construction), and `1YPFZYH`.
- **xlint's `check_def_one_line` is wrong in 74 of 74 cases.** It reports
	"function definition split across lines" for **74** `def`s across tracked
	`.py` and **none** are spills — every one is a single-line `def` carrying a
	trailing comment, because the closing pattern is anchored `\s*$` (`:130-140`).
	A 100% false-positive rate, and all 74 sit in `tools/taskview/test/`, which
	`AK633QC` shows is invisible to a plain `xlint .`. It also **bans the exact
	tab-indented signature shape the new houserule permits**, so the ruling and
	the check cannot both stand and the check cannot be the survivor. The
	trailing-comment fix is one line and converts 74 findings to 0 — worth
	landing before any redesign. **Split 2026-10-09**: the human ruled the 74
	lines are bad taste but not spills, so the one-line false-positive fix stays
	here and the new rule is `HRCQSV4` — where **`class` lines turn out never to
	have been checked at all** (`_DEF_PREFIX_RE` matches `def` only), so the 0
	count is a coverage gap rather than a clean baseline. epiq `1YPFZYH` + `HRCQSV4`
	(Todo).
- **xlint runs `check_trailing_whitespace` on `.py` and not on `.md`.**
	`check_file` (`:198-222`) branches by suffix: five checks for `.py`, two for
	`.md`. So Markdown hard breaks — two trailing spaces, a documented CommonMark
	feature — are permitted by omission rather than by decision, and **58 tracked
	`.md` lines carry trailing whitespace, 56 of them exactly two-or-more spaces**.
	Corrected 2026-10-09: I first wrote that this contradicted the double-space
	check; it does not, because the check is simply absent on `.md`. epiq
	`KJKEQ01` (Todo).
- **xlint has no mid-line double-space check, and the rule as stated would
	fight the repo's own comment alignment.** Not implemented — no check, no
	`--no-` flag. The human's condition is that it **must not fire inside data**
	(inline strings and the like), and that condition is most of the ticket: a
	prototype goes **116 → 586** findings repo-wide, of which **134 are the
	`ClassName    # comment` column layout** used across `dev/xcsv`, `xlib/` and
	`dev/xschema` — house style, not sloppiness. 120 more are SPEC.md alignment
	prose, 94 are string literals, 7 Markdown tables, 5 inline code spans. So
	exempting "data" is a **ruling, not a detail**, and the rule is unwritten:
	`doc/style/*.md` has no double-space sentence at all, and on the narrow
	sentence-period reading (`[.!?:]  +[A-Za-z]`) the repo is already clean at
	zero hits. Two implementation findings worth keeping: exempt by
	**replacement, never deletion** (deleting `` `<REF> ` `` from
	`...is \`<REF> \` — ref...` leaves two spaces and the line explodes: 1879 vs
	586 findings), and `_fence_exempt` (`:81-120`) is already built for the `.md`
	branch but feeds only `check_space_indent_exempt`. epiq `13QYCT8` (Todo).
- **xlint has no check for a single trailing blank line, and its two
	file-ending checks do not compose into the rule either states.**
	`check_final_newline` (`tools/xlint/xlint.py:142-145`) requires the file to
	end in a newline and `check_double_blank` (`:50-55`) rejects two consecutive
	blanks — so `import os\n\n` passes both, being a real last line, one blank,
	and a present terminator. Two blanks at the end *is* caught, which is the tell
	that `\n\n` is an oversight and not a policy. **Four tracked files carry it**,
	none currently flagged: `tools/taskview/taskview.py:765`,
	`tools/taskview/taskupdate.py:298`, `tools/bbprs/README.md:193`,
	`doc/reviews/pybundle-review.md:336` — the tool's own two entry points
	included. A prototype adds 4 findings repo-wide (116 → 120) and loses none.
	Same root as `DDRBHD5`: each check was written against its own symptom rather
	than against the rule, so neither composes. Also unenumerable — neither
	`missing final newline` nor this has a sentence in `doc/style/python.md`.
	epiq `BX56XRY` (Todo).
- **xlint's merged-imports rule is unsatisfiable for aliased imports.** The
	human ruled on 2026-10-09: **aliased imports get their own line, and should
	generally be avoided where avoidable — but xlint must handle them
	correctly.** The code change is now unambiguous (detect ` as ` explicitly,
	give aliased imports a branch, `prev_plain = False` so they do not
	propagate), and a prototype is inert on tracked code: 116 findings before and
	after, byte-identical. The ruling's second half is still open — whether
	"avoided when possible" is prose or a new check; mechanically it means "the
	alias never appears", which would fire on `import numpy as np` everywhere.
	`check_imports` (`tools/xlint/xlint.py:190`) decides plain-vs-dotted by
	testing the module text for a dot, and `import x as y` has no dot — so an
	aliased plain import is classified plain, flagged, and propagated as a
	mergeable predecessor. `import json` / `import math as m` /
	`import collections` produces two findings and **no rewrite that clears
	them**; the merged form `import json,math as m,collections` is legal Python
	(`ast.parse` accepts it, binds `json`/`m`/`collections`) but still reads as
	plain under the classifier. The two aliased forms are treated oppositely for
	no reason but the dot: `import a.b as c` escapes the rule, `import math as m`
	does not. `doc/style/python.md:20-23` covers plain and dotted and says nothing
	about aliases, which is how the linter filled the gap on its own.
	**Corrected 2026-10-09**: an earlier entry here said two shipped fixtures
	already violate it, making this non-latent. Wrong — both fixture findings are
	unrelated (`stdlib/main.py:3` is a plain/plain pair with the alias *after* it;
	`alias/main.py:3` is the `from`-import same-module check), so the
	unsatisfiable input has **zero occurrences in tracked code**. `tools/xlint/`
	has no test file at all, which is how it went unnoticed. epiq `DDRBHD5`
	(Todo).
- **xlint does not lint tests, and the house rule for test folder names is
	inverted relative to it.** `is_ignored` (`tools/xlint/xlint.py:28`) excludes any
	path part named `test` — the repo's own convention, so `xlint .` skips every
	test file and reports 0 while 109 violations sit in `tools/taskview/test/`
	(103), `tools/pybundle/test/` (5) and `dev/xprod/test/` (1). `tests/` — the name
	the rules call wrong — is *not* excluded, so `2VD2XZC`'s rename would move
	four linted libraries out of coverage. Needs a decision: narrow the
	exclusion to foreign test data, or write down that tests are exempt.
	`AK633QC`; `XCKN0AT`'s pre-commit hook inherits it verbatim.
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
- **`tools/tmux-xlib.sh` killing the session is intended**, on start and on exit —
	the panel takes down everything it started, so nothing is left running in the
	background. What it needs to be safe is a session name that means something: the
	name is derived from the target repo's path, so one repo's launch cannot kill
	another's panel. epiq `5DZ8NB1`. The live session named `xlib` predates that and
	is not what the XLib launcher opens any more.
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
2. **`Z491RDN` — is the patches file generated at release or hand-maintained at
	merge?** Generating it from `git log <prev-tag>..<tag>` cannot drift; a
	hand-kept file drifts by exactly the amount nobody remembered. Recorded
	because it is a design decision with reasoning that does not belong only in
	a conversation. Does Traveller tag releases? Without a boundary the patch
	notes cannot be sliced.
3. **The last stranded epiq event needs a session, or it needs epiq changed.**
	The mechanism is understood — per-actor logs, and `epiq_actor_assume` refuses a
	name its server was not launched with — so this is no longer a mystery but a
	decision: one session per stranded actor, which means the human launching it,
	or a change to epiq itself. **1 event remains stranded**, a bare
	`create.contributor` for an actor that registered and stopped, carrying no
	ticket content (`tools/epiq-pending.py`, 2026-10-08). Low stakes as a number;
	it stays open because the *mechanism* has no fix, and the next agent to exit
	without syncing restarts the count.
4. **Should `release.py` tag or commit a release?** It currently does neither,
	there are zero tags in the repo, and the README's scope section may mean that
	is deliberate. If deliberate it should be written down; if not it belongs in
	`1ZY2Q5Q`. Related: `Z491RDN`'s "entry written when the change reaches master"
	has no tooling behind it.
5. **Three pull requests rewrote `STATUS.md` from the same base, and merging them
	meant three hand-resolutions.** They conflicted because each was written as a
	snapshot of the moment before its own merge, so the merged file had to pick one
	version of every shared claim. That happened twice already (#1/#11, then this
	run) and will happen again while state-file rewrites are a per-ticket
	deliverable. Worth deciding whether a STATUS.md rewrite is a ticket of its own
	or a final step of the merge, since the second stops two agents racing for it.
5. **Should `doc/style/prose.md` bind dispatched workers too?** The rule file
	is reachable through `AGENTS.md`, which every agent reads, but a subagent
	runs from its own prompt in `.opencode/agent/` and does not necessarily get
	`AGENTS.md` in context. If the prose rules are meant to apply to worker
	output too, that needs a mechanism; today they bind the agents that read the
	repo rules. `KDX7KWJ` closed without deciding it.
6. **`xlib_dev` is approved and building** (taskview #112, human 2026-10-10).
	Three questions I raised are now closed: it uses an `__getattr__` mirror of
	`xlib/__init__.py` rather than a file per library; the "released never depends
	on dev" enforcement splits into **#113** (xlint gains repo-specific rules) →
	**#114** (the actual rule), plus **#115** (release.py refuses a library with
	a dev dependency) — and the human corrected my framing there, which had been
	wrong: **dev → dev dependency is fine and wanted**, only the dev → release
	boundary is policed. Work is on a separate branch so the other agent's
	in-flight xlint changes on master are left alone.
7. **Correction: there is no broken namespace-package import in `dev/`.** I told
	the human on 2026-10-10 that `import dev.<lib>` was unreliably importable on
	py3.14 and built an mtime/`FileFinder` theory on top of it. All of it was my
	own typo — I wrote `dev.xlsx.xlsx` (`dev` + `xlsx`) instead of
	`dev.xcsv.xcsv` (`dev` + `xcsv`). There is no `dev/xlsx`, so every failure was
	an honest `ModuleNotFoundError` for a directory that does not exist, and the
	mechanism I attributed to it was never exercised. Verified 10/10 in every
	configuration afterwards. No `__init__.py` is needed and no restructuring of
	`dev/` is required. **Why it matters beyond this task:** the failure mode was
	an unverified premise promoted to a confident root cause, with real-looking
	detail attached. A "not reproducible, here is my theory" report should have
	come first, and the cheapest check — printing the string I was importing —
	should have come before the theory, not after.

## Pointers

- Process: `doc/development.md`. Code rules: `AGENTS.md` + `doc/style/*.md`.
	Library structure and conventions: `doc/library-structure.md`. Library maps:
	`<library>/SPEC.md`. Plans: `doc/plans/README.md`.
- Tasks: `TASKS.md` (this workspace), taskview ids in
	`~/.local/share/taskview/tasks.csv`, epiq refs on either board. A taskview id
	and an epiq ref look alike and are different things.
- **Which board a ticket goes on is a rule, not state** — `AGENTS.md` under
	*Working on a ticket*. Short form: a ticket belongs on the board of the repo
	where its change lands, and relocating between boards means close-and-refile
	because a ticket cannot be moved across two separate epiq projects. The
	old→new map for the 2026-09-30 split is on `58MXTGY`.
- Shared user context and per-agent state: `.agents/` in the Agents workspace.
- Reviews: `doc/reviews/` (read its README first). Audits: `doc/audits/`.
dirty-test
