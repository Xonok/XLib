# History — Xonok

Append-only record of what happened and when, in this workspace. The state
files (`STATUS.md`, `TASKS.md`) state the present and only the present;
anything worth reading in six weeks goes here.

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

- `1790659623` · 2026-09-29 08:27:03 · `XLib` — Deleted the old-format per-agent notes `agent-notes-a1..a4.md` and the bare-role `agent-notes-planner.md` (16KB, the largest note in the workspace), on the human's ruling that ids are `<type>-<number>` and no type is called "a". Read in full first; they are git-ignored, so deletion is unrecoverable. The two live items they held were migrated first: **`tools/tmux-xlib.sh` kills the session named `$1` (default `xlib`) before creating it**, so a bare run destroys the human's live panel — recorded in the Agents workspace `machine-info.md`; and **`release.py` always writes** (no dry-run; `next_version` + unconditional write, flags are only `--minor`/`--major`/`--force`) — recorded in `tools/release/README.md`. Everything else was already tracked or superseded: the taskview context-filter discussion is `doc/plans/taskview-filter.md`, the real-time-status findings (`--port`/SSE) are duplicated verbatim in the Agents workspace `shared-notes.md`, the role-scoped identity design shipped as `role-N` ids, and the 2026-09-08 "every SPEC needs explicit approval" rule is superseded by `doc/development.md` (the human now writes specs; the planner writes plans). One of a4's env claims was already false: `python` exists (pyenv shim) and `pip` is installed — corrected in `machine-info.md`.

- `1790667052` · 2026-09-29 10:30:52 · `XLib` — Two pieces of untracked rot cleared out of the git-ignored `.agents/` folder. (1) **`.agents/plan-ai-code-viability.md` (7.3KB) promoted to `doc/plans/ai-code-viability.md` and indexed in `doc/plans/README.md`** — it had been untracked in the notes folder since 2026-09-10, so a plan the human calls critical long-term was invisible to `git status`, to every other machine, and to the plan index. One review session's insights had already landed in `doc/style/common.md` and AGENTS.md, but not one checklist box was ever ticked. The human's own task for it (`TASKS.md` — how legible can AI code be) had never been given a taskview id either; it is now **taskview #75**. (2) **`.agents/rotation.json` deleted** — the human confirmed rotation is dead. `ROTATION_CURSOR` is still declared at `tools/agent-coord.py:10` and referenced nowhere else, so that constant is now dead too; left in place because it is code and not mine to edit.

