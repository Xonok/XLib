# Marduk — Real-Time Agent Status Monitor

## Overview
Marduk is a monitoring tool that displays live status of OpenCode agent instances by connecting to their SSE event streams. Agents are launched via `tools/oc-agent`, a general-purpose role-aware launcher that writes port metadata files to a shared directory. Marduk watches this directory, connects to each agent's SSE endpoint, and renders a real-time status view.

**Name**: Marduk — Mesopotamian god with four eyes and four ears, "who sees in all directions at once."

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  tools/oc-agent (role-aware launcher)                           │
│    ├─ validates: agent name                                     │
│    ├─ exports: OPENCODE_AGENT_ROLE=<agent-name>                 │
│    ├─ spawns: opencode --agent <agent-name> --port 0 --log-level WARN │
│    ├─ discovers: listening port via ss                          │
│    └─ writes: ~/.opencode/ports/<port>.json                     │
│         { "port": 4123, "role": "researcher",                  │
│           "session_id": "abc123", "pid": 12345,                │
│           "started_at": 1725800000 }                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Marduk (monitor)                                               │
│    ├─ startup: reads all *.json in ~/.opencode/ports/          │
│    ├─ watch: inotify (or poll fallback) on ~/.opencode/ports/  │
│    ├─ on new file: parse JSON, connect SSE to /event           │
│    ├─ maintains: { session_id: { role, status, current_tool,  │
│           last_event_ts, port, pid } }                         │
│    ├─ cleanup: removes stale port files (PID dead, SSE dead)   │
│    └─ renders: live status display (narrow pane, like skynet)  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Port File Specification

### Location
`~/.opencode/ports/` (created by `tools/oc-agent` on first use)

