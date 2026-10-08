# XLib tasks

The human-readable list for this workspace. One line per task, current state
only — what is true now, not how it got here. Ids are taskview ids
(`~/.local/share/taskview/tasks.csv`); the tmux panel for this repo shows
whatever carries category `XLib`, which is exactly this list.

`[ ]` open · `[x]` done · `(by DATE)` the due date, or the date a decision is
needed when there is no due date.

## Open

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

- [ ] Give #75 a due date (by decision needed) — high importance, open since
	2026-09-29, and it is the one task here that blocks nothing else while
	everybody waits on it.
- [ ] Give #77 a real due date or keep 2026-10-05 (by decision needed) — a
	testing task with no test written yet is a task that will slip.

## Related, tracked elsewhere

Not tasks — do not copy them in here. Open questions for the human are in
`STATUS.md`; board tickets are on the epiq board. A taskview id (`#42`) and an
epiq ref (`SFGQD7J`) look alike and are different things.