- `1790766743` · 2026-09-30 14:12:23 · `XLib` — `personal/Xonok/STATUS.md` rewritten to present-only. The file had last been reconciled against `8cb4daf` (2026-09-20) while master moved 51 commits and 173 files to `49a9ca5`, and it was edited twice more without the snapshot date being touched. What the stale file asserted, checked against the tree: `release.py` was recorded as broken (it calls `bundler.bundle()` and is fine), the xlint frontmatter/fence skip and the xlint+release move to `tools/` were listed as pending (both landed, `527a5c0`/`e483409` and `8a67eeb`), the agent-coord role-notes redesign was listed unmerged (`agent-coord.py:388` has shipped it), the tmux launcher was credited with passing `--context all` (it does not, and `--context` no longer exists in `taskview.py`), and the epiq "never pushed" blocker was live (the state branch is pushed and `AZHG0FK` was closed on the human's ruling 2026-09-29). The file also carried the two things its own governing rule bans: a dated "14 commits landed" retrospective and **two** `## Recently done` sections. All of it is retired here rather than deleted. The one claim that was not fiction is the pybundle redesign: it was a real attempt that stalled on the code's complexity, and the human is writing a fresh spec for it (epi `6MFX0Z1`).

- `1790766743` · 2026-09-30 14:12:23 · `XLib` — The `doc/` move (`2bcd9f4`, 2026-09-17) relocated `style/`, `plans/`, `reviews/` and `audits/` without touching a single pointer to them, so AGENTS.md's rule table sent every agent to four files that no longer existed, for 13 days. AGENTS.md's pointer table, the root readme, `tools/release/README.md`, `doc/plans/README.md` and `dev/xschema/SPEC.md` now name the real paths, and AGENTS.md points at `doc/development.md` — the canonical plan→spec→tests→implementation→review contract, which until now was named by no pointer at all. The nine unindexed files in `doc/plans/` are indexed. Left alone deliberately: `doc/reviews/` and `doc/audits/` keep the paths they were written with, because rewriting them would falsify a dated record. → `doc/plans/README.md`

- `1790767119` · 2026-09-30 14:18:39 · `XLib` — **epi `YM7ESHS`: `ROTATION_CURSOR` deleted from `tools/agent-coord.py`.** The constant at line 10 named `.agents/rotation.json`, a file the human had already deleted on 2026-09-29 (see the entry above, which left the constant behind because it was code and not the secretary's to edit); the `rotation` subcommand went on 2026-09-08 as the human's call, it diluted dispatch-by-strength. Nothing read it, so nothing broke: `py_compile` clean, `agent-coord.py status` and `--help` still run. `DIR` is still used seven times, so dropping one member of that constant block left no orphan import. Also removed the second half of the ticket — the `STATUS.md` bullet calling the file "a deletion candidate", a present that had been superseded 20 hours earlier; that bullet had already been traded for a live pointer to this ticket, which is now gone with it. No behavioural change.

- `1790766743` · 2026-09-30 14:12:23 · `XLib` — Human rulings on the drift sweep, applied. (1) **Versionless imports in dev-folder tests are correct** — a test imports the code being developed — so AGENTS.md's blanket wording now exempts them; `dev/xschema/tests/test_xschema.py` was flagged as a violation of a rule that should not have applied to it. (2) **`tools/tmux-xlib.sh` killing the session is intended**, on start and on exit. The real problem is deferred to when the launcher works from more than one repo: the default session name and the kill can no longer be the same string, or a bare run in one repo destroys another's panel. Constraint and shape recorded on epi `8VX1HVE`, which also now knows that per-repo `.taskview.yaml` discovery is part of its blast radius. (3) **Test folder is `test/`, never `tests/`** — `dev/xprod/` already complies, four libraries do not; the convention is written into `doc/development.md` and the rename is epi `2VD2XZC`. (4) **The four abandoned pybundle reviews and the empty `tools/pybundle/_/` stay**; the facts are now written down in `doc/reviews/README.md` so nobody cites those reviews as a verdict on the current bundler. (5) **Task #42 closed done** — the schema cache was built, so the follow-on is new task #77, "does it earn its place?", due 2026-10-05. **Task #17 cancelled, not done** — its subject was superseded by the human writing a new pybundle spec. (6) **`dev/xprod/`'s missing SPEC.md and VERSIONS.md is manual work for the human**, parked deliberately and filed as epi `DCF9EHW` as a record so the gap cannot quietly become an accepted exception.

- `1790766743` · 2026-09-30 14:12:23 · `XLib` — The eight realized plans are deleted, as the plan index's own rule requires ("when a plan becomes reality, the plan file is deleted and the library's own docs take over"): taskview-filter, skynet-second-tracker and its spec (which became `tools/marduk/`), xcsv, testing, release-script, xconf, reviewer-agent. This had been the human's open decision since 2026-09-11. **Deleting them was not mechanical — three carried unrealized content, and that content was moved first**, which is the part worth remembering: `tools/release/README.md` gained a `## Future work` section (export function, publish-dependencies, bundler code reuse, folder layout), `dev/xcsv/SPEC.md` gained `## Open questions` (multiline vs line-based quoted fields; comment lines inside quoted rows — neither was ever settled), and `dev/xtest/SPEC.md` recorded that xlint integration is still not wired. The rest was genuinely absorbed already: xconf's two open questions had become its SPEC's "Planned Changes", xcsv's roadmap and taskview's filter design were in their SPECs, and the reviewer plan's requirements were all live in `.opencode/agent/reviewer.md` with hash-keyed reviews in `doc/reviews/`. A blind delete would have lost four future-work items and two design questions. → `doc/plans/README.md`

- `1790766743` · 2026-09-30 14:12:23 · `XLib` — epi `7V6RW42` done and closed: the library-structure description is out of AGENTS.md (109 → 84 lines) and into `doc/library-structure.md`, with the Pointers-table row the ticket correctly demanded rather than leaving a file nothing points at. The split drawn is the one the ticket argues for — prohibitions stay in the rules file, descriptions of shape move out — and the discipline that produced is worth keeping: while writing the import-resolution section, the old text turned out to be wrong in a way nobody had noticed. It said unversioned names resolve "via `xlib_pins.py` or latest on disk", but no such file exists, and `xlib/__init__.py` does `importlib.import_module("xlib_pins")` — a top-level module, not one inside the package. An agent following the old sentence would have gone looking for a file that was never there. The `## Module format` section also went: it existed only to say the format rules live in AGENTS.md, which the extraction made half false. epi `28Y59JV` is unblocked and carries a note on what is left to slim. → `doc/library-structure.md`

- `1790766743` · 2026-09-30 14:12:23 · `XLib` — **A parallel agent hit the same files in this window, and the coordination did not hold.** `secretary-4` worked epi `YM7ESHS` at 14:18 — deleting the dead `ROTATION_CURSOR` from `tools/agent-coord.py`, appending its own `HISTORY.md` entry, and retiring the `STATUS.md` line about `rotation.json` — while this session held claims on `STATUS.md` and `HISTORY.md` and had already rewritten both. The claim system did not stop it, and this session's later `STATUS.md` write put back a `ROTATION_CURSOR` bullet the other agent had just removed, so for ~20 minutes the master status file asserted a constant that no longer existed. Caught by noticing an unexplained one-line diff in a file this session never edited, which is the only reason it was caught at all. Both `HISTORY.md` entries survived — appends do not collide the way whole-file rewrites do. The lesson worth keeping: **`STATUS.md` is a whole-file rewrite every time, so two agents in the same hour will silently undo each other**, and a claim that can be taken while held is not a claim. The empty `Done` lane on the board while nine tickets sit In progress, and the two `secretary` actors on the same repo, are the same problem wearing different clothes.