### Filename
`<port>.json` — port number is unique, so no collisions. Later agent overwrites if port reused (OS won't reuse immediately).

### Content (JSON)
```json
{
  "port": 4123,
  "role": "researcher",
  "session_id": "abc123def",
  "pid": 12345,
  "started_at": 1725800000.123
}
```
- `port`: integer, the HTTP/SSE port
- `role`: string, agent role (`planner`, `programmer`, `reviewer`, `secretary`, `mechanic`, `researcher`, or custom)
- `session_id`: string, OpenCode session ID (from opencode)
- `pid`: integer, opencode process PID (for staleness detection)
- `started_at`: float, Unix timestamp (seconds.millis)

---

## Staleness Detection & Cleanup

Marduk removes port files **only** on definitive signals:

| Check | Method | Action |
|-------|--------|--------|
| **PID dead** | `os.kill(pid, 0)` raises `ProcessLookupError` | Delete port file immediately |
| **TCP connect fails** | `socket.connect(('127.0.0.1', port))` fails (connection refused, timeout) | Delete port file immediately |

**NOT cleanup triggers** (informational only, shown in UI):
| Check | Why Unreliable |
|-------|----------------|
| **SSE silent > N seconds** | Idle agents produce no events; 60s+ silence is normal |
| **Port file age > 24h** | Long-running sessions (research, background tasks) are valid |

**Display hint**: If SSE silent > 60s OR file age > 24h, show a `⚠` marker in status column (e.g., `idle⚠`), but **do not remove** the port file.

**Race condition**: If agent restarts and writes new file for same port, Marduk sees new file (inotify `CREATE` or `MODIFY`), re-reads, reconnects.

---

## SSE Event Handling

### Connection
- URL: `http://127.0.0.1:<port>/event`
- Standard `EventSource` / SSE client (Python: `requests` with `stream=True` or `httpx`)
- Reconnect on disconnect with exponential backoff (1s, 2s, 4s, max 30s)

### Events of Interest
| Event | Updates |
|-------|---------|
| `session.status` | `status = data.type` (`idle`, `busy`, `retry`) |
| `session.next.step.started` | `status = "working"`, `current_tool = null` |
| `session.next.text.started` | `status = "working"` |
| `session.next.reasoning.started` | `status = "working"` |
| `session.next.tool.called` | `current_tool = data.tool.name`; if `tool == "task"` → `status = "delegating"` |
| `question.asked` | `status = "question"` |
| `permission.asked` | `status = "question"` (waiting for user) |
| `session.next.agent.switched` | `status = "delegating"` (subagent context switch) |

### Status Inference (Marduk's Display State)
| Display Status | Source |
|----------------|--------|
| `idle` | `session.status` = `idle` |
| `working` | `session.status` = `busy` + step/text/reasoning started |
| `delegating` | `tool.called` with `task` OR `agent.switched` |
| `question` | `question.asked` OR `permission.asked` |
| `retry` | `session.status` = `retry` (rate limited) |
| `disconnected` | SSE closed, reconnecting... |

---

## Display Format

### Layout (narrow pane, ~40-50 columns)
```
=== Marduk (Live) ===

XLib
  planner      working     step:read  2s ago
  reviewer     question    ?          5s ago
  programmer   delegating  task       1s ago

Agents
  secretary    idle⚠                  3m ago
  mechanic     working     step:write 10s ago
```

### Formatting Rules
- **Header**: `=== Marduk (Live) ===`
- **Workspace group**: Workspace name (from agent's cwd or role notes) — blank line before each group
- **Agent line**: `  {role}  {status}  {detail}  {age}`
  - Role: 12 chars, left-aligned
  - Status: 10 chars, left-aligned (`idle`, `working`, `delegating`, `question`, `retry`, `disconnected`)
  - **Warning marker**: `⚠` appended to status if SSE silent > `--warn-sse-secs` OR file age > `--warn-age-hours`
  - Detail: current tool name or `?` for question, empty otherwise (truncated to fit)
  - Age: right-aligned, human-readable (`2s`, `5m`, `1h23m`)
- **Sorting**: Workspace alphabetical, then role alphabetical
- **Empty state**: `no agents connected`

---

## Command Line Interface

```bash
# Launch an agent (repository path)
tools/oc-agent researcher

# Launch through the user command symlink
oc-agent researcher

# Watch mode (default)
python3 -m marduk.marduk --watch

# One-shot (for testing)
python3 -m marduk.marduk --once

# Options
--ports-dir PATH       # Default: ~/.opencode/ports/
--poll-seconds FLOAT   # Default: 1.0 (fallback if no inotify)
--warn-sse-secs INT    # Default: 60 (SSE silent → show ⚠ marker)
--warn-age-hours INT   # Default: 24 (file age → show ⚠ marker)
--compact              # Compact mode for narrow panes
```

---

## Implementation Plan

### Phase 1: Core
1. Port file watcher (inotify via `inotify-simple` or poll fallback)
2. JSON parser with validation
3. SSE client with reconnection logic
4. Event parser → status inference
5. In-memory state store `{session_id: AgentState}`

### Phase 2: Cleanup & Robustness
6. Staleness detector (PID check, TCP connect, SSE silence, file age)
7. Port file cleanup on staleness
8. Startup: read existing files, connect all
9. Signal handling (SIGTERM → clean shutdown)

### Phase 3: Display & Integration
10. Renderer (ANSI, narrow-pane aware)
11. `--watch` loop with 1s redraw
12. `tmux-xlib.sh` integration (4th pane or replace skynet-agents)
13. Compact mode (< 35 cols)

---

## Dependencies
- Python stdlib: `json`, `os`, `pathlib`, `time`, `signal`, `socket`, `select`
- Optional: `inotify-simple` (for inotify; fallback to poll)
- HTTP/SSE: `httpx` (if available) or `urllib.request` + manual SSE parsing

---

## Integration with `tools/oc-agent`

`tools/oc-agent` is the producer of Marduk's port-file contract. It is a general-purpose, role-aware OpenCode launcher: callers provide an agent name, the launcher exports `OPENCODE_AGENT_ROLE`, starts OpenCode on an ephemeral port, discovers the listening port, and writes the metadata file Marduk watches.

```bash
tools/oc-agent researcher
# or, after installing the user command symlink:
oc-agent researcher
```

The launcher and monitor remain separate processes. Marduk does not import or invoke `tools/oc-agent`; it only reads and cleans up files under the configured ports directory. The metadata schema is defined in [Port File Specification](#port-file-specification).

The user-level `oc-agent` command is a symlink to `tools/oc-agent`, so moving the launcher into XLib does not change the existing command.

---

## Testing Scenarios

1. **Single agent, idle** → shows `idle` with increasing age; after `--warn-sse-secs` shows `idle⚠`
2. **Agent working** → shows `working` with tool name
3. **Agent asks question** → shows `question` with `?`
4. **Agent delegates** → shows `delegating` with `task`
5. **Agent exits** → port file cleaned up (PID dead + TCP fail), disappears from display
6. **Agent restarts** → new port file, Marduk reconnects
7. **Marduk starts after agents** → reads existing port files, connects
8. **Multiple workspaces** → grouped by workspace (from cwd or role notes)
9. **Port file orphaned** (PID dead) → cleaned up
10. **SSE disconnect/reconnect** → status shows `disconnected` briefly, then recovers
11. **Long-running session** (>24h) → shows `idle⚠` but port file NOT removed
12. **Very narrow pane** → compact mode works

---

## Future Enhancements
- Clickable: press key to focus tmux pane for that agent (requires tmux integration)
- Filter by workspace: `--workspace=XLib`
- Show current task from agent's role notes
- Color coding for statuses
- Historical timeline (last N status changes)
- Export JSON for other tools