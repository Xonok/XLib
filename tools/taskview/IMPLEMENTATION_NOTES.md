<!-- spec-origin: ai -->
> **AI-written spec.** Authored by an AI agent, not by the human.

> **SUPERSEDED 2026-09-27 — do not implement from this file.** It describes the
> old model, where a context was a tag list in a fixed per-user filter directory
> and tags doubled as project membership. The current design makes `category` the
> membership axis, puts the filter in the project folder, and discovers it from
> the working directory. See `SPEC.md` in this directory, which is the contract.
> Kept only as a record of how the filter feature was first built.

# taskview Filter Implementation Notes

## For the Programmer

This document summarizes what needs to be implemented in `taskview/taskview.py` based on the updated SPEC.md and plan.

---

## Required Changes to `taskview.py`

### 1. Add `--context` CLI Argument
```python
parser.add_argument("--context", default=None, help="Context name (loads filters/<name>.yaml)")
```
- Also read `TASKVIEW_CONTEXT` env var as fallback
- Default: `"default"` (loads `filters/default.yaml`)
- Error if filter file doesn't exist

### 2. Filter File Loading
- Filter directory: `~/.local/share/taskview/filters/`
- Load YAML file: `<filter_dir>/<context>.yaml`
- Parse structure:
	```yaml
	label: "Work Hours"
	tags: ["work", "admin", "oncall", "blocking"]
	limits:
		upcoming: 5
		queue_breakdown: true
	```
- Cache parsed filter; re-parse on mtime change in `--watch` mode

### 3. CSV Schema Update (Reading)
- New columns: `category`, `tags`, `importance` (positions 5, 6, 7)
- Backward compatible: missing columns = empty string
- Tag parsing: split `tags` column by comma, strip, filter empty → `set[str]`

### 4. Filter Evaluation Logic
For each open task (after folding), apply in order:
```python
def passes_filter(task_tags: set[str], filter_tags: list[str]) -> bool:
		# 1. never_show (built-in)
		if task_tags & {"cancelled", "archived"}:
				return False
		# 2. always_show (built-in)
		if task_tags & {"critical", "emergency"}:
				return True
		# 3. context filter (OR logic)
		if filter_tags and not (task_tags & set(filter_tags)):
				return False
		return True
```

### 5. Display Updates
- Header: `=== Tasks ({filter.label}) ===`
- Queue line: `{total} tasks remaining ({shown} shown, {filtered} filtered)`
- Upcoming: respect `limits.upcoming`
- Current task: most recent `open` from *filtered* set
- Pace/Queue stats: computed from *filtered* set

### 6. Watch Mode Enhancement
- Track mtime of both `tasks.csv` AND active filter file
- On either change: re-read CSV, re-parse filter, re-filter, re-render

---

## Files to Create (User Responsibility)

User must create filter directory and files:
```
~/.local/share/taskview/filters/
├── default.yaml      # required for default context
├── work.yaml
├── evening.yaml
├── weekend.yaml
└── ...               # any custom contexts
```

Example files provided in taskview/ as `*.yaml.example`.

---

## Secretary Agent Updates (Separate Workspace)

Secretary agent (in Agents workspace) must be updated to write new CSV columns:
- `category` — single value from allowed set
- `tags` — comma-separated list
- `importance` — low/medium/high

Uses `xcsv.write_entry` with updated schema.

---

## Integration: `tmux-xlib.sh`

`tools/tmux-xlib.sh` opens the panel against a target repository, and the
taskview pane runs in that repository rather than in XLib — the cwd is what
picks the filter, because discovery walks up from the working directory. No
flag, no `--context`:

```bash
tmux split-window -d -P -F '#{pane_id}' -c "$TARGET" -t "$SESSION:0.0"
tmux send-keys -t "$PANE" "python3 $(q "$TASKVIEW") --watch" Enter
```

With no filter in the repository, or anywhere above it, the pane still comes
up: it shows everything and says `no filter found` in its header.

---

## Dependencies

- `PyYAML` for filter file parsing (`pip install pyyaml` or `apt install python3-yaml`)
- No other new dependencies

---

## Testing Checklist

- [ ] `--context work` loads `filters/work.yaml` and filters correctly
- [ ] Missing filter file → clear error message
- [ ] Tag matching: OR logic (any tag matches → show)
- [ ] Global `always_show`: critical/emergency always shown
- [ ] Global `never_show`: cancelled/archived never shown
- [ ] Empty tags on task → no match (unless always_show)
- [ ] `--watch` re-parses filter file on change
- [ ] Display shows context label, filtered counts
- [ ] Backward compatible: old CSV rows (no category/tags/importance) work
- [ ] Default context (`default.yaml`) works when no --context given

---

## Example Filter Files

See `taskview/*.yaml.example` for template files:
- `work.yaml.example`
- `evening.yaml.example`
- `weekend.yaml.example`
- `default.yaml.example`

Copy to `~/.local/share/taskview/filters/` and customize.

---

## Example CSV

See `taskview/tasks.csv.example` for schema with new columns.
