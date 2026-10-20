# XLib tasks

The human-readable list for this workspace. One line per task, current state
only — what is true now, not how it got here. Ids are taskview ids
(`~/.local/share/taskview/tasks.csv`); the tmux panel for this repo shows
whatever carries category `XLib`, which is exactly this list.

`[ ]` open · `[x]` done · `(by DATE)` the due date, or the date a decision is
needed when there is no due date.

## Open

- [x] **#128 — pybundle: inlining across indentation conventions — CLOSED by
	ruling, 2026-10-15** (done 2026-10-15, high) — board: epiq `S1G5037` (Todo).
	Opened 2026-10-15 when a tab-indented module inlined into a space-indented
	caller at depth 8 was found to produce a bundle that **does not parse**
	(`TabError`, reproduced) — worse than the wrong bundle the ticket before it
	predicted. **Closed by not fixing it**, which is the ruling: *"we don't try
	to figure out whether a particular pattern would break things. It only
	matters that tabs and spaces are both used... Putting any serious effort into
	dealing with cases where spaces and tabs are used in the same project doesn't
	seem sensible, because the user can most likely solve this defect and would
	most likely appreciate the notice."* The bundle is written and ships; a stderr
	line says why. Same posture as D9's non-local star import, and the
	justification differs in a way the spec should record: there the cause is the
	bundler's own inlining, here it is a defect in the user's source. The root
	anchor catches this case for free — the callee disagrees with the root by
	construction.
- [x] **#126 — pybundle: mixed tab/space indentation — RULED twice, 2026-10-15**
	(done 2026-10-15, high) — board: epiq `S1G5037` (Todo). **Ruling 1, the
	mechanism**: *"Using the tokenizer's INDENT/DEDENT is a reasonable way of
	interpreting my intent. Checking strings exactly is not necessary."* D2 tracks
	blocks by matching INDENT/DEDENT, so the scope-tracking failure cannot happen
	and the `'\t' < '    '` hazard goes with it. This also settles D16's
	`indent`-as-a-string choice, which was made for exactly this reason. **Ruling
	2, the trigger**: anchor on the **root file** (or the first file that has
	indentation), warn if **any line** carries a different indentation type, and
	list every file that differs — over-firing deliberately. Two things the
	implementer needs that the ruling does not say: **scan statements, not
	lines**, or the warning fires on bracket continuation lines whose indentation
	Python ignores — six real ones in `dev/xhttp/test/test_parity.py` — and **D1
	already provides the fix**, since `NL` vs `NEWLINE` is exactly that
	distinction; and the **root anchor is what makes it catch the inline hazard**
	in #128. **Cost on XLib is zero**: across the 21 files that actually get
	inlined, mixed-leading lines are 0 and every one is unanimously tab-led.
	**Ruling 3, what the warning is for**: *"we don't try to figure out whether a
	particular pattern would break things. It only matters that tabs and spaces are
	both used"* — a red flag, not a hazard detector, with over-firing accepted and
	"serious effort" into mixed-convention handling explicitly declined.
	**Rulings 4 and 5, the shape**: whitespace-only lines are **ignored** (*"they
	don't affect how python runs in any case"*), and the report is **the first
	unexpectedly indented line per file** (*"this is generally not the bundler's
	purpose"*). **Calibration: silent on everything this repo has produced** —
	0 reported files across the 21 inlined sources *and* the 6 bundles in `xlib/`
	that the old bundler already produced; the 7 whitespace-only lines just
	excluded were the only thing in the repo a literal scan would ever have
	tripped on. Left is **wording only**, now folded into #127.
- [x] **#125 — pybundle: name-import shapes — RULED 2026-10-15, alias form**
	(done 2026-10-15, high) — board: epiq `F7KHKM8` (Todo). **Reverses F13.**
	*"following python behaviour strictly would be the correct choice and would
	mean that every import involves a rebind"*, then *"let's just say that every
	import, even non-local ones, gets a rebind"*, and finally **"okay, let's go
	with the alias solution"** after the collision evidence. **local** — import
	line deleted, one rebind per name (`server__ship__defs = server__defs`);
	**non-local** — import line rewritten with an alias
	(`from x import defs as A__defs`), no second statement; **local star import**
	— the same rebind, one per defined global, because a star import is *"just a
	more concise version of `from x import a,b,c...`"*. The two-statement form
	was tried first and dropped: it does not remove the collision, it relocates
	it, because `from x import defs` binds `defs` at top level whether or not
	anyone rebinds it. **All three questions answered by the one ruling, and
	verified together against real Python — 3 of 3 match**: star import then
	shadowing gives 2, a name the module does not define now traces because the
	callee's own import was prefixed on the way in, and function scope works
	provided **a rebind's LHS is already prefixed and must not be prefixed
	again**. Bloat measured at **+2%** (43 names, 1551 lines) and under the alias
	form non-local imports cost nothing extra. **The last undetermined shape is
	settled** — the split rule: **dotted module imports** (`import a.b`) keep the
	statement and add one rebind (`import email.utils` + `A__email = email`);
	**everything else** aliases in place. Reason: the alias hands the file the
	*leaf* instead of the *parent*, so `email.utils.parseaddr` keeps working by
	luck while `email.message_from_string` raises `AttributeError` — half-silent,
	and a test written against the working half reports green. **Bloat measured in
	bytes, not lines**: +3% over 44 807 B, ranging 0% (`_/server.py`, 10 imports)
	to 10% (`_/err.py`, 18 refs in 832 B). It tracks *references*, not lines, and
	flatters XLib — `dev/` is shallow, while the human's traveller example
	prefixes 4-character names with 13 characters. Accepted cost: *"I don't really
	see a way around it either."*
- [ ] **#127 — pybundle: re-derive and write in the spec edits** (by
	decision needed, medium) — board: epiq `R9H4PVD` + `EZAVYNM` (Todo).
	**Spec half DONE 2026-10-15.** New section *Decisions — 2026-10-15, after
	test pass 2* appended to `SPEC.md`: 268 insertions, **0 deletions**, and the
	first 730 lines verified byte-identical, so the append-only discipline of
	`03c0e75` holds. **D20** alias, reversing D9 and F13 · **D21** INDENT/DEDENT
	· **D22** `text`/`indent` plus the argv, empty-line and `pass` clauses ·
	**D23** D14's fourth diagnostic, fully specified · **D24** collisions ·
	**D25** the blocking count is six. The section opens by saying **read D20
	first — it reverses D9 two hundred lines up**, because an implementer working
	top to bottom would otherwise build the withdrawn mechanism.
	**What remains is the tests, not the spec.** The 138 were derived against D9
	as it stood *before* D20: six come back from the F13 deletion and every
	import-shape test needs re-deriving. The spec's own *What the tests must now
	cover* lists the seven cases. That re-derivation is the reviewer's, and it
	should not start until the reader it hands to has this section.
	**BOTH HALVES NOW DONE 2026-10-17.** Test pass 3 re-derived and committed
	(`de4f70b`, 188 in six files), and the bundler itself is implemented against
	them — 806 lines, five modules, **186 of 188 passing**, xlint clean. What the
	implementation exposed is filed as **#129** (the release path), **#130** (D15
	against the house idiom) and **#131** (the two structure tests, since fixed).
	**Landed `ba063b5`, 2026-10-17: all 188 pass.**
