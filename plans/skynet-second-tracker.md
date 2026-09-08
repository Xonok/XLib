# Skynet Second Agent Tracker

## Goal
Add a second tracker pane showing live agent sessions with workspace-scoped names and statuses, and trim the first tracker to make space.

## Current State
- `tools/skynet.py` (Tracker 1): Shows per-model usage stats (messages, tokens, refusals, finish reasons) in two tables (Window/Today)
- Runs in tmux-xlib.sh right pane with `--watch`

## Tracker 2 Requirements
**Data Source**: opencode's message log (same DB) — need to identify active sessions
- Sessions are active if they have messages within recent window (e.g., last 30 min)
- Session data: `session_id`, `agent_name`, `workspace`, `last_activity`, `status`

**Status inference** from message patterns:
- `idle`: no messages in last ~5 min
- `question`: last message was a question to user (ends with ?, or has no tool calls and short)
- `working`: recent tool calls or long response
- `delegating`: last message dispatched a subagent

**Display Format** (narrow pane):
```
=== Agents (Live) ===

Agents/a1 (Agents)
  secretary    working  2m ago
  mechanic     idle     15m ago

XLib/a1 (XLib)
  planner      delegating  30s ago
  reviewer     question    1m ago
  programmer   working     2m ago

XLib/a2 (XLib)
  researcher   idle        10m ago
```

**Sorting**: First by workspace (alphabetical), then by agent name (alphabetical) — consistent ordering without fiddling.

## Tracker 1 Cuts
To make space for Tracker 2 in tmux layout:
1. **Remove "Active" column** entirely — Tracker 2 shows live status better
2. **Disable (but keep) columns**: Len, Tool, Stop, Unk — hidden by default, togglable via key or flag
3. **Keep core**: Model, Msgs, In, Out, Tot, Ref — these are the essentials

## Implementation Approach
Option A: Single `skynet.py` with two modes (`--mode=usage|agents`)
Option B: Two scripts (`skynet-usage.py`, `skynet-agents.py`)
Option C: One script, two `--watch` panes (tmux splits)

Recommendation: **Option A** — single DB connection, shared poll loop, renders both views. tmux-xlib.sh splits into 3 panes: left (xlint), middle (taskview), right-top (skynet usage), right-bottom (skynet agents).

## Integration
- `tmux-xlib.sh`: Add second split for agents pane
- Shared poll interval (1s)
- Configurable window for "live" sessions (default 30 min)
- Key bindings to toggle hidden columns in Tracker 1

## Status
- [ ] Plan approved
- [ ] Spec written
- [ ] Implementation
- [ ] Test