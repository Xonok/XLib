# Task View Time-Based Updates

## Goal
Add periodic time-based refresh to the tmux task view (`taskview/taskview.py`) so relative timestamps (e.g., "7h ago", "2d ago") update even when the CSV hasn't changed.

## Current State
- `taskview/taskview.py` runs with `--watch` mode polling CSV every 1s
- Only redraws when file mtime/size changes (via inotify or poll)
- Relative time display (`fmt_time`, `fmt_due`) shows stale "X hours ago" until file changes

## Requirements
- **Periodic redraw**: Update display every 10 minutes (configurable) even if file unchanged
- **Relative time recalculation**: Recompute `fmt_time`/`fmt_due` on timer
- **Efficient**: Don't re-read/re-parse CSV on time-only updates, just recalculate time strings and redraw
- **Configurable interval**: Default 10 minutes (600s), adjustable via `--refresh-interval`

## Design
1. Add `--refresh-interval SECONDS` argument (default 600 = 10 min)
2. In `--watch` mode:
   - Track last full parse time
   - On each poll (1s), check if refresh interval elapsed
   - If yes: re-run `build_view` with fresh `datetime.now()` (no CSV re-read), redraw
   - If no: only redraw if file changed
3. `fmt_time` and `fmt_due` already use `datetime.now()` — just need to call `build_view` again

## Integration Points
- Modify `taskview/taskview.py` only
- No changes to `tmux-xlib.sh` needed
- CSV format unchanged

## Status
- [ ] Plan approved
- [ ] Spec written
- [ ] Implementation
- [ ] Test