- [ ] **#122 — Support cursor agents in marduk** (by decision needed, medium) — board: epiq `W1GTG4A` (Todo).
- [ ] **#123 — Consider whether to support cursor agents in skynet** (by decision needed, medium) — board: epiq `4P4VD3A` (Todo).
- [ ] **#141 — Mechanize the `git checkout` ban** (by decision needed, high) —
	category: agents. The rule itself is written and in force
	(`doc/working-tree.md` here, `AGENTS.md` in Agents); this is about enforcing
	it. **Two guards, catching different things.** (1) A global opencode plugin
	in `~/.config/opencode/plugins/` hooking `tool.execute.before` and rejecting
	any shell command matching `git checkout` — this is the one that stops the
	actual accident, because every agent command passes through the tool, and
	`~/.config/opencode/plugins/` is global so subagents are covered too (which
	also bears on open question 5 in STATUS.md, about prose rules not binding
	dispatched workers). `tool.execute.before` **is** in v2.0.31's plugin hook
	surface (`~/.opencode/node_modules/@opencode-ai/plugin/dist/index.d.ts:234`,
	signature `(input: {tool, sessionID, callID}, output: {args})`), but the
	published plugin docs are still the V1 entrypoint shape, so *whether throwing
	aborts the call* needs a live test — that is the first thing to try, not an
	assumption. (2) An xlint rule flagging the literal string in tracked
	`.md`/`.py`, enforced by the pre-commit hook. This catches only the
	**durable** half — `git checkout` written into a script, a doc, a test or a
	README — not a one-off command, and a one-off is exactly the accident. Needs
	#113's extension point first, or lands inside `xlint.py` against that
	ticket's reasoning. **Neither was built: both are programmer work**, and the
	human's *"a mechanized check could also be good"* reads as an endorsement of
	the idea rather than an instruction to implement it. **The target grew on
	2026-10-19: the ban now covers `git reset --hard` and `git reset --merge`
	as well, so a guard that matches only `git checkout` would miss the two
	forms that actually destroy work** — and plain `git reset` is *not* on the
	list, on the measured grounds that it never touches the working tree and only
	resets the index. A guard matching `git reset` as a prefix would be wrong:
	it would block the safe `--soft` and path forms too.
