# History — Xonok

Append-only record of what happened and when, in this workspace. The state
files (`STATUS.md`, `TASKS.md`, `PLAN.md`) state the present and only the
present; anything worth reading in six weeks goes here.

**Append only.** Entries are never rewritten or removed without the human's
sign-off. A correction is a new entry naming the entry it supersedes — the
record that a belief changed is worth more than the belief was.

Policy and rationale: `plans/history-files.md` in the Agents workspace.

## Entry format

One entry per line, a list, appended at the bottom:

```
- `1790534607` · 2026-09-27 21:43:27 · `machine` — Anki segfault root-caused to
	QtWebEngine GPU init; fixed with a `--disable-gpu` wrapper.
```

| Field | Required | Notes |
|-------|----------|-------|
| Unix timestamp | yes | Timezone-less, seconds. Authoritative — settles ordering, and a slipped human clock cannot corrupt it. |
| Local date+time | yes | `YYYY-MM-DD HH:MM:SS`, biggest unit first, all digits. **If the two disagree, the unix timestamp wins.** |
| Scope tag | yes | `` `machine` ``, `` `person` ``, `` `agents` ``, or a repo basename. This is what makes a single flat file greppable. Keep the vocabulary small. |
| Body | yes | What was true, what was done or decided, the outcome. **Key findings belong here, not just a link to a plan** — a plan holds the reasoning, history holds what was learned. |
| Doc pointer | optional | Trailing `→ path`, only to a plan or `library/` doc. Never to a `STATUS.md`, which changes under it. |

Absolute paths are allowed here — this file is per-person, and that is the
mitigation.

Which file an entry goes in: something a person cloning that repo would want
lives in that repo's `HISTORY.md`; anything about the human, the machine, or
the workspace across repos goes here. Never both.

---

- `1790572309` · 2026-09-28 08:11:49 · `agents` — History-file policy decided and step 1 applied. Decision: one append-only `personal/<person>/HISTORY.md` per person, per repo, always named `HISTORY.md` — the Agents workspace's file absorbs the bucket list (machine / person / agents), other repos carry their own, so there is no per-scope file proliferation. Each entry carries a timezone-less unix timestamp *and* a local `YYYY-MM-DD HH:MM:SS` string, plus a scope tag, so the flat list stays greppable; unix wins if they disagree. Entries are appended, never edited — a correction is a new entry naming the one it supersedes, because the record that a belief changed is worth more than the belief was (four claims were withdrawn on 2026-09-27). Key findings go in the entry, not just a link to the plan. Applied: `AGENTS.md` and `XLib/AGENTS.md` amended (present-tense rule replaces "Recently done", `HISTORY.md` added to the absolute-path exceptions as a per-person file, added to the document-state exemptions); `XLib/personal/Xonok/STATUS.md`'s inline "Recently done" rule now points at history; both `HISTORY.md` files created. `Xonok/XLib` is public and stays that way — the details are already public via the tracked `personal/Xonok/STATUS.md`, and the exposure that would matter is in the private Agents repo. → `plans/history-files.md`

## BACKFILL 2026-09-28 — reconstructed, not contemporaneous

Everything below was written on 2026-09-28 from the state files,
`machine-info.md` and the git log as they stood then. It is a reconstruction of
the record, not a record made at the time: **the time of day on each entry is
reconstructed, not observed.** A few dates come from the Agents git history,
which only reaches back to 2026-09-20 — this workspace's first commit.

Deliberately NOT backfilled: anything from 2026-09-27, which is still today's
work and still sits in the state files. Backfilling it now would duplicate it in
two places; it gets written when the state files are stripped.


- `1789098900` · 2026-09-11 06:55:00 · `XLib` — taskview filtering implemented and committed (`129e4c2`) with SPEC, IMPLEMENTATION_NOTES and example YAMLs; the tmux launcher passes `--context all` (uncommitted change in `tools/tmux-xlib.sh`).

