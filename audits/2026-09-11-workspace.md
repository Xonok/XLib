# Documentation audit — XLib workspace

Audit date: 2026-09-11
Auditor: XLib/auditor-1
Audited state: working tree at `fcda15e` (~07:30 EEST). Note: three commits
(`6fbd360` STATUS, `616d8c9` xlint, `fcda15e` agent-coord coder map) landed
*mid-audit*; findings below reflect the final state, and flag where committed
content and the committed STATUS.md no longer agree.

## Summary

**Needs work.**

The coordination-layer docs (STATUS.md, AGENTS.md) are accurate about the
big picture but several specific claims went stale within the last 24 hours
(xlint commit, WORKER_MAP commit, role-N ids, snapshot hash). Two library
SPECs (xcsv, pybundle) describe releases and code shapes that no longer exist
— the single most damaging category, since agents are explicitly told
(AGENTS.md, style/common.md) to build from SPECs. One committed handoff doc
(taskview/IMPLEMENTATION_NOTES.md) describes already-shipped work as pending.

Verified accurate during this audit: STATUS's 14-commit list (`314c158..8cb4daf`
counts 14, all subjects match), xcsv `1_1_0` released and matching
`xlib/xcsv_1_1_0.py`'s API, pybundle 10/10 fixtures passing (ran
`pybundle/test/test_bundler.py`), xconf/xtest/xschema SPECs matching their
code APIs, `.opencode/` symlink claim, `reviews/taskview-2026-09-08-87c183.md`
existing as newest taskview review, and the broken
`release.py` `getattr(lib_module, "bundle")` WIP.

## Findings

### Drift — documentation no longer matches code/state

**H1. xcsv/SPEC.md describes release 1_0_1 as current; 1_1_0 is released.**
`xcsv/SPEC.md:5` — "Current release (1_0_1) is write-only: write_line,
write_entry, serialize, tokenize, schema_parse, parse_line. The next version
adds a reader layer" — and `:11` "Current Write API (released, v1_0_1)". The
API table (lines 13–22) omits everything 1_1_0 added: `read_line`, `read_all`,
`write_line_tokens`, `write_all`, `parse_all`, `write_entries`, the exception
hierarchy, and `raise_errors`. Proof: `xlib/xcsv_1_1_0.py` (09-10) and
`xcsv/VERSIONS.md` 1_1_0 entry; `xcsv/xcsv.py` dev file exposes all of them.
The Roadmap section (lines 169–176) was updated for 1_1_0, so the file
contradicts itself: roadmap says 1_1_0 shipped Stage 1+2, overview says 1_0_1
is current and the reader layer is "next". An agent told to "read a library's
spec before working on it" (AGENTS.md pointers) would design against a
write-only API.

**H2. pybundle/SPEC.md references a deleted entry file and removed machinery.**
- `pybundle/SPEC.md:14`, `:118–120`, `:136` — "orchestrated by `bundle(entry)`
  in `pybundle/bundler.py`" / "`pybundle/bundler.py`: Public API only" /
  "`bundler.bundle(str(entry))`". `pybundle/bundler.py` is deleted in the
  working tree (git status `D pybundle/bundler.py`); the public entry is the
  untracked `pybundle/pybundle.py` with `bundle()` and `main()`.
- `:81–87` "Import Handling" and Known Limitations `:97–98`, `:101–106`
  describe the hoisted-preamble machinery — `_merge_imports`, `_MERGE_IMPORT`,
  `_MERGE_FROM` regexes — as current. VERSIONS.md 1_0_0 says "merge_imports
  dropped" and 1_0_3 says "removed dead code (_merge_imports, _topo,
  _MERGE_IMPORT, _MERGE_FROM)"; bundler_impl.py contains none of them; SPEC
  `:74` itself says "no global merged preamble; `_merge_imports` removed".
  The SPEC contradicts its own Import Handling section.
- Internal contradiction on SyntaxError: `:23` says `ast.parse` failure raises
  (hard stop, "never emitted as opaque"); `:110` (Known Limitation 6) says
  syntax-broken modules get `tree = None` and are "emitted as-is (no
  mangling)". Both cannot describe v1_x.
- `:140` — "All 7 fixtures must pass" with a list of 7; `pybundle/test/fixtures/`
  now has 10 (added: `self_alias`, `pep420_implicit`, `entry_only_imports`),
  all verified passing.

