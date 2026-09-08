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

## Snapshot (as of 2026-09-08 17:55 EEST)

- Repo on `master`; since the previous snapshot two commits landed:
  `8aa653e` (agent-coord: agent types + subagent dispatch) and `311ad73`
  (taskview fix, keeps hash `87c183` — the approved review applies).
  Working tree still carries uncommitted agent work (see Blocked).
- Live agents: `XLib/unknown-1` (XLib, active ~17:10 today), plus two Agents-
  workspace sessions. Role env (`OPENCODE_AGENT_ROLE`) not set anywhere yet —
  ids default to `unknown-N`.
- No file claims outstanding besides this file.

## In progress

| Item | Who | Done | Where |
|------|-----|------|-------|
| agent-coord role-notes redesign (id `role-N`, role notes, ctx budget) | planner (XLib) | ~90% — ctx/dispatch parts landed in `8aa653e`; role-notes part still in working tree | `plans/agent-coord-role-notes.md`, `tools/agent-coord.py` diff |
| reviewer pipeline: tests (xtest) in review + bump recommendation | planner (XLib) | in progress — plan doc being updated; Phase 1 approved | `plans/reviewer-agent.md` (dirty), `.agents/shared-notes.md` |
| agent rules: "Subagent context optimization" section in AGENTS.md | — | draft added to AGENTS.md (17:27), uncommitted, mirrors Agents workspace rules | `AGENTS.md` diff |
| taskview context-aware filter (design input from user) | planner | 0% — design phase, not a dispatch yet | `plans/taskview-filter.md`, `.agents/agent-notes-a1.md` (top) |
| skynet second tracker pane (live agent sessions) | planner | spec done, implementation not started | `plans/skynet-second-tracker.md` + `-spec.md` |
| taskview periodic time refresh (`--refresh-interval`) | — | planned only; already noted in taskview SPEC | `plans/taskview-time-refresh.md` |
| SPEC.md coverage | planner | xcsv ✅ approved; xschema ⏳ pending approval; xconf ❌ unwritten; xtest ❌ unwritten | notes a1; `xcsv/SPEC.md`, `xschema/SPEC.md` (untracked) |
| tmux-panel-priorities display | — | plan marked complete — needs a verify pass | `plans/tmux-panel-priorities.md` |

## Recently done

- **taskview** — reviewed twice, final review approved (hash `87c183`), committed
  `311ad73` (09-08). inotify + poll fallback; follow-ups tracked above.
- **agent-coord** — `8aa653e` committed: agent types and subagent dispatch
  (ctx budget). Role-notes redesign still outstanding (see In progress).
- **testing as release requirement** — Phase 1 approved (tests in dev folder,
  reviewer runs `xtest.run()`); being folded into the reviewer pipeline.
- **bundler** — "fix per current rules" pass done 09-06, behavior-identical (7
  fixtures byte-identical). Single-pass redesign still open in `plans/bundler.md`.
- **csv → xcsv, xconf, xschema, xtest** — released (xcsv `1_0_1` working;
  `1_0_0` kept as history). VERSIONS.md added for all released libs.
- **release script** — rewritten as thin wrapper on bundler (no import
  resolution, no output edits).
- **skynet Tracker 1** — per-model usage monitor done (`tools/skynet.py`).

## Blocked / needs attention

- **Uncommitted agent work in repo** (human owns commits): `tools/agent-coord.py`
  (role-notes part, on top of `8aa653e`), `AGENTS.md` (subagent-ctx section),
  `plans/reviewer-agent.md`, `plans/skynet-second-tracker.md`,
  `plans/tmux-panel-priorities.md`, untracked `STATUS.md`, `xcsv/SPEC.md`,
  `xschema/SPEC.md`, `plans/agent-coord-role-notes.md`,
  `plans/skynet-second-tracker-spec.md`, `reviews/taskview-2026-09-08-87c183.md`.
- `.agents/rotation.json` orphaned (rotation feature removed) — deletion candidate.
- Old slot-based notes (`agent-notes-a1..a4.md`) are legacy; new format is
  `agent-notes-{role}-{N}.md`. Do not treat them as current.
- OPENCODE_AGENT_ROLE not set by anything yet — role-notes design depends on it.
- xschema SPEC approval pending with planner; xconf/xtest SPECs unwritten.
- Bundler single-pass rewrite open design questions (`plans/bundler.md`).

## Pointers

- Roadmap: `plans/README.md` (list + cross-cutting decisions), `plans/build-order.md`.
- Live coordination state: `python3 tools/agent-coord.py status` (claims) / `news`.
- Shared user context: `.agents/shared-notes.md`. Per-agent state:
  `.agents/agent-notes-<id>.md` (role-scoped going forward).
- Reviews: `reviews/taskview-2026-09-08-*.md` (3 versions, newest = `87c183`).
- Code rules: `AGENTS.md` + `style/*.md`; library maps: `<lib>/SPEC.md`.