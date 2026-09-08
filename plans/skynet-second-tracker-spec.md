# Skynet Second Tracker — Technical Specification

## Overview
Add a second monitoring pane to the XLib tmux session showing live agent sessions with workspace-scoped names and inferred statuses. Implemented as a second mode in the existing `skynet.py` script.

---

## Data Source

### Database
- **Path**: `~/.local/share/opencode/opencode.db` (read-only, URI mode)
- **Table**: `message`
- **Relevant columns**:
  - `session_id` — unique per opencode session
  - `data` — JSON blob containing: `modelID`, `role`, `time.created`, `tokens.*`, `finish`, `error`, tool calls
  - `time_created` — milliseconds since epoch

### Session Identification
Each opencode session corresponds to one agent instance. The session's agent identity is derived from:
1. **Workspace tag** — directory name of the workspace root (e.g., `XLib`, `Agents`)
2. **Role + instance number** — allocated by `agent-coord.py` (e.g., `planner-1`, `programmer-2`)

**Mapping strategy**: The agent-coord system writes instance notes to `.agents/agent-notes-{role}-{num}.md` in the workspace root. We can infer the agent identity for a session by:
- Finding which workspace the session's cwd belongs to (via `session_id` → cwd mapping, or heuristic from first message's working directory)
- Reading the agent ID from the instance notes file that was active at session start

**Simpler fallback**: If cwd mapping isn't reliably available in the DB, use the session's first message timestamp to find which agent-coord ID was allocated at that time (by checking `ids.json` allocation order vs session start time).

**Pragmatic approach for v1**: Use the opencode session's `cwd` if available in message data, else fall back to workspace tag from the DB path context. The agent-coord `ids.json` maps `session_key` (pid-based or explicit) → qualified agent ID. We can match by pid if the opencode process pid is recorded, or by time correlation.

### Required Query
```sql
SELECT session_id,
       json_extract(data, '$.role') as role,
       json_extract(data, '$.modelID') as model,
       json_extract(data, '$.time.created') as msg_time,
       json_extract(data, '$.tokens.input') as tok_in,
       json_extract(data, '$.tokens.output') as tok_out,
       json_extract(data, '$.tokens.total') as tok_total,
       json_extract(data, '$.finish') as finish,
       json_extract(data, '$.error.name') as error_name,
       json_extract(data, '$.error.data.statusCode') as error_status,
       json_extract(data, '$.toolCalls') as tool_calls,
       json_extract(data, '$.content') as content,
       time_created
FROM message
WHERE json_extract(data, '$.role') = 'assistant'
  AND time_created >= ?
ORDER BY session_id, time_created
```

---

## Agent Identity Resolution

### Primary Method: cwd → workspace tag → agent-coord IDs
1. Extract `cwd` from first user message in session (or session metadata if available)
2. Find workspace root containing that cwd (nearest ancestor with `.agents/`)
3. Workspace tag = basename of workspace root
4. Load `.agents/ids.json` from that workspace
5. Find entry where `session_key` matches this session's opencode pid (if recorded) or correlates by time

### Fallback: Time-correlation with ids.json
- `ids.json` entries with `pid-{pid}` keys are created when agent starts
- Session's first message time ≈ agent start time
- Match by closest timestamp

### Fallback 2: Anonymous sessions
If identity cannot be resolved, display as `Unknown/{session_id[:8]}` with status only.

---

## Status Inference Algorithm

### Inputs per session (aggregated from recent messages, last 30 min window)
- `last_msg_time` — timestamp of most recent assistant message
- `last_msg_content` — text content of last message
- `last_msg_tool_calls` — array of tool calls in last message (or empty)
- `last_msg_finish` — finish reason: `stop`, `tool-calls`, `length`, `unknown`
- `msg_count_5min` — messages in last 5 minutes
- `tool_call_count_5min` — tool calls in last 5 minutes
- `has_recent_question` — last message ends with `?` and no tool calls, length < 500 chars

### Status Rules (evaluated in order)
1. **`delegating`** — Last message contains a subagent dispatch (tool call to `task` with `subagent_type` set)
2. **`question`** — `has_recent_question` is true
3. **`working`** — `tool_call_count_5min > 0` OR `msg_count_5min > 2` (active back-and-forth)
4. **`idle`** — None of the above (no activity in ~5 min)

### Time Display
- `now` — < 1 minute ago
- `{N}m` — minutes ago (1-59)
- `{H}h{M:02d}m` — hours ago (1-23h)
- `{D}d{H}h` — days ago

---

## Display Format

### Layout (narrow pane, ~40-50 columns)
```
=== Agents (Live) ===

XLib/a1 (XLib)
  planner      working  2m ago
  reviewer     question 30s ago

XLib/a2 (XLib)
  programmer   idle     15m ago

Agents/a1 (Agents)
  secretary    working  1m ago
  mechanic     idle     10m ago
```

