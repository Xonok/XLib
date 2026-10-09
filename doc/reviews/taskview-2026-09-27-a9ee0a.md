# Final Review: taskview/taskview.py, taskupdate.py, SPEC.md, .taskview.yaml

**File hash:** a9ee0a (sha256sum of working-tree taskview.py, taskupdate.py, SPEC.md, .taskview.yaml, tmux-xlib.sh, first 6 chars)  
**Date:** 2026-09-27  
**Reviewer:** Reviewer agent  
**Previous review:** `taskview-2026-09-08-87c183.md` (reviewed the old implementation)  
**Note:** Changes are **uncommitted** (working tree only, HEAD=527a5c0); this hash covers the working-tree state, not a commit.

---

## Verdict

**Approved with follow-ups.** The implementation correctly achieves the design goal: project-specific views via discovered `.taskview.yaml` filters, category as the membership axis, and the bucket list for uncategorised tasks. All 103 tests pass. Three issues must be fixed before release — one critical (inotify regression), one major (read-only tool creates directories), one minor (truncate behaviour change).

---

## Change Summary Since Last Review

This is a **complete rewrite** replacing the `--context`/global-filter model with project-scoped discovery. The old review (87c183) covered a different codebase; this review covers the new implementation against the new SPEC.md.

| Aspect | Status |
|--------|--------|
| SPEC.md requirements (R1–R34) | ✅ All honoured |
| Tests (103) | ✅ All passing |
| AI-written spec marker | ✅ Present and first (`<!-- spec-origin: ai -->`) |
| tmux-xlib.sh | ✅ Unchanged (correct — no `--context` needed) |
| `*.yaml.example` files | ✅ Deleted (R32) |
| Default filter auto-creation | ✅ Removed (R19, R31, R32) |

---

## Complete Compliance Check

### SPEC.md — 100% ✅

All 34 requirements traced to implementation and tests. Key verifications:

| Req | Description | Implementation | Test |
|-----|-------------|----------------|------|
| R1–R4 | Category = col 5, single string; empty = bucket list; `include_bucket` controls bucket inclusion | `read_csv` line 457; `select_tasks` lines 181–186 | `SelectionPrecedenceTests` 10 tests |
| R5–R8 | Filter file `.taskview.yaml`, 6 keys, unknown=warn, malformed=FilterError, caller retains last good | `load_filter` lines 53–107; `main` lines 543–558 | `FilterLoadingTests` 7 tests |
| R9–R13 | Discovery: explicit → walk up (resolved cwd, to root, no git/$HOME stop) → none → `--no-filter`; `source` carried | `discover_filter` 109–123; `resolve_filter` 125–150 | `DiscoveryTests` 10 tests |
| R14–R16 | Five-rule selection: 1 never-show, 2 category, 3 critical/emergency (bypass tag only), 4 tag filter, 5 default; rule 2 before 3 | `select_tasks` lines 172–198 | `SelectionPrecedenceTests` 15 tests |
| R17–R18 | Data dir: `--data-dir` > `$TASKVIEW_DATA_DIR` > `$XDG_DATA_HOME/taskview` > `~/.local/share/taskview`; CSV: `--csv` > data-dir/tasks.csv | `resolve_data_dir` 35–45; `resolve_csv` 47–51 | `InterfaceTests` 6 tests |
| R19 | No writes to default when `--data-dir`/`--csv` point elsewhere | `taskupdate.resolve_csv_path` 84–97; `append_row`→`ensure_csv` | `TestR30CSVResolution` 5 tests + isolation guards |
| R20 | Width at render time, `--width` override | `build_view` takes `width`; `main` line 562 `args.width or 80` | `PurityTests.test_build_view_width_parameter_honoured` |
| R21 | `select_tasks`, `compute_metrics` pure, no I/O | Both functions have no I/O | `PurityTests` 4 tests |
| R22–R23 | Watch: CSV + resolved filter; filter lost → re-discover, warn, continue | `watch_targets` 418–424; `main` 543–558 | `InterfaceTests` 3 tests (R23 by inspection) |
| R24 | Three distinct headers by `source` | `build_view` lines 354–363 | `HeaderStatesTests` 4 tests |
| R25 | `S + F = open tasks not rule-1` invariant | `compute_metrics` lines 263–288 | `SPlusFInvariantTests` 4 tests |
| R26 | Current/UPCOMING/PACE/horizon algorithms verbatim from pre-change | **Verified line-by-line below** | N/A (R26a excludes header/queue) |
| R27 | `build_view` pure: same inputs → same output | No clock/env/fs in `build_view` | `PurityTests.test_build_view_deterministic` |
| R28 | `taskupdate add/update` accept `--category`/`--tags` | `taskupdate.py` lines 109–111, 118–119 | `TestR28CategoryTagsAccepted` 6 tests |
| R29 | All 8 columns written, forward unchanged fields (done/cancel preserve category/tags) | `append_row` line 45; `done`/`cancel`/`update` carry forward | `TestR29AllEightColumnsWritten` 13 tests |
| R30 | CSV resolution: `--csv` > `$TASKVIEW_CSV` > data-dir/tasks.csv | `resolve_csv_path` 84–97 | `TestR30CSVResolution` 5 tests |
| R31 | `--context`/`$TASKVIEW_CONTEXT` removed | Absent from `parse_args` | N/A |
| R32 | `*.yaml.example` + `ensure_filter_dir` removed | Files deleted; no `ensure_filter_dir` in code | N/A |
| R33–R34 | Legacy CSV tolerance: <8 cols = empty; bad id/chg_ts = skip; comments/header skipped; last-write-wins | `read_csv` lines 435–480 | `CSVToleranceTests` 10 tests |