- [x] **#142 — `agent-coord.py news` destroys every agent's claims and the rule
	cursor** (done 2026-10-20, high) — **REOPENED and FIXED on the same day: the
	PR #47 repair did not hold, and PR #50 is the repair. MERGED as `f12ebd5`.**
	Board: epiq `K93Z39B` (reopened, In progress). Board: epiq `K93Z39B` (reopened, In progress). **The fix is
	in PR #50, waiting for the human's merge.**
	**What PR #47 fixed, and what it did not.** The claims-wipe is genuinely
	fixed: `migrate_ids()` no longer drops the claims of every agent on the
	machine, and `rule_files()` finds the 41 rule files in `doc/style/`. **The
	workspace resolution is not.** The repair settled on the opencode client by
	walking this process's ancestry, and it assumed the client is an ancestor of
	the tool shell — under opencode 2 it is not. The shell descends from the
	shared service and the client is a separate process, so the walk finds the
	service, whose cwd is the home directory, and the session resolves to
	`/home/xonok`. **Measured live, in the session that found it: `news` printed
	`no rule files found in /home/xonok — nothing checked`, 0 rule files, and
	`workspace` printed `/home/xonok`.** The verification recorded on the ticket
	was taken in a session whose ancestry happened to hold a client; the topology
	this machine actually runs — one service, four clients, no client in any tool
	shell's ancestry — was not covered. **So the `git checkout` ban, which this
	ticket's `news` was carrying, still cannot reach a session shaped like this
	one.**
	**The fix: the client is found by what it says about itself.** It names the
	session it serves in its own arguments, and it works in the directory the
	session works in. The service is never a candidate — one service runs for
	the whole machine, so it is not evidence about the session asking. The
	session key follows, so two windows are two sessions again: the client's
	pid, not the service's.
	**One thing the transition needed that the ticket did not ask for:** the
	service's pid was the session key, so every session attached to the service
	shared one identity, one notes file, one rule cursor and one set of claims.
	With the key changed, that identity is a leftover, and its claims are
	stranded where the guard refuses the rightful owner. It is now taken over
	once, with its claims and its cursor, and re-tagged to the workspace the
	session is really in — the old tag was the home directory's name, which was
	never a workspace. **36 tests in `tools/test/test_agent_coord.py`; 11
	mutations of the repair, each killed by the test that names it.**
- [x] **#150 — Drift sweep: `STATUS.md` and `TASKS.md` against the task store
	and the board** (done 2026-10-20, medium) — **MERGED as `671b150` (PR #51).**
	Board: epiq `TAQ74SC` (Done). The scheduling paragraph in
	`STATUS.md` is wrong on both counts: it says 4 high-importance tasks have no
	due date (#52, #61, #63, #75 — all four have one now) and that 10 tasks are
	past due, where the store says **17**. It also points at "this workspace's
	two" tasks, and `TASKS.md` has **28** open. The 16 tasks that genuinely have
	no due date are a different set (#104–#110, #122, #123, #127, #133, #137,
	#138, #140, #141, #143) and are not mentioned.
- [ ] **#155 — xtest: rewrite the unittest suites in xtest's own idiom** (by
	2026-10-27, medium) — board: epiq `QJEA7EM` (Todo, tagged
	`rewrite-to-xtest` and `new-tests-xtest`). **The release half is done:**
	**xtest 1_1_0 is on master as `e8ffe49`** (epi `48GH7NW`), verified against
	the release rather than the source — `from xlib import xtest` resolves to
	`xlib/xtest_1_1_0.py` and that file runs xtest's own suite, 13 passed. **The
	decision is written down** in `AGENTS.md`, `doc/development.md` and
	`dev/xtest/SPEC.md`: **rewrite to xtest if it gets in the way**, and
	**always write new tests with xtest**. What is left is the migration: the
	852 tests in `unittest.TestCase` classes **run** under xtest but are still
	**written** in unittest's idiom. Start with `tools/marduk/test/` (101 tests,
	the most varied use of unittest's features), then `tools/taskview/test/`
	(123) and `tools/xlint/test/` (98); `dev/xhttp/test/` (239) is last, because
	its runner has a `--core` flag, an `edge` tag convention and a `preflight()`
	that the migration has to keep or reinvent.
- [x] **#158 — skynet: always stay within the window bounds, and say what was
	cut** (done 2026-10-20, high) — board: epiq `VTJVHMY` (Done). **PR #58,
	commit `a46cf2f` — it waits for the human's review, and the merge is the
	agent's action once that review is given.** The shape the human fixed is
	what was built: the caps come from the space available (the terminal's own
	height, which in a tmux pane is the pane), the two sections split what is
	left of the room evenly, **the odd line goes to Today**, an overflow note
	costs a row of its own, and a capped table ends with `… +N more`.
	- **Measured**: the display fits every pane height from 1 to 49 lines,
		checked through a pty at each height. At 30 lines it is exactly 30:
		nine of structure, eleven for Today, ten for Window.
	- **The suite is 25 tests**, 18 of them new, in xtest's idiom. `xlint` is
		clean, and the repository's runner is unchanged (the same six known
		`ContentNegotiationTest` failures, epi `BFNRBG7`).
	- **Two decisions the ticket does not cover**, both flagged on the PR: the
		blank line after the `Skynet` header was added, because the ticket's own
		count of the nine lines includes it; and a pane shorter than seven lines
		gets the counts on one line (`Skynet: 19 models today, 53 models in
		window`) rather than a display that runs past the edge.
	- **One thing the requirement forced**: the watch loop watches the
		terminal's size as well as the database's, so a resized pane redraws.
- [x] **#156 — Agents workspace: commit the `.taskview.yaml` category rename**
	(done 2026-10-20, low) — **committed: `cd7900e` on the Agents repo's master.**
	Board: epiq `YQK582P` (Agents board, Done). The panel's comment now names
	the categories in use in the house style, and says what the second level is
	for XLib work. **The filter itself did not change** — this panel is the
	unfiltered one, so it picks up whatever no other panel claims. The change
	had been live in the working tree since 2026-10-20; this was the commit,
	which the commit-msg hook would not take without a ref, and which needed a
	ticket on the board where the change lands.
- [ ] **#151 — Spec: the wide all-tasks priority view** (by 2026-10-24, medium)
	— board: epiq `E5MH4S2` (Todo). **The human's own framing, 2026-10-20:** the
	wide tool *always orders by due date* — changing the order is simply a
	result of changing a due date, so a separate priority mechanism is not
	needed and the priority sweep of all 77 open tasks is not wanted. **The
	interaction the human sketched:** click a task, then set a new due date
	directly (`2026/10/27`) or write a relative time to bump it (`+7d`).
	**The spec is the deliverable, not the tool**, and it must go through the
	normal process — AI-written and labelled, or human-written. It reuses
	taskview's selection layer (`read_csv`, `select_tasks`, `compute_metrics`)
	rather than reimplementing it, and it reads the same CSV, which stays the
	single authority.
- [x] **#139 — xlint: add html support** (done 2026-10-19, medium) — board: epiq
	`YFJZRYC` (Done). **Implemented and merged** — PR #42, on master as `5c1865e`,
	merged on the human's own instruction so they could run it over Traveller.
	Three html-specific rules on top of the generic ones, as ruled: **unclosed tags
	(strict — every non-void tag must be closed explicitly)**, **closing tags that
	shouldn't be** (all three readings: a closer for a void element, a closer with
	no matching open, and a closer that does not match the innermost open), and
	**bad indentation** (both depth-mismatch and spaces-instead-of-tabs, under
	separate flags, with depth measured in the file's own unit). **Code in
	`tools/xlint/_html.py`** — a tokenizer, one walk over the tags, the depth rule
	— imported by `xlint.py`; `.html` in `_ALL_SUFFIXES`; a `--no-html-*` flag
	family (7 flags). **23 new tests; the suite is 90 green.** **Measured on
	Traveller's 27 html files and Mallesne's one: unclosed 0, stray 0, depth 774 —
	589 of them the one systematic off-by-one — spaces 0, trailing whitespace 7,
	double blank 2, final newline 0.** The depth is one finding from the earlier
	measurement (773 and 588) and the shape matches: the same 184 deeper findings,
	the same single -1 at `main.html:134`. **Trailing whitespace reads 7, not the
	3 that earlier script found: the difference is four lines ending in a tab**,
	which xlint's own generic rule catches and that script's did not. The corpus
	is clean on structure, so the two structural rules have their own fixtures
	rather than the acceptance test; Mallesne's one html file is clean on
	everything.
- [ ] **#140 — New XLib html-bundling library + watch option** (by decision needed,
	medium) — board: epiq `WAH4BYM` (the library) + `6BGG7TH` (the watch option),
	both Todo. **A separate library, by the human's own ruling 2026-10-19**: *"I
	guess the bundler is also an XLib issue."* Source is Space-Traveller's
	`server/Misc/html.py` (210 lines), which expands `page_insert` components and
	concatenates page scripts into `_cache/`. **Three findings recorded on the
	ticket:** a dead near-duplicate at `Space-Traveller/lib/HTML.py` (212 lines, no
	longer imports); `load()` and `load_html()` are two drifted copies of the same
	logic; and the traveller-specific parts — `js/pageinit.js`, the `/main.js` in
	`<head>` convention, `html/comp/`, `class="page_insert"` — are convention, not
	code, and have to become configuration. **The watch option's trap:** compare
	source mtimes fs against fs, never against a wall clock, because a watcher that
	misses a change is worse than no watcher — it is trusted, so nothing checks it
	by hand.
