# Task View Context-Aware Filtering

## Goal
Add context-aware filtering to the tmux task view (`taskview/taskview.py`) so the display shows tasks relevant to the user's current situation (workday, evening, weekend, etc.) while preserving the existing urgency ranking.

## Current State
- `taskview/taskview.py` reads `tasks.csv`, folds to current state, ranks by urgency/deadline
- Display sections: Current task, Upcoming, Pace, Queue
- No concept of categories, contexts, or filtering — all open tasks compete equally
- `--watch` mode polls CSV every 1s, redraws on change

## Requirements
1. **External filter files** — filter logic lives in separate, human-editable files (one per context), not hardcoded in `taskview.py`
2. **Manual context switching** — user explicitly chooses context via `--context NAME` (not automatic by time)
3. **Tag-based matching** — tasks shown if they have at least one tag matching the active context's tag list
4. **Complements urgency ranking** — filter narrows what's shown; existing priority order within the filtered set is preserved
5. **Override mechanism** — global `always_show` tags bypass context filter (e.g., critical/emergency)

## Design

### 1. Filter File Format

**Location**: `~/.local/share/taskview/filters/` (directory containing one YAML file per context)

**File naming**: `<context-name>.yaml` (e.g., `work.yaml`, `evening.yaml`, `weekend.yaml`)

**Structure** (per file):
```yaml
# taskview filter — work context
# Edit this file to define which tags are shown in this context

# Human-readable label for UI
label: "Work Hours"

# Tags that cause a task to be shown in this context (OR logic: match ANY)
tags: ["work", "admin", "oncall", "blocking"]

# Optional: tags that ALWAYS show regardless of context (global override)
# Typically defined once in a special file or built-in defaults
# always_show_tags: ["critical", "emergency"]

# Display limits for this context
limits:
  upcoming: 5        # max upcoming tasks to show
  queue_breakdown: true
```

**Notes on format**:
- YAML chosen for: comments, readability, native list/dict support
- One file per context = easy to add/edit/remove contexts without touching other files
- Context name derived from filename (without `.yaml` extension)
- `tags` list = the ONLY filter criterion; task matches if `set(task.tags) ∩ set(filter.tags) ≠ ∅`
- `category`, `importance`, `urgent_within` are NOT used for filtering (kept in CSV for other uses)

---

### 2. Task Data Model Extensions

The CSV schema is extended with three new columns (Option A — extend CSV schema):

```
id,status,title,due_ts,chg_ts,category,tags,importance
1,open,Review bundler,2026-09-13,1757280000,work,"review,blocking",high
```

- **category**: single primary bucket (work/personal/house/learning) — used for display/grouping, NOT filtering
- **tags**: comma-separated cross-cutting concerns (oncall, blocking, someday, critical, emergency) — PRIMARY filter mechanism
- **importance**: low/medium/high — impact rating, NOT used for filtering (available for future enhancements)

- Secretary agent writes these fields
- Backward compatible: missing fields = empty string; empty tags = no match (unless `always_show` applies)
- Filter file references match column names

---

### 3. Context Selection Mechanism

**User switches context manually** via:
1. **Command-line flag**: `taskview.py --context work` (loads `filters/work.yaml`)
2. **Environment variable**: `TASKVIEW_CONTEXT=work` (for tmux integration)
3. **Runtime keybinding** (future): press keys in `--watch` mode to cycle contexts

**Initial implementation**: CLI flag + env var only. Keybindings deferred.

**Default behavior**: If `--context` not given and `TASKVIEW_CONTEXT` not set, use `default` context (loads `filters/default.yaml`) or show all tasks if no default file exists.

**Resolution**: `--context NAME` → `<filter_dir>/NAME.yaml` (must exist, else error)

---

### 4. Filter Evaluation Logic

For each open task, evaluate in order:

1. **Global `never_show`** (built-in) — if task has tag `cancelled` or `archived`, exclude (highest priority)
2. **Global `always_show`** (built-in + optional filter file) — if task has tag `critical` or `emergency`, include (bypasses context filter)
3. **Context filter** — if active context's `tags` list has ANY overlap with task's `tags`, include
4. **Result** — included tasks proceed to urgency ranking

**Matching rules**:
- Task's `tags` column: comma-separated string → split → set of tags
- Filter's `tags` list: YAML list → set of tags
- Match = intersection non-empty (OR logic)
- Empty task tags = no match (unless `always_show` applies)
- Empty filter tags = match nothing (shows empty view)

**Global `always_show` tags** (built-in, always active):
- `critical`
- `emergency`

**Global `never_show` tags** (built-in, always active):
- `cancelled` (maps to status=done/cancelled via secretary)
- `archived`

---

### 5. Display Changes

- **Context indicator** in header: `=== Tasks (work) ===`
- **Filtered counts** in Queue section: `23 tasks (8 shown, 15 filtered)`
- **Upcoming section** respects `limits.upcoming` from context config
- **Current task selection** — still picks most recent `open` from *filtered* set
- **Pace/Queue stats** — computed from *filtered* set

---

### 6. Filter File Reloading (Watch Mode)

In `--watch` mode:
- Poll filter file mtime alongside CSV mtime (same 1s interval)
- On filter file change: re-parse, re-apply filter, redraw
- Consistent with CSV watching behavior

---

### 7. Integration Points

- **`taskview/taskview.py`** — add `--context` arg, load filter directory, apply filter before ranking
- **`tmux-xlib.sh`** — pass `--context` via env var or flag (user configures default)
- **Secretary agent** — must write `category`, `tags`, `importance` when creating tasks
- **Filter directory** — user creates/edits `~/.local/share/taskview/filters/*.yaml`

---

## Decisions (Resolved Open Questions)

1. **CSV schema evolution**: Missing fields = empty string; filter rules won't match (except global `always_show`).
2. **Category vs tags**: **Both**. Category = primary bucket (display/grouping). Tags = cross-cutting (filtering).
3. **Importance field**: **Kept in CSV** but NOT used for filtering. Urgency = time (due_ts), Importance = impact.
4. **Time-based default context**: **No**. Manual only (`--context` or `TASKVIEW_CONTEXT`). Default = `default` context file.
5. **Filter file reloading**: **Yes**. Poll mtime in `--watch`, re-parse on change.
6. **Multiple active contexts**: **No**. Single context at a time. One filter file per context.

---

## Status

- [x] Plan approved
- [ ] Spec written (update SPEC.md with filter behavior)
- [ ] CSV schema extended (category, tags, importance columns)
- [ ] Secretary agent updated to write new fields
- [ ] Filter file format finalized
- [ ] Implementation in `taskview.py`
- [ ] `tmux-xlib.sh` integration (env var for context)
- [ ] Test with real tasks

---

## Future Enhancements (Post-MVP)

- Interactive context switching in `--watch` mode (keybindings)
- Context-specific sort orders (e.g., weekend sorts by "enjoyment" not urgency)
- Filter composition: `work + urgent_personal`
- Per-context column visibility (hide Pace on weekend)
- Export filtered view to other formats (JSON for other tools)
- `always_show_tags` / `never_show_tags` definable in a global filter file