### Formatting Rules
- **Header**: `=== Agents (Live) ===`
- **Workspace group**: `{workspace_tag}/{instance_tag} ({workspace_tag})` — blank line before each group
- **Agent line**: `  {role}-{num}  {status}  {age}`
  - Role truncated to 12 chars, left-aligned
  - Status: `working`, `idle`, `question`, `delegating` (10 chars, left-aligned)
  - Age: right-aligned in remaining space
- **Sorting**: Workspace tag alphabetical, then role alphabetical, then instance number
- **Empty state**: `no active agents` if no sessions in window

### Column Widths (for 40-col pane)
- Role: 12 chars
- Status: 10 chars
- Age: remaining (~18 chars)

---

## Integration Architecture

### Option A: Single Script, Two Modes (Selected)
`skynet.py` gains a `--mode` argument:
- `--mode=usage` — current behavior (per-model token/refusal stats)
- `--mode=agents` — new behavior (per-agent status display)

Shared infrastructure:
- Single DB connection pool
- Single poll loop (1 second)
- Shared `db_stamp()` change detection
- Shared `--watch` and `--window-hours` args

### Command Line Interface
```bash
# Usage tracker (existing)
python3 tools/skynet.py --watch --window-hours 168 --mode=usage

# Agent tracker (new)
python3 tools/skynet.py --watch --window-hours 0.5 --mode=agents
```
- Default window for agents: 30 minutes (0.5 hours)
- Default window for usage: 168 hours (7 days)

### tmux-xlib.sh Changes
```bash
# Current: 3 panes tiled
# New: 4 panes — left (xlint), middle (taskview), right-top (skynet usage), right-bottom (skynet agents)

tmux new-session -d -s "$SESSION"
tmux send-keys -t "$SESSION" "cd $XLIB_DIR ; python3 xlint/xlint.py --watch ." Enter

tmux split-window -h
tmux send-keys -t "$SESSION" "cd $XLIB_DIR ; python3 taskview/taskview.py --watch" Enter

tmux split-window -h
tmux send-keys -t "$SESSION" "cd $XLIB_DIR ; python3 tools/skynet.py --watch --mode=usage" Enter

tmux split-window -v    # Vertical split on right pane
tmux send-keys -t "$SESSION" "cd $XLIB_DIR ; python3 tools/skynet.py --watch --mode=agents --window-hours 0.5" Enter

tmux select-layout tiled
```

---

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `--mode` | `usage` | `usage` or `agents` |
| `--window-hours` | 168 (usage), 0.5 (agents) | Lookback window |
| `--idle-threshold-min` | 5 | Minutes of inactivity before `idle` |
| `--live-window-min` | 30 | Minutes for "live" session inclusion |
| `--poll-seconds` | 1.0 | Poll interval |

---

## Edge Cases & Handling

| Case | Handling |
|------|----------|
| No DB file | Print `opencode db not found`, exit 1 |
| DB locked (WAL) | URI `mode=ro` handles this |
| No sessions in window | Print `no active agents` |
| Agent identity unresolved | Show as `Unknown/{sid[:8]}` |
| Session spans workspace boundary | Use cwd at session start |
| Multiple workspaces in one DB | Group by resolved workspace tag |
| Very long role names | Truncate to 12 chars with `…` |
| Pane narrower than 35 cols | Compact mode: drop workspace group header, show `ws/role status age` |

---

## Implementation Plan

### Phase 1: Core Logic
1. Add `--mode` argument parser
2. Implement `load_agent_sessions(window_hours)` — returns sessions with messages
3. Implement `resolve_agent_identity(session_id, first_msg_cwd, first_msg_time)` → qualified ID
4. Implement `infer_status(session_messages, now)` → status enum
5. Implement `render_agents(sessions, now)` → formatted string

### Phase 2: Integration
6. Wire into `watch()` loop with mode switch
7. Add `--idle-threshold-min`, `--live-window-min` args
8. Update `tmux-xlib.sh` with 4-pane layout

### Phase 3: Polish
9. Compact mode for narrow panes
10. Key binding to toggle hidden columns in usage mode (per plan)
11. Test with multiple concurrent agents

---

## Testing Scenarios

1. **Single agent, idle** → shows `idle` with increasing age
2. **Agent asking question** → shows `question` briefly
3. **Agent using tools** → shows `working`
4. **Agent dispatching subagent** → shows `delegating`
5. **Two workspaces (XLib + Agents)** → grouped correctly
6. **Unresolved identity** → shows `Unknown/abc12345`
7. **DB missing** → clean error message
8. **Rapid mode switch** → no DB connection leaks

---

## Dependencies
- Python stdlib only (`sqlite3`, `json`, `argparse`, `time`, `datetime`, `os`, `pathlib`)
- `inotify` optional (not needed — uses poll loop like current skynet)
- `agent-coord.py` for identity resolution (reads `.agents/ids.json`)

---

## Future Enhancements (Post-v1)
- Clickable/interactive: press key to focus tmux pane for that agent
- Filter by workspace: `--workspace=XLib`
- Show current task (from agent's instance notes)
- Color coding for statuses
- Historical status timeline