- [ ] **#143 — xhttp: gzip regardless of Accept-Encoding** (by decision needed, medium) —
	board: epiq `BFNRBG7` (Todo). **The only red in xhttp**: `send_response_full`
	compresses whenever `compress=True`, which is the default, so a client that
	sent no `Accept-Encoding`, an empty one, or `gzip;q=0` is answered with gzip
	anyway. `ContentNegotiationTest` (`dev/xhttp/test/test_response.py:282`) is
	the marker — six failures, deliberately not fixed, per the 1_0_1 release note
	(epi `VC9QWYY`). **The shape is already sketched there**: reuse the
	thread-local pattern `closing` uses — `wrap_handler` reads the header off the
	request, `send_response_full` consults it, no public signature change. **One
	case needs a ruling rather than an assumption**: what `send_response_full`
	should do when it is called outside any request. **Filed 2026-10-19 because
	`AC9YJYQ`'s description claimed the six failures "are filed separately" and
	they were not** — no ticket and no taskview task existed, which is how a
	known defect goes quiet.
- [x] **#144 — xlint: reports clean inside a `.work/` worktree, checking nothing**
	(done 2026-10-19, medium) — category: XLib. **Found 2026-10-19 while adding
	html support to xlint.** The root repo's `.xlintignore` lists `.work/`, and
	the exclusion applies to the worktrees the root contains — so `xlint .` in
	`.work/<ticket>/` excludes everything and prints "clean" while checking
	nothing. **The failure mode is the one a linter cannot have**: a run that
	excluded the whole tree is indistinguishable from a run that found nothing.
	Two of the exclusion tests fail there for the same reason, and pass from the
	root checkout. The repair is in the exclusion matching, not in the pattern.
	**DONE 2026-10-19 — PR #44, two tickets: `XP56NNC` (the linter) and
	`2X3PZT3` (the hooks).** The repair is where the note said it would be: the
	upward walk that finds `.xlintignore` files now **stops at the checkout that
	owns the path**, and a worktree's `.git` is a *file*, so the old lookup
	walked straight out of it and found the outer repository's rule. **A second
	mechanism turned up while measuring it, and it is the bigger half: the
	style gate did not run in a worktree at all** — `core.hooksPath` was the
	relative path `.git/hooks`, which resolves inside a worktree to a *file*
	rather than a directory, so git found no hook to run and neither the xlint
	gate nor the ticket-ref check did anything there. Both fixed; a run over an
	excluded path now says **"nothing checked"** instead of printing `clean`.
	**Eight new tests; the suite is 98 green.** The gate's output at the
	repository root is unchanged.