**H3. STATUS.md snapshot and three rows no longer match HEAD.**
- `STATUS.md:21` — "Repo on `master` at `8cb4daf`"; HEAD is `fcda15e` (three
  commits later). STATUS.md itself was committed in `6fbd360` without
  refreshing its own snapshot.
- `STATUS.md:93–94` — "agent-coord.py WORKER_MAP still says coding →
  worker-mimo in the committed version … Uncommitted diff fixes it." The fix
  is committed (`fcda15e`, "Update coder in agent-coord"); HEAD's WORKER_MAP
  is `worker-north-mini-code`.
- `STATUS.md:48` — xlint "new check works (scratch tests at root); uncommitted".
  The xlint change is committed (`616d8c9`); and see M1 — the "check" claim
  itself is misleading.

**M1. STATUS.md overstates the xlint "return-type-hint check".**
`STATUS.md:48` says "new check works". The committed xlint change is one regex
broadening in `xlint/xlint.py:79` (`check_def_one_line` now accepts `-> type`
before the colon). There is no return-type-hint check in xlint (verified:
`xlint/xlint.py` has checks double-blank, space-indent, trailing, def-one-line,
final-newline, imports only; `--no-*` flags list the same). The scratch tests
claim "Public function without return type hint - should be flagged" — xlint
flags nothing of the sort.

**M2. AGENTS.md tmux description is stale.**
`AGENTS.md:129` — "runs `xlint --watch` in one pane, a shell in another, and
the `skynet` agent monitor in a third." Actual `tools/tmux-xlib.sh` has four
panes (xlint, taskview, skynet, marduk) and no shell pane since `9665d1d` /
`155aa17` (09-10).

**M3. AGENTS.md agent-id / notes scheme contradicts the implementation.**
`AGENTS.md:11` — "prints your agent id (`a1` or `a2` …)"; `:5`, `:41` —
notes at `.agents/agent-notes-<id>.md`. The committed `agent-coord.py`
(`8aa653e`) allocates role-based ids — `agent_id = "%s/%s-%d" % (tag, role, n)`
(line 202) — and this session's id came back `XLib/auditor-1`. Status shows
`agent-notes-{role}-{N}.md` is the new format and `agent-notes-a1..a4.md` are
"legacy" (`STATUS.md:99–100`), and `.agents/` contains exactly that mix.
AGENTS.md is the doc every agent reads first; it still documents the outdated
scheme.