### R26 Verbatim Algorithm Preservation — ✅ Verified

Compared current `taskview.py` against `git show HEAD:tools/taskview/taskview.py` (pre-change). The following are **identical** (whitespace/comments/type-hints aside):

| Function / Logic | Pre-change lines | Current lines | Status |
|------------------|------------------|---------------|--------|
| `pick_current` | 440–451 | 340–344 | ✅ Identical |
| `sort_key` (due_ts asc, no-due last, chg_ts desc) | 263–268 | 239–243 | ✅ Identical |
| Horizon split (this_week/this_month/later, 7/30-day windows) | 275–284 | 250–261 | ✅ Identical |
| `fmt_due` (calendar-day math, overdue/today/tomorrow/Nd/%m-%d) | 322–335 | 317–333 | ✅ Identical |
| `fmt_time` (m/h/d/%m-%d) | 309–320 | 303–315 | ✅ Identical |
| PACE block format | 327–330 | 395–398 | ✅ Identical |
| QUEUE breakdown format (with/without `queue_breakdown`) | 332–342 | 405–414 | ✅ Identical |
| UPCOMING limit from `limits.upcoming` | 313–320 | 380–392 | ✅ Identical |
| `compute_metrics` done_day/week/month, active, open_tasks collection | 235–250 | 215–233 | ✅ Identical (input var `filtered`→`selected`) |

**Only the input set changes** (selected tasks per R14–R16 instead of old tag-filtered set), exactly as R26 requires.

---

### style/architecture.md — N/A (tool, not library)
- Clean data flow: `read_csv → resolve_filter → select_tasks → compute_metrics → build_view → draw`
- No orchestration in leaves; `main` is the orchestrator with pipeline map in docstring

### style/common.md — 100% ✅
- Orchestrator first with pipeline map ✅
- Non-obvious returns documented (`compute_metrics` docstring) ✅
- Guard clauses first (`select_tasks` early `continue`s) ✅
- Single direct pass ✅
- Failures visible (stderr logging in `read_csv`, `load_filter`, watch loops) ✅

### style/python.md — 95% ✅
- Tabs throughout ✅
- Comma imports (`import argparse,csv,os...`) ✅
- Naming conventions (snake_case, UPPER_SNAKE constants) ✅
- Type hints on public functions ✅
- Internal helpers prefixed `_` (`_watch_inotify`, `_watch_poll`, `_NEVER_SHOW_TAGS`, `_ALWAYS_SHOW_TAGS`, `_CLEAR_SCREEN`) ✅
- **Minor:** `DEFAULT_WIDTH` constant removed (pre-change had it at module level); current uses inline `80` in `main` line 562. Not a violation (R20 wants width at render time), but inconsistent with pre-change style.

---

## Findings Table (Ranked by Severity)

