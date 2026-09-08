# Task View Context-Aware Filtering

## Goal
Add context-aware filtering to the tmux task view (`taskview/taskview.py`) so the display shows tasks relevant to the user's current situation (workday, evening, weekend, etc.) while preserving the existing urgency ranking.

## Current State
- `taskview/taskview.py` reads `tasks.csv`, folds to current state, ranks by urgency/deadline
- Display sections: Current task, Upcoming, Pace, Queue
- No concept of categories, contexts, or filtering — all open tasks compete equally
- `--watch` mode polls CSV every 1s, redraws on change

## Requirements
1. **External filter file** — filter logic lives in a separate, human-editable file, not hardcoded in `taskview.py`
2. **Manual context switching** — user explicitly chooses context (not automatic by time), though the filter file can define time-based defaults if desired
3. **Flexible matching** — not simple "category X only"; some non-work tasks visible on workdays if they're urgent/important
4. **Complements urgency ranking** — filter narrows/supplements what's shown; existing priority order within the filtered set is preserved
5. **Override mechanism** — tasks marked as "always show" (e.g., urgent phone call) bypass context filter

## Design

### 1. Filter File Format
**Location**: `~/.local/share/taskview/filters.yaml` (YAML for readability, supports comments)

**Structure**:
```yaml
# taskview filters — context-aware task filtering
# Edit this file to define contexts and their rules

# Named contexts the user can switch between
contexts:
  work:
    # Human-readable label for UI
    label: "Work Hours"
    
    # Core filter: which tasks to include
    # All conditions are ANDed; a task must match ALL to be included
    include:
      # Category matching (exact or glob)
      - category: "work"
      - category: "admin"
      
      # Urgency override: always include if due soon regardless of category
      # Evaluated per-task: if due_ts within this window, include it
      - urgent_within: "4h"          # tasks due within 4 hours
      
      # Importance override: always include high-importance tasks
      - importance: "high"           # if task has importance=high (future field)
      
      # Tag-based inclusion
      - tags: ["oncall", "blocking"]
    
    # Explicit exclusions (applied after include)
    exclude:
      - category: "personal"
      - tags: ["someday"]
    
    # Display limits for this context
    limits:
      upcoming: 5        # max upcoming tasks to show
      queue_breakdown: true
  
  evening:
    label: "Evening"
    include:
      - category: "personal"
      - category: "learning"
      - urgent_within: "2h"
      - importance: "high"
    exclude:
      - category: "work"
    limits:
      upcoming: 7
  
  weekend:
    label: "Weekend"
    include:
      - category: "personal"
      - category: "house"
      - category: "learning"
      - urgent_within: "24h"
    exclude: []
    limits:
      upcoming: 10
  
  all:
    label: "All Tasks"
    include: []          # empty = no filtering
    exclude: []
    limits:
      upcoming: 15

# Default context if none selected (optional)
default_context: "work"

# Global fallback rules (always applied regardless of context)
global:
  # Tasks matching these are ALWAYS shown (unless done/cancelled)
  always_show:
    - urgent_within: "1h"
    - tags: ["critical", "emergency"]
  
  # Tasks matching these are NEVER shown
  never_show:
    - status: "cancelled"
    - tags: ["archived"]
```

**Notes on format**:
- YAML chosen over JSON/TOML for: comments, readability, native list/dict support
- `category` field doesn't exist in current CSV — this plan assumes a future `category` column or tag system (see Open Questions)
- `urgent_within` accepts human durations: `30m`, `4h`, `2d`, `1w`
- `importance` and `tags` are future CSV fields; filter file defines the schema taskview will expect

---

### 2. Task Data Model Extensions
The filter requires metadata not in the current CSV. Two approaches:

**Option A: Extend CSV schema** (recommended for simplicity)
```
id,status,title,due_ts,chg_ts,category,tags,importance
1,open,Review bundler,2026-09-13,1757280000,work,"review,blocking",high
```
- Secretary agent writes these fields
- Backward compatible: missing fields = empty string
- Filter file references match column names

**Option B: Sidecar metadata file**
- Separate `tasks.meta.yaml` mapping `id` → `{category, tags, importance}`
- More flexible, doesn't touch CSV
- Adds complexity (two files to keep in sync)

**Decision**: Option A. Simpler, single source of truth, CSV is append-only so new columns just appear in new rows.

---

