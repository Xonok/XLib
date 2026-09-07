# taskview — Task List Display for tmux

## Purpose
Read-only terminal display showing personal tasks in a condensed format for a tmux pane.
Replaces the unused shell pane in `tmux-xlib.sh`.

## Data Model

**File**: `~/.local/share/taskview/tasks.csv` (append-only CSV, git-ignored)

```csv
// tasks.csv — append-only, last-write-wins by id
id,status,title,due_ts,chg_ts
1,open,Review bundler end-to-end,2026-09-13,1757280000
2,open,Move GitHub folder to second drive,2026-09-13,1757280500
1,done,...,2026-09-13,1757290000
```

- `id`: integer, assigned by secretary (via separate counter file `tasks.id`)
- `status`: `open` | `done` | `cancelled` (reopen = new `open` row)
- `title`: task description
- `due_ts`: Unix epoch seconds (deadline), or empty
- `chg_ts`: Unix epoch seconds (when this record was written) — always present

**Counter file**: `~/.local/share/taskview/tasks.id` — single integer, next available id.

**Writer**: Secretary agent (Agents workspace) claims `tasks.csv` and `tasks.id` via `agent-coord.py`, appends via `xcsv.write_entry`, increments counter.

**Reader**: `taskview.py` reads entire CSV, folds to current state (last row per id wins), computes metrics, renders.

## Display Layout

Narrow tmux pane, top to bottom:

```
=== Tasks ===

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
 23 tasks remaining (6 this week, 10 this month, 7 later)
```

- **Current task**: Most recent `open` task with `status != done`, given most vertical space.
- **Upcoming**: Next few `open` tasks, one line each.
- **Pace**:
  - Day: calendar day (midnight → now)
  - Week: rolling 7 days
  - Month: rolling 30 days
  - Counts: `done` tasks by `chg_ts`, `active` = `open` tasks
- **Queue**: Total `open` tasks, broken down by due date horizon (week/month/later)

Categories are not displayed (future enhancement).

## Program Behavior

**Modes**:
- `python3 taskview/taskview.py` — render once, exit
- `python3 taskview/taskview.py --watch` — poll file (1s), redraw on change

**Refresh**: Watch mode polls file size/mtime; on change, re-read, re-fold, re-render.
Uses ANSI clear-screen (`\033[2J\033[H`) like `skynet.py`.

**No API calls** — read-only local file monitor (follows project rule: monitoring scripts don't add AI usage).

## Implementation Notes

- **Reading CSV**: Use Python's `csv` module (handles quoting) or simple manual parse (xcsv format is standard CSV with `//` comment lines skipped). xcsv `readline`/`readall` not required for MVP — noted for planner as future simplification.
- **Folding**: `state[id] = row` in file order; skip comment lines (`//`); ignore rows with missing `id`.
- **Current task selection**: Most recent `open` by `chg_ts` (or first `open` if no `chg_ts` ordering). Fallback: first `open`.
- **Time parsing**: `due_ts` and `chg_ts` are Unix seconds (int). Display formats as relative ("2d", "Sep 13") or absolute.
- **Dependencies**: None beyond stdlib. xcsv used by secretary only (writer).
- **No release** — stays in `taskview/` dev folder. Not versioned.

## Integration

**tmux-xlib.sh** change: replace shell pane command with:
```bash
tmux split-window -h
tmux send-keys -t "$SESSION" "cd $XLIB_DIR ; python3 taskview/taskview.py --watch" Enter
```

**Secretary agent** (future): Skill/tool that:
1. Claims `tasks.csv` and `tasks.id`
2. Reads counter, increments, writes back
3. `xcsv.write_entry(csv_path, schema, id=..., status="open", title=..., due_ts=..., chg_ts=now())`
4. Releases claims

## Future Enhancements (not in MVP)

- Category display / filtering
- Interactive keybindings (j/k scroll, Enter expand, d done)
- Reschema support in CSV (schema evolution)
- xcsv `readline`/`readall` / key-value / reschema (planner tracked)
- Persistent data dir via XDG (`~/.local/share/taskview/`)