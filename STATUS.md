# XLib STATUS — master file

Current picture of what exists, is in progress, is blocked, and is done in this
workspace. This is the coordinator's quick-summary file: any agent that does
anything here updates it, so nobody has to crawl the repo to know what is going
on. Details live in the pointers at the bottom; this file stays a summary.

## Convention (all agents)

- Update this file when you start or finish something, or when your progress
  estimate changes. One line per work item: what, who, % done, where to look.
- Claim `STATUS.md` before editing (`python3 tools/agent-coord.py claim STATUS.md`),
  release when done.
- Move finished items to "Recently done" instead of deleting them. Nothing gets
  dropped without the human's sign-off.
- The % done number is **your own estimate of how done you think it is** — rough
  is fine, stale is not.

## Snapshot (as of 2026-09-11 ~14:00 EEST)

- Repo on `master` at `8cb4daf`; since the previous snapshot (`314c158`, 09-09)
  **14 commits landed**:
  - `8cb4daf` AGENTS.md coder dispatch → worker-north-mini-code
  - `129e4c2` taskview filtering implemented (SPEC + IMPLEMENTATION_NOTES + examples)
  - `7f4b52c` ignore more files (incl. `.opencode/` symlink dirs)
  - `6f90f32` / `155aa17` / `9665d1d` marduk added, integrated into tmux, panel sized
  - `f37357d` style rule: no empty line between class methods
  - `8e8f2c7` reviewer rules updated
  - `f0b81d0` xcsv updated + reviewed many times (post-release fixes landed)
  - `7987a3d` AGENTS.md factoring rule
  - `4c4da82` xconf SPEC written
  - `8f8cdb8` taskview prioritizes due date over changed date
  - `0785114` AGENTS.md requires type hints for public API
  - `80c0f9b` AGENTS.md dev submodule policy clarified
- **Working tree heavily uncommitted** — the pybundle single-pass redesign is the
  bulk (see below); also `release.py`, `tools/agent-coord.py`, `tools/tmux-xlib.sh`,
  `xlint/xlint.py`, `plans/bundler.md` modified.
- No file claims outstanding.
- `.opencode/` is a symlink to `/storage/Agents/.opencode/` (git-ignored, not untracked).
- **Coordinator model switched** to `openrouter/nex-agi/nex-n2.5-pro:free` (from `opencode/ling-3.0-flash-fin-free`). Updated `.opencode/agent/coordinator.md` and `.opencode/agent-common/coordinator.md`. Secretary, 09-11.

## In progress

| Item | Who | Done | Where |
|------|-----|------|-------|
| **pybundle single-pass bundler redesign** | — | redesign APPLIED but **all uncommitted**; reviews approve bugs 1–3 + try/except handling; versioned `1_0_3` in VERSIONS.md; 10/10 fixtures pass | `pybundle/` diff, `reviews/pybundle-review-*.md` |
| **release.py bundle-integration change** | — | uncommitted WIP; currently **broken** — calls `bundle()` on the target library, but no library defines it | `release/release.py` diff |
| agent-coord role-notes redesign | planner | ~90% — plan committed (`82bdeb4`); not merged into agent-coord.py yet | `plans/agent-coord-role-notes.md` |
| xlint return-type-hint check | — | new check works (scratch tests at root); **uncommitted**, not wired into style rules | `xlint/xlint.py` diff, `test_return_type_hints*.py` |
| taskview periodic time refresh | — | planned only; noted in taskview SPEC | `plans/taskview-time-refresh.md` |
| **xAudit tool** | secretary | planned + decided; implementation pending | `plans/xaudit.md` |
| **xlint + release move to `tools/`** | human-owned | decided; not started (git change, release.py carries uncommitted WIP) | blast radius in `plans/xaudit.md` |

## Recently done

- **Rule audit + AGENTS.md trim** — ~157 lines (39%) cut from AGENTS.md
  (222→96), common.md (79→69), architecture.md (101→80). Session lifecycle,
  tooling docs, agent roles (duped in `.opencode/agent/`), subagent ctx prose
  cut; R2/R6 folded into R5; Checking section removed. Secretary, 09-11.
  Uncommitted; human commit pending.
- **xAudit plan decided** — `plans/xaudit.md` (new): project-specific
  structural checks, xaudit owns watch loop + calls xlint one-shot.
- **taskview due-date fix** — `taskupdate.py parse_due`: date-only inputs now store
  noon (12:00) not midnight; `%m-%d` without year uses current year (was year 1900).
  `tasks.csv.example` corrected (due_ts was ISO strings → now Unix timestamps, noon
  convention documented). Existing midnight due_ts in `~/.local/share/taskview/tasks.csv`
  bumped +12h and tasks 13/14/15 shifted −1 day (yesterday/today/tomorrow), via
  append-only rows (09-11). Fix uncommitted, human commit pending.