### 3. Context Selection Mechanism
**User switches context manually** via:
1. **Command-line flag**: `taskview.py --context work`
2. **Runtime keybinding** (future): press `w`/`e`/`k`/`a` in `--watch` mode to cycle contexts
3. **Environment variable**: `TASKVIEW_CONTEXT=work` (for tmux integration)

**Initial implementation**: CLI flag only (`--context`). Keybindings deferred to interactive enhancement.

**Default behavior**: If `--context` not given, use `default_context` from filter file, or `all` if undefined.

---

### 4. Filter Evaluation Logic
For each open task, evaluate in order:

1. **Global `never_show`** — if matches, exclude (highest priority)
2. **Global `always_show`** — if matches, include (bypasses context filter)
3. **Context `exclude`** — if matches, exclude
4. **Context `include`** — if empty, include all (subject to above); if non-empty, task must match AT LEAST ONE include rule
5. **Result** — included tasks proceed to urgency ranking

**Matching rules**:
- `category: "work"` — exact match on `category` column
- `category: "work*"` — glob match (fnmatch)
- `tags: ["oncall"]` — task's `tags` column (comma-separated) contains ANY listed tag
- `urgent_within: "4h"` — task has `due_ts` and `due_ts - now() <= 4h`
- `importance: "high"` — exact match on `importance` column

**Multiple include rules** = OR logic (task matches if ANY rule matches).
**Multiple exclude rules** = OR logic (task excluded if ANY rule matches).

---

### 5. Display Changes
- **Context indicator** in header: `=== Tasks (work) ===`
- **Filtered counts** in Queue section: `23 tasks (8 shown, 15 filtered)`
- **Upcoming section** respects `limits.upcoming` from context config
- **Current task selection** — still picks most recent `open` from *filtered* set
- **Pace/Queue stats** — computed from *filtered* set (option: show global stats too)

---

### 6. Integration Points
- **`taskview/taskview.py`** — add `--context` arg, load filter file, apply filter before ranking
- **`tmux-xlib.sh`** — optional: pass `--context` based on time of day (user can override)
- **Secretary agent** — must write `category`, `tags`, `importance` when creating tasks
- **Filter file** — user creates/edits `~/.local/share/taskview/filters.yaml`

---

## Open Questions

1. **CSV schema evolution**: How to handle existing tasks without `category`/`tags`? 
   - *Proposal*: Treat missing as empty string; filter rules simply won't match them (unless `urgent_within` applies).

2. **Category vs tags**: Should we use one or both?
   - *Proposal*: Both. Category = single primary bucket (work/personal/house/learning). Tags = cross-cutting concerns (oncall, blocking, someday).

3. **Importance field**: Is `importance` (low/medium/high) distinct from urgency (due date)?
   - *Proposal*: Yes. Urgency = time pressure. Importance = impact. Both useful for filtering.

4. **Time-based default context**: Should `tmux-xlib.sh` auto-select context by time?
   - *Proposal*: Yes, as a convenience. User can override with `--context`. Example:
     ```bash
     hour=$(date +%H)
     if [ $hour -ge 9 -a $hour -lt 16 ]; then ctx=work
     elif [ $hour -ge 16 -a $hour -lt 22 ]; then ctx=evening
     else ctx=weekend; fi
     ```

5. **Filter file reloading**: In `--watch` mode, should filter file changes trigger redraw?
   - *Proposal*: Yes, same as CSV — poll filter file mtime, re-parse on change.

6. **Multiple active contexts**: Allow `--context work,evening` (union)?
   - *Proposal*: Not in MVP. Single context keeps mental model simple. Can add later.

---

## Status
- [ ] Plan approved
- [ ] Spec written (update SPEC.md with filter behavior)
- [ ] CSV schema extended (category, tags, importance columns)
- [ ] Secretary agent updated to write new fields
- [ ] Filter file format finalized
- [ ] Implementation in `taskview.py`
- [ ] `tmux-xlib.sh` integration (optional auto-context)
- [ ] Test with real tasks

---

## Future Enhancements (Post-MVP)
- Interactive context switching in `--watch` mode (keybindings)
- Context-specific sort orders (e.g., weekend sorts by "enjoyment" not urgency)
- Filter composition: `work + urgent_personal`
- Per-context column visibility (hide Pace on weekend)
- Export filtered view to other formats (JSON for other tools)