- [x] **#145 — agent-coord: check-clean reports clean for a dirty file in a
	worktree** (done 2026-10-19, medium) — category: XLib. Board epiq
	`8FVW49J`, open since 2026-10-01 and unassigned until this session. `nearest_git`
	(`tools/agent-coord.py:791`) requires `.git` to be a **directory**, so a path
	inside a worktree walks past the worktree root to the parent repository; the
	relative path then never matches the parent's dirty list, and the guard
	reports `clean` for a file that is dirty. **The same shape as the linter
	blind spot fixed in PR #44, in different code** — xlint never used
	`nearest_git`, so fixing it there would not have fixed the linter, and
	fixing the linter did not fix this. A guard that says "clean" about a dirty
	file is the failure mode the coordinator exists to prevent: two agents edit
	the same file and neither is told. **FIXED and on master: PR #47, commit
	`806253e`** (board epiq `8FVW49J`, Done). The
	walk stops at the checkout that owns the path, a worktree's `.git` counts
	whether it is a file or a directory, and a file behind a symlink is compared
	under the tracked name as well (`STATUS.md` → `personal/<person>/STATUS.md`).
	**One consequence to say out loud:** with a worktree resolving to its own
	checkout, a check naming a file in the worktree *and* a file in the parent
	names two checkouts — the old code refused that outright ("paths span
	multiple repos"), which is the failure `STATUS.md` recorded on 2026-10-01
	and `.agents/shared-notes.md` says "did not reproduce". Each checkout is now
	checked against its own status, and the path printed says which one it is.
	**8 more tests; the suite is 21.**
- [ ] **#138 — Set up Discord access for agents (bot token, permissions, channel bindings)** (by decision needed, high) — category: agents. Follows from #111 (how it would work); now needs actual bot creation, token management, and channel/role bindings for the agent workflow.
- [ ] **#136 — marduk: track the opencode process, not the window** (by
	2026-10-23, medium) — board: epiq `NAHEGJE` (Todo). The registry's `pid` is
	oc-agent's own `$$`, so an entry lives exactly as long as the kitty tab
	rather than the session. Three decisions taken 2026-10-18: record the
	opencode child's pid, keep service-only sessions shown but uncorroborated,
	and fold in the no-usable-pid and pid-reuse leaks.
- [x] **#116 — xhttp: fix `_/websocket.py` so `xlib_dev` can load it** (done
	2026-10-10, high) — import chain fixed; `_/websocket.py` now uses
	`from .. import xhttp`. `from xlib_dev import xhttp` loads and tests pass.
- [x] **#124 — dev/xhttp: move RFC comparison material out of the root folder**
	(done 2026-10-13, medium) — the RFC reference implementation and its harness
	now live in `dev/xhttp/compare/`, a sibling of `test/` and deliberately
	**not** inside it: `run.py`'s `discover` walks subdirectories, and 7 of the
	loose files match `test_*.py` while being ad-hoc scripts, so moving them into
	`test/` would enrol them in the suite. Root `test_server.py` would also
	clobber the tracked suite file of the same name. Board `MV6J077`, commit
	`ba84849`. The two open questions it raised were settled in the same pass:
	the second `compare_websockets.py` was the **superset** (it reads raw frame
	bytes to inspect the masked bit) so the root copy was the stale ancestor and
	was deleted; `test_websocket_correctness.py` was already being discovered by
	`run.py`, so it is now tracked on purpose.
- [ ] **#119 — xhttp: fix websocket thread lifecycle** (by 2026-10-20,
	medium) — `sender` thread in `_/websocket.py` blocks on `queue.get()`
	forever with no shutdown signal. When connection drops, `receiver` exits
	but `sender` leaks. Queue grows unbounded if `send()` called after close.
	No sentinel, no socket check. Unused `queue` import. `key_hash` typo,
	`_send` arg order, `on_message` msg pass were fixed.
- [x] **#117 — xhttp: does a release survive being used by Space-Traveller**
	(done 2026-10-18, high) — the game server has been running on xhttp "for a bit
	now and seems to be working fine". The released `xhttp_1_0_0.py` (`2X0B2XW`)
	is verified xlint-clean, 223 tests green, and survives that use. The refresh
	flakiness is attributed to the frontend (still on `dumb_http`) and is tracked
	separately.
