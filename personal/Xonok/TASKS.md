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
	**⛔ Do not execute as written — its main item is now wrong in direction.**
	`R9H4PVD` repairs D9/D19 by removing rebinding language, on the grounds that
	F13 deleted rebindings; **F13 was reversed on 2026-10-15** (alias, every
	import rebinds). Both tickets need re-deriving against the alias ruling
	before anyone writes a line. **What survives unchanged and is ready now:**
	D16's two field names (`text`, `indent` — the string form is the hinge the
	indentation question turned on), D13's argv clause, D1's empty-line clause,
	F18, the counting correction (six, not nine), and the fully-ruled
	indentation-warning paragraph. **New from the alias ruling:** `import a.b`
	binds `a`, not `a.b`, and the alias form cannot express it — 1 occurrence,
	`dev/xhttp/_/helper.py:2`. **D19's declined warning may be moot** — three of
	its four collision sources are now structurally prevented rather than merely
	unlikely; only the non-local star import survives, which D9 already warns
	about separately.
- [ ] **#122 — Support cursor agents in marduk** (by decision needed, medium) — board: epiq `W1GTG4A` (Todo).
- [ ] **#123 — Consider whether to support cursor agents in skynet** (by decision needed, medium) — board: epiq `4P4VD3A` (Todo).
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
- [ ] **#117 — xhttp: validate against real code in Space-Traveller** (by
	2026-10-20, high) — the human's stated condition for calling xhttp done.
	Blocked behind #116. Parity reads 8/8 and the core suite is green, but parity
	is a checked list, not a running server.
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

## Related, tracked elsewhere

Not tasks — do not copy them in here. Open questions for the human are in
`STATUS.md`; board tickets are on the epiq board. A taskview id (`#42`) and an
epiq ref (`SFGQD7J`) look alike and are different things.