**M4. STATUS.md: line 47 contradicts the committed agent-coord role-notes work.**
"agent-coord role-notes redesign … not merged into agent-coord.py yet".
Committed `HEAD:tools/agent-coord.py` already implements role-N ids, the
`role-note` / `role-claim` / `role-release` / `role-status` commands, and
old-format upgrade (`:156`); my `id`/`note` outputs confirm it — so `:47`
is wrong as written. **Update (human confirm, 09-11): the last dependency,
`OPENCODE_AGENT_ROLE`, is wired too** — `oc-agent`
(`/home/xonok/.local/bin/oc-agent` → `/storage/Scripts/oc-agent:27`) exports
`OPENCODE_AGENT_ROLE="$AGENT"` before spawning each agent. The redesign is
therefore done end-to-end; `STATUS.md:101` ("OPENCODE_AGENT_ROLE not set by
anything yet") is stale and the `:47` row should move from In progress to
Recently done. Corroborating staleness in the Agents workspace:
`/storage/Agents/.agents/role-notes-coordinator.md:73` and
`agent-notes-unknown-2.md:24` still claim the env is unset — a session ran
with role `unknown`, which is consistent with a launch path that predates the
oc-agent export, not with current oc-agent behavior.

**M5. STATUS.md pointers reference a nonexistent review.**
`STATUS.md:110` — "`reviews/xcsv-dev-review.md` (new, untracked)". The file
does not exist in `reviews/` (which holds only taskview-2026-09-08-*.md ×3,
xcsv-81f355dd.md, pybundle-review*.md ×3). The actual xcsv review,
`reviews/xcsv-81f355dd.md`, is already referenced at `:62`.

**L1. marduk/SPEC.md CLI examples use a wrong path.**
`marduk/SPEC.md:150–153` — "`python3 tools/marduk.py --watch`". Marduk lives
in `marduk/marduk.py` and is invoked as `python3 -m marduk.marduk --watch`
(`tools/tmux-xlib.sh:19`).

**L2. pybundle/VERSIONS.md entries contradict each other.**
1_0_0 entry says "merge_imports dropped"; 1_0_3 says "removed dead code
(_merge_imports, _topo, _MERGE_IMPORT, _MERGE_FROM)". Also 1_0_3 does not
record the bugs 1–3 closures that the reviews in `reviews/pybundle-review-*.md`
and STATUS (`:45`, "reviews approve bugs 1–3 + try/except handling") describe.

**L3. worker-mimo agent description is stale.**
`.opencode/agent/worker-mimo.md` — "Primary coding worker (dispatch coding)".
Coding now dispatches to `worker-north-mini-code` (AGENTS.md `8cb4daf`,
WORKER_MAP `fcda15e`, and PC: `tools/agent-coord.py:406`). Lives in the
symlinked `/storage/Agents` workspace; change there or via human.

### Redundancy — duplicated / overlapping content

**R1 (M). taskview/IMPLEMENTATION_NOTES.md duplicates SPEC.md and describes
shipped work as pending.** The file is a pre-implementation handoff brief —
":3 For the Programmer", ":9 Required Changes to taskview.py", ":109–120"
unchecked testing checklist. The feature is committed (`129e4c2`; verified in
`taskview/taskview.py`: `--context`, filter eval with never_show/always_show,
inotify+poll). Its content (filter structure, eval order, integration snippet,
deps, example files) is already in `taskview/SPEC.md:34–58`, `:104–115`,
`:123–133`, `:141`. It also contradicts current reality: it says the default
context is `default.yaml` and missing file = error (SPEC `:55`), while the
actual tmux pane runs `--context all` and code falls back to
`TASKVIEW_CONTEXT` then `"default"` (`taskview.py:38`).

**R2 (L). plans/README.md contents index is incomplete and its own rule is
violated.** Six existing plan files are not listed: `bundler.md` (the
exemplar map doc AGENTS.md points everyone at!), `agent-coord-role-notes.md`,
`code-analysis.md`, `comment-types.md`, `skynet-second-tracker-spec.md`,
`taskview-filter.md`. Meanwhile `plans/README.md:5` states "When a plan
becomes reality, the plan file is deleted" — reality-plans that are still
present: `taskview-filter.md`, `skynet-second-tracker.md` (+spec), `xcsv.md`,
`testing.md`, `release-script.md`, `xconf.md`. Either the rule or the files.

### Structure

**S1 (M). Repo root is a scratch dump, only partially flagged.**
`test_final.py`, `test_return_type_hints.py`, `test_return_type_hints2.py`
(untracked) and `test_indent_edge.py` (tracked) sit at the root. STATUS
(`:95–97`) flags the first three as cleanup candidates but not
`test_indent_edge.py`, which is part of the same scratch set and committed.
Nothing references these files except STATUS itself (grep across
`.py`/`.md`).

**S2 (L). SPEC size vs the stated map rule.** `style/common.md:10–13` says a
SPEC "aim[s] for well under 100 lines"; xcsv is 185, xschema 103, pybundle
185, marduk 254, taskview 154. xcsv/xschema are libraries proper; the float
is partly roadmap content, but marduk at 254 lines (a tool) doubles as a
plan doc — see R1/C3 for the same pattern in taskview.

**S3 (L). Review-doc naming convention not followed.** AGENTS.md (Reviewer
role) defines `reviews/<lib>-<hash>.md`. `xcsv-81f355dd.md` and
`taskview-2026-09-08-87c183.md` follow it; the three pybundle reviews
(`pybundle-review.md`, `pybundle-review-next.md`,
`pybundle-review-2026-09-10.md`) carry no hash and inconsistent names, so the
"change detector" property (hash ties review to dev-folder content) is lost
for pybundle.

### Completeness

**C1 (M). release/README.md references a deleted module.**
`release/README.md:30` — "It calls the bundler (`pybundle/bundler.py`)".
`pybundle/bundler.py` is deleted in the working tree; the committed
`release/release.py:7` (`from pybundle import bundler`) will break the moment
the deletion lands. The uncommitted release.py WIP (`getattr(lib_module,
"bundle")`, `:71–73`) is a different, separately-broken design; README
describes neither. Needs a rewrite in whichever direction the human commits.

**C2 (L). xcsv SPEC "Planned changes" state.** xcsv/SPEC.md has no
"Planned changes" section even though AGENTS.md's SPEC contract asks for one
when future work exists; Stage 3 (`file_reader`/`file_writer`) is planned
(roadmap row 4, `:176`) but lives only in the roadmap table, not a planned-
changes section. Minor.

### AI-readiness

**A1 (M). SPECs that contradict reality are the worst case for agents.**
AGENTS.md and style/common.md tell agents to read the SPEC before working on a
library, and xcsv/SPEC.md (H1) + pybundle/SPEC.md (H2) send them at stale
APIs. A model has no way to detect the drift by reading the doc; it will
generate code against 1_0_1's write-only surface or the deleted `bundler.py`.
Fix H1/H2 before any agent task touching xcsv or pybundle.

**A2 (L). IMPLEMENTATION_NOTES.md reads as pending work to a reader.**
Unchecked checkboxes (`:111–120`) and "Required Changes" phrasing signal
in-progress state to agents; it is shipped code. See R1.

## Cut candidates

1. **`taskview/IMPLEMENTATION_NOTES.md`** — stale handoff brief; duplicates
   `taskview/SPEC.md` (filter structure `:34–58`, filter evaluation `:104–115`,
   integration `:123–133`, examples `:141`) and misrepresents shipped work as
   pending, including a wrong default-context description. Replacement:
   one-line reference in SPEC.md — "See `taskview/SPEC.md` for filter format
   and evaluation." Evidence: feature committed in `129e4c2`; SPEC carries all
   the information; nothing references the file (grep: only STATUS' commit
   description).
2. **Root scratch tests (`test_final.py`, `test_return_type_hints.py`,
   `test_return_type_hints2.py`, `test_indent_edge.py`)** — STATUS itself
   calls them cleanup candidates; no code references them; they test a check
   that doesn't exist (see M1). If the return-type-hint check is wanted,
   move the assertions into `xlint/` tests; otherwise delete. Evidence:
   grep across repo finds references only in STATUS.md.
3. **pybundle/SPEC.md sections describing removed machinery** —
   "Import Handling" (`:81–87`), Known Limitations 1/3/4 (`:97–98`,
   `:101–106`) and limitation 6's opaque-SyntaxError paragraph (`:110`). They
   describe `_merge_imports`/regex preamble/`tree = None` behavior that
   VERSIONS 1_0_0/1_0_3 and bundler_impl.py contradict. Rewrite to current
   single-pass behavior or delete. Evidence: SPEC's own `:74`; VERSIONS entries;
   `bundler_impl.py` grep (no `_merge_imports`, no `_MERGE_*`).

## Quick wins

1. `xcsv/SPEC.md:5,11` — change "Current release (1_0_1) is write-only" to
   "Current release 1_1_0", and extend the API table with `read_line`,
   `read_all`, `write_line_tokens`, `write_all`, `parse_all`, `write_entries`,
   `raise_errors`, and the exception hierarchy (all present in
   `xcsv/xcsv.py`).
2. `STATUS.md` — refresh snapshot hash to `fcda15e`; update rows at `:47`,
   `:48`, `:93–94` (role-notes complete: merged in `8aa653e`, env var wired
   via oc-agent — see M4; xlint fix committed; WORKER_MAP committed); drop
   `:101` ("OPENCODE_AGENT_ROLE not set by anything yet"); delete the
   `reviews/xcsv-dev-review.md` pointer at `:110` (review is
   `xcsv-81f355dd.md`).
3. `AGENTS.md:129` — describe the four-pane launcher (xlint, taskview,
   skynet, marduk) and drop "a shell in another".
4. `AGENTS.md:5,11,41` — update the id/notes scheme to `role-N` ids and
   `.agents/agent-notes-{role}-{N}.md`, and mark `a1..a4`-style notes as
   legacy (matches `STATUS.md:99–100`).
5. `pybundle/SPEC.md` — rename `bundler.py` → `pybundle.py` (`:14`, `:118–120`,
   `:136`), update fixtures to 10 with the three new names (`:140`), resolve
   the SyntaxError contradiction (`:23` vs `:110`).
6. `release/README.md:30` — point at `pybundle/pybundle.py`, and rewrite once
   the release.py direction (lib.bundle vs bundler) is committed.
7. `marduk/SPEC.md:150–153` — `python3 tools/marduk.py` →
   `python3 -m marduk.marduk`.
8. Commit `tools/tmux-xlib.sh`'s `--context all` change (human-owned; it's the
   only uncommitted line, matching `STATUS.md:55`).
9. `plans/README.md` — add the six missing entries (`bundler.md` first) or
   delete reality-plans per its own rule.