- **taskview current-task selection** — was most-recent-by-`chg_ts` (a just-touched
  tomorrow task could occupy the "now" slot while today's task sat in UPCOMING).
  Now: first open task in due-date order (`pick_current` = soonest due, overdue
  first — human confirmed "most overdue in now"). SPEC.md current-task sections
  updated to match. Uncommitted, human commit pending.
- **taskview context-aware filter** — implemented + committed (`129e4c2`, 09-11); SPEC,
  IMPLEMENTATION_NOTES, example YAMLs added. tmux launcher passes `--context all`
  (uncommitted change in `tools/tmux-xlib.sh`).
- **skynet second tracker → marduk** — agent monitor added (`9665d1d`), integrated
  into the xlib tmux session (`155aa17`), panel made smaller for it (`6f90f32`).
- **SPEC coverage complete** — xconf SPEC written (`4c4da82`); all five libraries
  (xcsv, xconf, xschema, xtest, marduk) now have SPECs.
- **xcsv** — post-release fixes committed after many review rounds (`f0b81d0`);
  **xcsv `1_1_0` released** (minor: read API read_line/read_all, reschema support,
  exception hierarchy, raise_errors). Review: `reviews/xcsv-81f355dd.md`.
- **Review loop mandated** — programmer must repeat review→fix until reviewer sign-off
  (shared-notes 09-10; reviewer rules updated `8e8f2c7`).
- **API type hints required** — AGENTS.md rule (`0785114`); xlint check in the works.
- **coder dispatch** — AGENTS.md now maps coding → worker-north-mini-code (`8cb4daf`);
  the matching `agent-coord.py` WORKER_MAP change is still uncommitted.
- **taskview** — reviewed twice, final review approved (hash `87c183`), committed
  `311ad73` (09-08); inotify + poll fallback; delivered before this snapshot.
- **agent-coord** — `8aa653e`: agent types + subagent dispatch (ctx budget).
  Role-notes redesign plan committed (`82bdeb4`).
- **testing as release requirement** — Phase 1 approved (tests in dev folder,
  reviewer runs `xtest.run()`); folded into reviewer pipeline.
- **bundler v1** — "fix per current rules" pass behavior-identical (7 fixtures).
  Superseded by the single-pass redesign now in `pybundle/` (uncommitted).
- **csv → xcsv, xconf, xschema, xtest** — released; VERSIONS.md added for all.
- **release script** — previously rewritten as thin wrapper on bundler; the current
  uncommitted change moves bundling into the library entry (`lib.bundle`) — broken as-is.
- **skynet Tracker 1** — per-model usage monitor done (`tools/skynet.py`).
- **taskview/taskupdate.py** — helper for secretary committed (`314c158`).

## Blocked / needs attention

- **release.py broken as-is** (uncommitted): `getattr(lib_module, "bundle")` — no
  dev library defines `bundle` (verified: xcsv, xconf, xschema, xtest all lack it).
  Either a WIP step toward libraries self-bundling or a regression; releases would
  fail with AttributeError until resolved. Human owns this commit.
- **pybundle redesign fully uncommitted** (human owns commit): `bundler.py` deleted →
  `pybundle.py` new public entry; `bundler_impl.py` heavily rewritten; SPEC +
  BUG_FIX_SPEC + VERSIONS.md (1_0_0→1_0_3, 09-10/09-11) added; 3 new fixtures
  (self_alias, pep420_implicit, entry_only_imports; 10 total); 3 review docs in
  `reviews/` (latest approves). `plans/bundler.md` marks the redesign applied.
- **agent-coord.py WORKER_MAP** still says `coding → worker-mimo` in the committed
  version; AGENTS.md (`8cb4daf`) says worker-north-mini-code. Uncommitted diff fixes it.
- **xlint** return-type-hint check uncommitted; scratch files at repo root
  (`test_final.py`, `test_return_type_hints.py`, `test_return_type_hints2.py`) —
  cleanup candidates once the check is settled.
- `.agents/rotation.json` orphaned (rotation feature removed) — deletion candidate.
- Old slot-based notes (`agent-notes-a1..a4.md`) are legacy; new format is
  `agent-notes-{role}-{N}.md`. Do not treat them as current.
- OPENCODE_AGENT_ROLE not set by anything yet — role-notes design depends on it.
- pybundle now keeps a VERSIONS.md (1_0_0–1_0_3) although it's a tool, not released
  to `xlib/` — noting in case a decision is needed (AGENTS.md says tools get no versions).

## Pointers

- Roadmap: `plans/README.md` (list + cross-cutting decisions), `plans/build-order.md`.
- Live coordination state: `python3 tools/agent-coord.py status` (claims) / `news`.
- Shared user context: `.agents/shared-notes.md`. Per-agent state: `.agents/agent-notes-<id>.md` (role-scoped going forward).
- Reviews: `reviews/taskview-2026-09-08-*.md` (3 versions, newest = `87c183`), `reviews/xcsv-dev-review.md` (new, untracked).
- Code rules: `AGENTS.md` + `style/*.md`; library maps: `<lib>/SPEC.md`.