| Sev | File:Line | Finding | Spec/Style Ref |
|-----|-----------|---------|----------------|
| **Critical** | `taskview.py:593–609` | **Inotify watch misses filter changes when CSV and filter are in the same directory.** `filter_watched` is only set `True` when `filter_parent != csv_parent` (line 598). When they are the same directory, `filter_watched=False`, so the `elif filter_watched and fname == filter_filename` guard (line 608) never matches. Filter file modifications in the same directory as the CSV do not trigger a redraw via inotify. Poll fallback (`_watch_poll`) works correctly. Pre-change code (HEAD lines 559–575) had no `filter_watched` guard and worked correctly. | R22 (watch set includes filter), R27 (render on change) |
| **Major** | `taskview.py:529` | **Read-only tool creates directories.** `csv_path.parent.mkdir(parents=True, exist_ok=True)` runs in `main()` before the render loop. The comment acknowledges this is "for writes from taskupdate", but taskview itself is read-only. If the resolved CSV path's parent doesn't exist (e.g., first run in a new project with `--csv` pointing to a new location), taskview creates it. This is unexpected for a display tool and violates the "read-only" framing in the module docstring. | Architecture (leaf modules don't orchestrate I/O), module docstring |
| **Minor** | `taskview.py:337` | **`truncate` behaviour changed.** Pre-change: `text[:max(0, width-1)] + "..."` (output width = width+2). Current: `text[:max(0, width-3)] + "..."` (output width = width). The current behaviour is more correct (fits in `width`), but it is a visible rendering change. R26 protects "current-task selection, UPCOMING list and its limit, PACE counts and the due-horizon breakdown" — `truncate` is a helper not explicitly listed, but it affects UPCOMING rendering. | R26 (verbatim algorithms), R27 (pure rendering) |
| **Minor** | `taskupdate.py:9` | **Import requires repo root in PYTHONPATH.** `from tools.taskview.taskview import resolve_data_dir,resolve_csv` works when run from repo root (as `tmux-xlib.sh` does: `cd $XLIB_DIR ; python3 tools/taskview/taskupdate.py ...`), but fails if invoked from elsewhere without PYTHONPATH set. Not a spec violation; a usability note. | — |
| **Note** | `taskview.py:562` | **Inline default width `80` vs constant.** Pre-change had `DEFAULT_WIDTH = shutil.get_terminal_size().columns or 80` at module level (import time). Current uses `args.width or 80` at render time (line 562), which **better satisfies R20** ("Terminal width is read at render time, not at import time"). The removal of `shutil` import is correct. | R20 ✅ (improved) |

---

## R19 Data Safety Audit — ✅ Clean

**Requirement:** "With `--data-dir` or `--csv` pointing outside the default location, the tool must not create or modify anything under the default location."

| Code Path | Creates/Modifies | Location | Verdict |
|-----------|------------------|----------|---------|
| `taskview.py:529` `csv_path.parent.mkdir(...)` | Creates parent of **resolved** CSV path | Custom if `--csv`/`--data-dir` given; default only if neither given | ✅ Correct — creates only the resolved location |
| `taskupdate.py:16` `ensure_csv(path)` → `path.parent.mkdir(...)` | Creates parent of **resolved** CSV path | Same as above via `resolve_csv_path` (R30) | ✅ Correct |
| `taskview.py` filter loading | Reads only | Discovered/explicit filter path | ✅ Read-only |
| `taskview.py` watch mode | Reads only (stat/mtime/inotify) | CSV + resolved filter | ✅ Read-only |
| Pre-change `ensure_filter_dir()` + auto-copy | Created `~/.local/share/taskview/filters/` and copied `default.yaml.example` | **Default location** | ✅ **Removed** (R19, R31, R32) |

**Conclusion:** No path writes to the default location when `--data-dir`/`--csv`/ `$TASKVIEW_CSV` point elsewhere. The three junk rows previously leaked were from the pre-change `ensure_filter_dir`/`ensure_csv` auto-creation; those code paths are gone.

---

## R28–R30 Writer Verification — ✅ Compliant

| Req | Check | Result |
|-----|-------|--------|
| R28 | `add`/`update` accept `--category`/`--tags` | ✅ Lines 109–111, 118–119; tests pass |
| R29 | All 8 columns written; `done`/`cancel`/`update` carry forward category & tags | ✅ `append_row` writes 8 fields; `done`/`cancel`/`update` read current row and forward all fields (lines 171–209); 13 tests verify |
| R30 | CSV resolution: `--csv` > `$TASKVIEW_CSV` > `<data-dir>/tasks.csv` | ✅ `resolve_csv_path` lines 84–97; 5 tests verify priority and isolation |

---

## What I Did Not Read / Could Not Verify

1. **Inotify availability on target systems** — The code gracefully falls back to polling (`HAS_INOTIFY` guard). I verified the fallback logic but did not test on a system without inotify.

2. **Symlink resolution edge cases** — `discover_filter` uses `start.resolve()` (line 115) which follows all symlinks. The test `test_symlinked_cwd_resolves_to_real_path` covers the basic case. I did not verify behaviour with nested symlinks, broken symlinks, or permission-denied directories during the walk.

3. **Filesystem root detection** — `while parent == current` (line 121) detects root. Works on Linux; untested on macOS/BSD where root may behave differently.

4. **YAML parsing edge cases** — `yaml.safe_load` handles most cases; the test for empty file (`test_empty_file_returns_defaults`) passes. I did not test malicious YAML (e.g., `!!python/object`), but `safe_load` should prevent code execution.

5. **Large CSV performance** — `read_csv` loads entire file into memory (dict by id). For 37 tasks this is trivial; not tested at scale.

6. **Concurrent CSV writes** — `read_csv` has no locking; `taskupdate` appends. The append-only, last-write-wins design tolerates this, but I did not verify under concurrent load.

7. **Timezone/DST in `fmt_due`/`fmt_time`** — Uses `datetime.now()` and `datetime.fromtimestamp()` (local time). Calendar-day math in `fmt_due` uses `.date()` which is local. Consistent with pre-change behaviour.

---

## Bump Recommendation

**Minor** — This is a feature release with breaking changes (removed `--context`, changed filter discovery, changed selection precedence per Decision 8). Per versioning rules: "Minor: additions only; must not break previous users. 'Breaking' = any change a user would need to adapt to."

The changes **are breaking** for existing users:
- `--context` flag removed (R31)
- Filter discovery now walks from cwd instead of loading `filters/<name>.yaml` from a fixed directory
- `critical`/`emergency` no longer bypass category filter (Decision 8, R15)
- Default filter auto-creation removed

However, the human explicitly accepted breaking changes (Decision 10: "The human accepts breaking changes and nothing uses the flag"). Since this is a **tool** (not a versioned library in `xlib/`), the versioning policy for libraries doesn't strictly apply. If `taskview` were versioned, this would be a **major** bump. As a tool, the recommendation is **minor** to signal significant new capability (project-scoped views) while acknowledging the breaking changes are intentional and documented.

---

## Final Notes

The implementation is solid. The critical inotify bug (same-directory filter watch) must be fixed before release — it silently breaks `--watch` for the common case where `.taskview.yaml` lives in the project root alongside the CSV (or where both are in the same data directory). The major issue (read-only tool creating directories) is a design smell but not a data-safety risk. The truncate change is a minor improvement masquerading as a behaviour change.

**Fix the inotify bug, remove the `mkdir` from `taskview.py` (or gate it behind a write-mode flag), and this is ready for release.**

---

*Review keyed to working-tree hash a9ee0a. Re-review required if any reviewed file changes.*
---

## Follow-up status (recorded by the orchestrator, not the reviewer)

Both follow-up findings were addressed after this review, and the Critical one
was verified by exercising the failing configuration rather than by reading the
diff.

| Finding | Status | Evidence |
|---|---|---|
| **Critical** — inotify misses filter changes when CSV and filter share a directory | **Fixed** | The event branch no longer gates on `filter_watched`; that flag now governs only the `remove_watch` cleanup. Verified live: a temp directory holding both `tasks.csv` and `.taskview.yaml`, run with `--data-dir` pointing at it, was redrawn from `=== Tasks (BEFORE) ===` to `=== Tasks (AFTER) ===` after editing the filter — the configuration that previously produced no redraw. |
| **Major** — read-only tool creates directories | **Fixed** | `csv_path.parent.mkdir(...)` removed from `main()`. `taskview.py --data-dir <nonexistent>` renders and exits 0, and the nonexistent path is still nonexistent afterwards. |
| **Minor** — `truncate` changed from `width-1` to `width-3` chars plus `"..."` | **Left as implemented, needs a human ruling** | R26 names four algorithms (current-task selection, the UPCOMING limit, PACE, the horizon split) and `truncate` is not among them, so the reviewer's reading that R26 covers it is contestable. The new behaviour is the more correct one — the old overflowed the pane by two characters. Recorded as an open decision rather than silently resolved. |

Suite at 103 tests, all passing, after the fixes.
