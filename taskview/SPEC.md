# taskview — Task List Display for tmux

## Purpose
Read-only terminal display showing personal tasks in a condensed format for a tmux pane.
Replaces the unused shell pane in `tmux-xlib.sh`.

## Data Model

**File**: `~/.local/share/taskview/tasks.csv` (append-only CSV, git-ignored)

```csv
// tasks.csv — append-only, last-write-wins by id
id,status,title,due_ts,chg_ts,category,tags,importance
1,open,Review bundler end-to-end,2026-09-13,1757280000,work,"review,blocking",high
2,open,Move GitHub folder to second drive,2026-09-13,1757280500,admin,"migration",medium
1,done,...,2026-09-13,1757290000,work,"review,blocking",high
```

- `id`: integer, assigned by secretary (via separate counter file `tasks.id`)
- `status`: `open` | `done` | `cancelled` (reopen = new `open` row)
- `title`: task description
- `due_ts`: Unix epoch seconds (deadline), or empty
- `chg_ts`: Unix epoch seconds (when this record was written) — always present
- `category`: single primary bucket (work/personal/house/learning/admin) — for display/grouping
- `tags`: comma-separated cross-cutting concerns (oncall, blocking, someday, critical, emergency, migration) — PRIMARY filter mechanism
- `importance`: low | medium | high — impact rating (not used for filtering)

**Counter file**: `~/.local/share/taskview/tasks.id` — single integer, next available id.

**Writer**: Secretary agent (Agents workspace) claims `tasks.csv` and `tasks.id` via `agent-coord.py`, appends via `xcsv.write_entry`, increments counter.

**Reader**: `taskview.py` reads entire CSV, folds to current state (last row per id wins), applies context filter, computes metrics, renders.

### Filter Files

**Directory**: `~/.local/share/taskview/filters/` (one YAML file per context)

**File naming**: `<context-name>.yaml` (e.g., `work.yaml`, `evening.yaml`, `weekend.yaml`, `default.yaml`)

**Structure** (per file):
```yaml
# taskview filter — work context
label: "Work Hours"
tags: ["work", "admin", "oncall", "blocking"]
limits:
  upcoming: 5
  queue_breakdown: true
```

- `label`: human-readable name for UI header
- `tags`: list of tags; task matches if it has ANY of these tags (OR logic)
- `limits.upcoming`: max upcoming tasks to show (default: 5)
- `limits.queue_breakdown`: show queue breakdown by horizon (default: true)

**Context resolution**: `--context NAME` loads `filters/NAME.yaml`. Missing file = error.

**Built-in global tags** (always active, no config needed):
- `always_show`: `critical`, `emergency` — bypass context filter
- `never_show`: `cancelled`, `archived` — always excluded

## Display Layout

Narrow tmux pane, top to bottom:

```
=== Tasks (work) ===

▸ XLib: Review bundler end-to-end
  In progress since yesterday. Next: agree review process with a2.

 UPCOMING
 · Move GitHub folder to second drive          (by Sep 13)
 · Data loss prevention                         (by Sep 20)
 · MaFE public web page                         (this week)

 PACE (rolling)
 Day: 3 done, 1 active
 Week: 7 done, 2 active
 Month: 12 done, 5 active

 QUEUE
 23 tasks remaining (8 shown, 15 filtered)
```

- **Header**: `=== Tasks (context-name) ===` — shows active context label
- **Current task**: Most recent `open` task from *filtered* set, by `chg_ts`
- **Upcoming**: Next few `open` tasks from *filtered* set, one line each (respects `limits.upcoming`)
- **Pace**: Rolling counts from *filtered* set
  - Day: calendar day (midnight → now)
  - Week: rolling 7 days
  - Month: rolling 30 days
  - Counts: `done` tasks by `chg_ts`, `active` = `open` tasks
- **Queue**: Total `open` tasks from *filtered* set, broken down by due date horizon (week/month/later)
- **Filtered indicator**: `(X shown, Y filtered)` in Queue line

## Program Behavior

**Modes**:
- `python3 taskview/taskview.py` — render once, exit
- `python3 taskview/taskview.py --watch` — watch for changes, redraw on change
- `python3 taskview/taskview.py --context NAME` — use context `NAME` (loads `filters/NAME.yaml`)
- `python3 taskview/taskview.py --context NAME --watch` — watch with context

**Filter Evaluation** (per open task, in order):
1. If task has tag `cancelled` or `archived` → exclude (never_show)
2. If task has tag `critical` or `emergency` → include (always_show, bypasses context)
3. If active context filter's `tags` list overlaps task's `tags` → include
4. Otherwise → exclude

**Refresh**: Watch mode uses **inotify as primary** (Linux, efficient), **poll fallback** (1s interval, portable). On CSV or filter file change, re-read, re-fold, re-filter, re-render.
Uses ANSI clear-screen (`\033[2J\033[H`) like `skynet.py`.

**Periodic time refresh** (planned): `--refresh-interval SECONDS` (default 600) triggers redraw even without file changes to update relative timestamps ("2h ago" → "3h ago"). See `plans/taskview-time-refresh.md`.

**No API calls** — read-only local file monitor (follows project rule: monitoring scripts don't add AI usage).

## Implementation Notes

- **Reading CSV**: Use Python's `csv` module (handles quoting) or simple manual parse (xcsv format is standard CSV with `//` comment lines skipped). xcsv `readline`/`readall` not required for MVP.
- **Folding**: `state[id] = row` in file order; skip comment lines (`//`); ignore rows with missing `id`.
- **Tag parsing**: `tags` column split by comma, stripped, empty strings filtered → `set[str]`. Missing/empty column = empty set.
- **Current task selection**: Most recent `open` by `chg_ts` from filtered set. Fallback: first `open` from filtered set.
- **Time parsing**: `due_ts` and `chg_ts` are Unix seconds (int). Display formats as relative ("2d", "Sep 13") or absolute.
- **Dependencies**: None beyond stdlib. `inotify` optional (Linux) — if unavailable, falls back to 1s polling. `yaml` (PyYAML) for filter files. xcsv used by secretary only (writer).
- **No release** — stays in `taskview/` dev folder. Not versioned.

## Integration

**tmux-xlib.sh** change: replace shell pane command with:
```bash
tmux split-window -h
tmux send-keys -t "$SESSION" "cd $XLIB_DIR ; python3 taskview/taskview.py --watch --context ${TASKVIEW_CONTEXT:-default}" Enter
```

**Secretary agent** (future): Skill/tool that:
1. Claims `tasks.csv` and `tasks.id`
2. Reads counter, increments, writes back
3. `xcsv.write_entry(csv_path, schema, id=..., status="open", title=..., due_ts=..., chg_ts=now(), category=..., tags=..., importance=...)`
4. Releases claims

**Filter directory**: User creates/edits `~/.local/share/taskview/filters/*.yaml`

## Future Enhancements (not in MVP)

- Category display / grouping in UI
- Interactive keybindings (j/k scroll, Enter expand, d done)
- Reschema support in CSV (schema evolution)
- xcsv `readline`/`readall` / key-value / reschema (planner tracked)
- Persistent data dir via XDG (`~/.local/share/taskview/`)
- Context-specific sort orders (e.g., weekend sorts by "enjoyment" not urgency)
- Filter composition: `work + urgent_personal`
- Per-context column visibility (hide Pace on weekend)
- Export filtered view to other formats (JSON for other tools)
- Global `always_show_tags` / `never_show_tags` definable in a global filter file