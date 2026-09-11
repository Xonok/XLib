# agent-coord: Role-Based Notes

## Goal

Add role-based notes shared between agents of the same role within a workspace, alongside existing instance-based notes. Agents promote important discoveries from instance → role notes manually.

## Current State

- `agent-coord.py` assigns slot IDs (`a1`..`a8`) per workspace
- Instance notes: `.agents/agent-notes-{slot}.md` (e.g., `agent-notes-a1.md`)
- Shared notes: `.agents/shared-notes.md` (all agents)

## Design

### Agent Identity

```
workspace/role-N
```

- `workspace` = workspace tag (directory name, e.g., `XLib`, `Agents`)
- `role` = `planner`, `programmer`, `reviewer`, `secretary`, `mechanic`, `researcher`
- `N` = instance number (auto-allocated, recycled)

Example: `XLib/planner-1`, `Agents/secretary-2`

### Note Files

| Type | Path | Scope |
|------|------|-------|
| Instance | `.agents/agent-notes-{role}-{N}.md` | One agent session |
| Role | `.agents/role-notes-{role}.md` | All agents of role in workspace |
| Shared | `.agents/shared-notes.md` | All agents (unchanged) |

### Lifecycle

- **Instance notes**: Created fresh per session. Clean slate preferred. Discarded on `/new` unless agent promotes content.
- **Role notes**: Persistent across sessions. Agents of the role claim before editing (convention). Promoted into manually by agents on discoveries and `/new`.
- **No cross-workspace sync**: Planners in `XLib` ≠ Planners in `Agents`. User explicitly requests sync if needed.

### Allocation & Recycling

- Instance number `N` auto-allocated per (workspace, role) pair
- Recycled when instance process dies (like current slot recycling)
- Max concurrent instances per role: configurable (default 8, same as SLOTS)

### Claims

- Role notes claimed via same `claims.json` mechanism
- Convention: only agents of that role claim `role-notes-{role}`
- No code enforcement — agents know their role

### Backward Compatibility

**None.** Old `agent-notes-a1.md` files ignored. Fresh start.

## Required Changes to agent-coord.py

### 1. Agent ID Format

```python
# Current: workspace/slot (e.g., "XLib/a1")
# New: workspace/role-N (e.g., "XLib/planner-1")
```

### 2. Role Detection

Agent role comes from environment (set by `tools/oc-agent` / `/agents`):
```python
role = os.environ.get("OPENCODE_AGENT_ROLE") or "unknown"
```

### 3. Instance Number Allocation

```python
def allocate_instance(role, workspace_tag):
    """Return next available instance number for (workspace, role), recycling dead."""
    # Scan ids.json for existing role-N entries
    # Check process liveness
    # Return smallest free N (1..max_instances)
```

### 4. Note Path Functions

```python
def instance_note_path(agent_id):  # "XLib/planner-1"
    role, num = agent_id.split("/")[-1].split("-")
    return os.path.join(DIR, f"agent-notes-{role}-{num}.md")

def role_note_path(role, workspace_root):
    return os.path.join(workspace_root, ".agents", f"role-notes-{role}.md")
```

### 5. New Commands

| Command | Purpose |
|---------|---------|
| `role-note [--role ROLE]` | Print path to role notes (defaults to caller's role) |
| `role-claim <paths>` | Claim role notes (convention: caller's role) |
| `role-release <paths>` | Release role notes |
| `role-status` | Show role note claims |
| `instance-note` | Print path to instance notes (replaces `note`) |

`note` command deprecated → `instance-note`

### 6. ID Migration

```python
def my_id():
    # If OPENCODE_AGENT_ID set (explicit), use it
    # Else: role from env, allocate instance, return "workspace/role-N"
    # No migration of old slot-based IDs
```

### 7. Remove Legacy

- `agent-notes-a1.md` style files no longer created/read
- `SLOTS` constant reused for max instances per role
- `ids.json`, `claims.json`, `rule-cursor.json` keyed by new ID format

## Implementation Order

1. Add role detection from env
2. Change ID format to `workspace/role-N`
3. Update `note_path()` → `instance_note_path()`, add `role_note_path()`
4. Add new commands (`role-note`, `role-claim`, `role-release`, `role-status`, `instance-note`)
5. Update `cmd_id`, `cmd_note`, `cmd_workspace` for new format
6. Remove legacy slot allocation logic
7. Test: two agents same role in same workspace share role notes

## Open Questions (Resolved)

| Question | Decision |
|----------|----------|
| Role source | `OPENCODE_AGENT_ROLE` env var |
| Instance number | Auto-allocate + recycle |
| Promote command | Not needed (manual) |
| Role claiming enforcement | Convention |
| Backward compat | None |
| Cross-workspace sync | No (user-initiated only) |

## Files to Modify

- `tools/agent-coord.py` — main changes
- `.agents/ids.json`, `claims.json`, `rule-cursor.json` — new format (auto-migrated on first run)
- No new files

## Dependencies

- `tools/oc-agent` / `/agents` must set `OPENCODE_AGENT_ROLE` (separate concern)
- No Python version or library changes