- `1789100700` · 2026-09-11 07:25:00 · `XLib` — agent-coord's coder dispatch changed, then again to `worker-north-mini-code` later the same day. xlint taught that a return type hint is not a variable type hint.

- `1789114920` · 2026-09-11 11:22:00 · `XLib` — Coordinator model switched to `openrouter/nex-agi/nex-n2.5-pro:free` (from `opencode/ling-3.0-flash-fin-free`). Historical — the coordinator was removed on 2026-09-22.

- `1789117200` · 2026-09-11 12:00:00 · `XLib` — taskview due-date parsing fixed: date-only inputs now store NOON rather than midnight, and `%m-%d` without a year uses the current year (it was using 1900). `tasks.csv.example` was wrong in the same way — `due_ts` held ISO strings where unix timestamps belong. Existing midnight values in the live file were bumped +12h, shifting tasks 13/14/15 by a day, done with APPEND-ONLY rows. Still uncommitted.

- `1789117200` · 2026-09-11 12:00:00 · `XLib` — taskview current-task selection changed from most-recent-by-`chg_ts` to the first open task in due-date order — soonest due, overdue first, which the human confirmed as "most overdue in now". A just-touched tomorrow task could otherwise occupy the "now" slot while today's task sat in UPCOMING. Still uncommitted.

- `1789117200` · 2026-09-11 12:00:00 · `XLib` — Rule audit and AGENTS.md trim: ~157 lines (39%) cut from AGENTS.md (222→96), `style/common.md` (79→69) and `style/architecture.md` (101→80). Session lifecycle, tooling docs and the agent-roles section (duplicated in `.opencode/agent/`) removed; R2/R6 folded into R5. Still uncommitted, human commit pending.

- `1789209780` · 2026-09-12 13:43:00 · `XLib` — pybundle reviews done, then the review line was abandoned on 2026-09-12 in favour of a new spec.

- `1789577400` · 2026-09-16 19:50:00 · `XLib` — Work started on `xprod`; marduk bug fixed where it failed to create a require folder.

- `1789669560` · 2026-09-17 21:26:00 · `XLib` — Tool schema cache committed — described at the time as "a currently unused attempt at reducing token usage".

- `1789669860` · 2026-09-17 21:31:00 · `XLib` — Markdown indentation sweep: spaces converted to tabs in `.md` files, and a jump from 1 to 3 indents fixed.

- `1789895220` · 2026-09-20 12:07:00 · `XLib` — `agent-common` removed; orchestration inlined. skynet rolling window set to 28 days (`90a28a3`).

- `1789915740` · 2026-09-20 17:49:00 · `XLib` — Per-person structure introduced here too: `personal/Xonok/STATUS.md` tracked, root `STATUS.md` a gitignored per-person symlink created by `agent-coord.py personal init`. This is the convention `HISTORY.md` joined on 2026-09-28.

- `1790092680` · 2026-09-22 18:58:00 · `XLib` — Spec written for changing xlint (frontmatter + fence skip).

- `1790095500` · 2026-09-22 19:45:00 · `XLib` — xlint changed to ignore frontmatter in agent definitions, and to skip code blocks used as examples. Tabs in agent frontmatter were rejected the same day — that region is YAML, and YAML forbids tabs.

- `1790120460` · 2026-09-23 02:41:00 · `XLib` — `doc/development.md` created — the load-bearing rules and the spec→tests→implementation handoff contract, written as part of agent restructure Part 2. Linter errors in it fixed the next day (`9cd5984`).

- `1790325480` · 2026-09-25 11:38:00 · `XLib` — epiq project initialised.

- `1790444400` · 2026-09-26 20:40:00 · `XLib` — `ctx` added — the context-usage tool, so agents can check their own context fill instead of guessing. Not on PATH by default; see `.agents/machine-info.md` in the Agents workspace. Do not confuse it with `agent-coord.py ctx`, which is subagent dispatch bookkeeping.