- [x] **#118 — xhttp: commit `dev/xhttp/`** (done 2026-10-14, medium) — the whole
	folder arrived from Space-Traveller untracked on 2026-10-10. The scratch layer
	was the last of it: `REVIEW.md` and `TODO.md` were the only untracked files
	left anywhere in the repo, and `0a0dcd8` committed them. **Nothing under
	`dev/xhttp/` is untracked now.** The store already had this as `done` while
	this list still showed it open — that drift is what the line above fixes.
	(how it went: `bec0a9a` and earlier for the code, `ba84849` for `compare/`,
	#124, then `0a0dcd8`.)
- [x] **#112 — `xlib_dev` override package: run real code against prerelease
	libraries** (done 2026-10-10, high) — human's proposal 2026-10-10: a root
	package `xlib_dev/` so `from xlib_dev import xcsv` runs real code against a
	prerelease. The `xlib_dev` prefix is the right call — it cannot collide with a
	builtin, which the old `from <library> import <library>` shape could.
	**Shipped** as `xlib_dev/__init__.py` on master, commit `b0214a4`, board:
	epiq `ASTXNPG` (Done). An `__getattr__` mirror of `xlib/__init__.py`, not one
	file per library. 12 tests, mutation-checked. **Dev → dev dependency is
	allowed and wanted**; only dev → release gets policed, and by release.py
	(#115), not by a lint rule. Enforcement split into #113/#114.
	`test_no_released_file_references_the_override` already enforces part of
	#114 — it should move to xlint when the rule lands, not be duplicated.
- [ ] **#115 — `release.py`: refuse to release a library that depends on dev
	versions** (by 2026-10-31, medium) — human's call 2026-10-10. **Not a bundler
	change**: the bundler is generic and only inlines internal modules;
	`release.py` owns "is this releasable". This is the real enforcement half —
	#114 alone would leave a released file free to name `xlib_dev`, but a dev
	library pointing at another dev library is fine and intended.
	**Newly blocked 2026-10-14**: `release.py` imports the bundler at module
	scope and the bundler was deleted in `5e87ae8`, so the script fails at import
	and there is no release path to add a check to until `6MFX0Z1` lands a
	replacement bundler.
- [ ] **#114 — xlint: released files under `xlib/` must not mention `xlib_dev`**
	(by 2026-10-31, medium) — deliberately its own ticket rather than a line in
	#113: this is *policy*, #113 is *mechanism*. Grep-level, zero false
	positives. Needs #113's extension point first.
- [ ] **#113 — xlint: support repo-specific rules without editing `xlint.py`**
	(by 2026-10-24, medium) — the meta ticket. Repo policy should live in config,
	not inside a shared tool. `tools/xlint/xlint.py` is currently a flat set of
	`check_*` functions called from `check_file`; there is no extension point.
- [ ] **#110 — The best alignment in the repo is docstring prose** (by decision
	needed, low) — `dev/xcsv/xcsv.py:24-30` and `xlib/xcsv_1_1_0.py:97-103`
	align exception names **inside a module docstring**, where no comment exists.
	`doc/style/python.md` says nothing about docstrings at all. Found because this
	is why two of my earlier counts were wrong. Board: epiq `HRGFRWX` (Todo).
- [ ] **Houserule, ruled 2026-10-09: spaces are never used for alignment.** If
	alignment is desired, use tabs; avoid alignment where possible. A spilled
	function signature becomes ordinary tab indentation rather than columns —
	`func(` alone, arguments one tab deeper, `)` back at the `func(`'s indent —
	because renaming a parameter can break an alignment and cannot break an
	indent. Aligned comments only where comment density is **very high**; inline
	comments should usually be avoided for a line above, and the single space
	applies **only to inline comments**. Rare by design — high density is itself
	often a *why-not-what* violation. A line above is already 79% of tracked
	Python comments. Not yet written into `AGENTS.md` or `doc/style/python.md`.
	Board: epiq `BSFQYPF` (Todo); enforcement is #107 / `F8XBH1F` and #109 /
	`HRCQSV4`.
- [ ] **#109 — xlint: separate rule for comments on `def`/`class` lines** (by
	decision needed, medium) — ruled **bad taste, but not a split signature**, so
	it gets its own rule rather than being folded into `check_def_one_line`. 74
	`def` lines today; **`class` lines are never checked at all**
	(`_DEF_PREFIX_RE` matches `def` only), so 0 is a coverage gap, not a clean
	baseline. Split out of #108. Board: epiq `HRCQSV4` (Todo).
- [ ] **#104 — xlint: aliased imports misclassified** (by decision needed) —
	`import x as y` has no dot, so `check_imports` classes it as plain and both
	flags it and propagates it as a mergeable predecessor. `import json` /
	`import math as m` / `import collections` yields two findings and **no legal
	fix** — the rule is unsatisfiable for that input. Needs a style ruling first:
	`doc/style/python.md` says plain imports are comma-joined and dotted names get
	their own line, and is **silent on aliases**, so the linter filled the gap in
	one direction. Board: epiq `DDRBHD5` (Todo).
- [ ] **#108 — xlint: `check_def_one_line` is 100% false positives** (by decision
	needed, medium) — reports **74** "function definition split across lines" and
	**0** of them are spills; every one is a single-line `def` with a trailing
	comment, because the closing pattern is anchored `\s*$`. All 74 sit in
	`tools/taskview/test/`, invisible to a plain `xlint .` (`AK633QC`). It also
	bans the tab-indented signature shape the houserule **permits**. The one-line
	trailing-comment fix is worth landing on its own. Board: epiq `1YPFZYH` (Todo).
