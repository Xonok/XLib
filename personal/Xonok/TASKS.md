# XLib tasks

The human-readable list for this workspace. One line per task, current state
only — what is true now, not how it got here. Ids are taskview ids
(`~/.local/share/taskview/tasks.csv`); the tmux panel for this repo shows
whatever carries category `XLib`, which is exactly this list.

`[ ]` open · `[x]` done · `(by DATE)` the due date, or the date a decision is
needed when there is no due date.

## Open

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