- [ ] **#107 — Reformat 369 lines of space alignment across 47 files** (by
	decision needed, low) — the enforcement side of the houserule below.
	**Corrected 2026-10-09**: the `.py` half is **17 sites plus the 74
	`def`-line comments** (#109 owns those), not 134 — and 2 of the 5 real
	high-density blocks were already single-spaced and compliant. **The Markdown
	half (135 lines: tables, prose, ASCII diagrams) is now most of the work** and
	is untouched by the ruling. Board: epiq `F8XBH1F` (Todo).
- [ ] **#106 — xlint: no mid-line double-space check** (by decision needed, low) —
	**not implemented** — the data exemptions are the ticket, per the human. A
	prototype goes 116 → 586 findings repo-wide, and **134 of them are the
	repo's own `ClassName    # comment` alignment**, so the rule as stated
	contradicts house style. Data must be exempted by **replacement, never
	deletion** (deletion gives 1879 — false positives at the seam). Needs calls on
	scope, the exemption list, whether the 470 existing files get reformatted,
	and `tokenize` vs regex for string literals. Board: epiq `13QYCT8` (Todo).
- [ ] **#105 — xlint: no check for a single trailing blank line** (by decision
	needed, low) — `import os\n\n` passes both `check_final_newline` and
	`check_double_blank`, so the two halves of "a file ends with exactly one
	newline" do not add up to that rule. Four tracked files hit it (`taskview.py`,
	`taskupdate.py`, `bbprs/README.md`, `doc/reviews/pybundle-review.md`).
	Needs a call on overlap with `double blank line`, and on whitespace-only and
	empty files. Board: epiq `BX56XRY` (Todo).
- [ ] **#77 — Test the tool schema cache cluster** (by 2026-10-05) — does it earn
	its place? It replaces #42, which closed done: the idea was investigated and
	built (`tools/tool_schema_cache.py` with `prompt_builder.py` and
	`session_tracker.py` around it), the three call each other and nothing calls
	them, and `.schema_cache/session_state.json` is still at turn 0. Also on the
	board as epiq `SFGQD7J` (Todo). (why: HISTORY.md 2026-09-17)
- [ ] **#75 — How legible can AI code be** (by decision needed, high) — the
	plan survived: it was recovered from the git-ignored notes folder and
	committed as `doc/plans/ai-code-viability.md`, indexed in the plan README.
	Five mechanisms to cost and rank, and not one checklist box is ticked. Also
	on the board as epiq `E98CRYM` (human-input-needed). (why: HISTORY.md
	2026-09-30)
- [ ] **#96 — taskview: a description field, and 2 tasks in full detail** (by
	2026-10-08) — four rulings on 2026-10-08: a separate description column on
	`tasks.csv`; exactly 2 tasks rendered in full detail with the remaining space
	going to the condensed list; and the 2 always being the most urgent by due
	date, overdue first, regardless of day. Blocked on `AQQNPAN` (the CSV header
	still declares 5 columns against 8-field rows) and on every other open
	taskview ticket by the human's ruling. Board: epiq `XNTVCEE` (Todo).

## Done

- [x] **#42 — Tool schema cache** — closed 2026-09-30. Built but unevaluated, so
	the follow-on is #77 rather than a closure of the question.
- [x] **#17 — pybundle spec** — cancelled 2026-09-30, not done. Its subject was
	"hammer out the kinks in `pybundle/SPEC.md`", and the human is writing a new
	spec from scratch instead (epi `6MFX0Z1`), which makes those kinks moot.

## Scheduling

- [ ] Give #104 a due date (by decision needed) — it is blocked on a style
	ruling, not on writing code, so it needs a date for the ruling rather than
	for the fix.
- [ ] Give #75 a due date (by decision needed) — high importance, open since
	2026-09-29, and it is the one task here that blocks nothing else while
	everybody waits on it.
- [ ] Give #77 a real due date or keep 2026-10-05 (by decision needed) — a
	testing task with no test written yet is a task that will slip.

## pybundle — after the implementation, 2026-10-17

All three are decisions, not code. The bundler itself is written, and all three
are settled now — two ruled and implemented 2026-10-17, one (`#133`) left as
future work.

- [x] **#129 — pybundle: how does `release.py` reach the bundler** (done
	2026-10-17, high) — board: epiq `1ZY2Q5Q`. `release.py:74` called
	`bundler.bundle(str(entry))`, which **the spec does not have**: the seven
	functions are `statements`, `imports`, `renamed`, `translate`, `inline`,
	`main`, `cli`, and the old `bundle(entry) -> str` is not among them, so every
	library failed with `AttributeError`. **Decided and built 2026-10-17: the
	second option**, on the human's ruling *"spec as written, bridge separately"*.
	`bundled(entry)` is now in `release.py` and is `main` over a `StringIO` — the
	spec keeps its seven functions. **Verified without releasing anything**:
	byte-identical to the CLI's
	output for all five libraries, and a redirected `release("xhttp","rev",
	False)` writes an xlint-clean `xhttp_1_0_0.py`. Board epiq `1ZY2Q5Q`, whose
	comment carries the same evidence and whose lane is the human's to move.
- [x] **#132 — pybundle: retire `RELATIVE_IMPORT_IN_ROOT`** (done 2026-10-17,
	high) — board: epiq `NJ529TQ` (Done). **Ruled 2026-10-17 as D30** and
	implemented the same day, out of lane on the human's authorisation to write
	code. Guard, exception class and its two uses gone; the four tests that pinned
	it rewritten. **188 → 202 tests, all passing**, whole-repo xlint clean.
	**All five libraries in `dev/` now bundle and every bundle is xlint-clean.**
	What D30 settled, and the evidence behind it, is in the entry below.
- [x] **#134 — pybundle: emit xlint-clean bundles** (done 2026-10-17, high) —
	board: epiq `GADE1PY` (Done). **RULED 2026-10-17 — *"the bundler has to
	produce xlint-clean code"* — and implemented the same day.** The three rules,
	from `tools/xlint/xlint.py:907-920`: no `, ` in an emitted import; an emitted
	statement with an alias is **split one target per line** (the 2026-09
	houserule, so the bundler was breaking house style rather than inventing a
	form); a removed statement leaves no double blank. **Correction to a claim
	recorded here on 2026-10-09:** the merged-imports rule is *not* unsatisfiable
	for the bundler's shape — only for two **plain** imports plus one alias, which
	is a source shape, so `#104` / `DDRBHD5` stays open and untouched. **D33's
	comparison is in too** (`renamed(name, prefix) == name`), with its negative
	test: a non-root file must still get its aliases. **The obligation has a test
	that invokes xlint**, because `is_ignored` excludes any path part named `test`
	(`AK633QC`) and a fixture in `test/` would be invisible to the check it exists
	to satisfy. **Verified**: all five bundles lint-clean, and the xhttp bundle
	still runs its 223 tests green — the two failures this work kept reporting
	were tests that had never been written (see the `#117` entry's neighbour,
	`7Z7DE78` in epiq).
	**Also found and fixed while implementing it, as `SPEC.md` D34**: an indented
	non-local name import lost its indentation, so the bundle **did not parse**.
	D20's *"rewritten in place"* had been read as *rebuilt*.
- [x] **#135 — xhttp: VERSIONS.md before a first release** (done 2026-10-17,
	medium) — written, with the shape `dev/xconf/VERSIONS.md` uses: the title, the
	convention note, and no entries because nothing is released yet. The first is
	`1_0_0`, which `release.py xhttp` now produces — verified with the write
	redirected to a temp folder, so no release was made.
- [ ] **#137 — pybundle: bundle Space-Traveller as the acceptance test** (by
	decision needed, medium) — the human's own framing, 2026-10-18: *"I want to see
	what happens if I bundle traveller at some point. If Traveller can survive the
	bundling, then it's very likely that the bundler's behaviour is correct
	overall."* **That is a bigger test than any fixture**: Traveller is real code
	with real structure, so if it bundles and runs, the bundler's judgement calls —
	what gets a prefix, what keeps its name, what is left behind — have been right
	on something nobody wrote the tests for. **It is only possible because the
	bundler refuses no input for style reasons** (D36), so the gate lives in
	`release.py` instead (D37). Nothing to do until he says go.
- [ ] **#133 — pybundle: an option that emits internal-module shims** (by
	decision needed, low) — board: epiq `AYB2896` (Todo). The human's own words,
	2026-10-17: *"We'll probably have to add an option to the bundler for making
	these shims automatically. Future work."* A bundle has no module objects
	(D17), so a bundled library cannot run its own suite —
	`test_response.py:25` does `from xhttp._.response import http_responses` and
	`test_websocket.py` reaches `websocket._recv`. Running all 223 against the
	xhttp bundle needed a hand-written shim package that rebuilds each internal
	module out of prefixed names. **Not a blocker while internals stay
	unreachable by design**; it becomes one when a library ships bundled and its
	suite is the only thing that can catch a regression in it.
- [x] **#130 — pybundle: D15 forbids a relative import in the root, and three
	libraries use one — ANSWERED, the spec is wrong** (done 2026-10-17, high). The
	human asked whether python allows it. **It does**, and this repo depends on it:
	`import pkg.mod` runs clean, `python pkg/mod.py` raises `ImportError:
	attempted relative import with no known parent package`. D15's premise —
	*"which python does not allow"* — is true of `__main__` and false of a package
	module, and `dev/xhttp/test/harness.py:7` puts `dev/` on `sys.path` so
	`from xhttp import xhttp` works. **So `from ._ import …` in a root is the house
	idiom and legal, three libraries use it, and the six bundles in `xlib/` came
	from a bundler that handled it.** The error belongs on an entry that is a
	script, which the bundler cannot currently tell. **Decided 2026-10-17: relax
	it** — *"Callers are not supposed to use those. That's part of why the root file
	of a library needs to reflect whatever internals matter"* — and the
	implementation is `#132`.
- [x] **#131 — two tests in `test_bundler_structure.py` cannot pass as written**
	(done 2026-10-17, medium). Neither was satisfiable by any import mechanism.
	`test_each_function_of_the_set_lives_in_the_file_the_table_names` compared
	`Path(value.__module__).name` against `"bundler_source.py"`, and `__module__`
	is a dotted module name, never a filename. `test_some_module_of_the_bundler
	_imports_tokenize` matched `^\s*import\s+tokenize\b`, which only a single-name
	import satisfies, while `doc/style/python.md:26` mandates comma-joined
	imports — so it matched none of this repo's own imports. **Fixed on the human's
	authorisation**, both helpers corrected to their intent rather than weakened.

## Related, tracked elsewhere

Not tasks — do not copy them in here. Open questions for the human are in
`STATUS.md`; board tickets are on the epiq board. A taskview id (`#42`) and an
epiq ref (`SFGQD7J`) look alike and are different things.
