# Tool Schema Caching

Reference, not rules: what the mechanism is and what integrating it would take.
The tool it describes is `tools/tool_schema_cache.py`, in this repo, and
**nothing calls it** — it was built and left unwired, so treat every integration
step below as a proposal rather than a description of working behaviour.

Written 2026-09 as an Agents-workspace library entry; moved here 2026-10-02 so the
tool and its documentation sit in one repo. Until then every command in it named a
path that did not exist in the repo holding it.

## What It Is

A mechanism to reduce per-turn token overhead by sending full tool schemas **once** (turn 1), then referencing them by stable ID in all subsequent turns.

**Typical savings: ~85% after turn 1** (4,000 tokens → ~200 tokens for tool definitions).

---

## Core Concepts

| Concept | Description |
|---------|-------------|
| **Stable ID** | `toolname_v<hash>` — derived from schema content hash (first 12 chars of SHA256). Changes only when schema changes. |
| **Schema version** | Monotonic version in output (`schema_version: "1"`) so consumers can detect format changes. |
| **Two output modes** | `first-turn` (full schemas + IDs) and `subsequent-turn` (IDs only). |

---

## Key Mechanisms

### 1. Initialization
```bash
python3 tools/tool_schema_cache.py init
```
Generates `definitions.json` and `ids.json` in `.schema_cache/` from built-in `TOOL_SCHEMAS` dict.

### 2. Turn 1 — Full Schemas
```bash
python3 tools/tool_schema_cache.py first-turn
```
Output:
```json
{
  "schema_version": "1",
  "tools": [
    {"id": "read_v3a7f2e1...", "schema": {...}},
    {"id": "write_v8b1c4d2...", "schema": {...}},
    ...
  ]
}
```
Model sees full parameter types, required fields, enums, descriptions.

### 3. Turn 2+ — IDs Only
```bash
python3 tools/tool_schema_cache.py subsequent-turn
```
Output:
```json
{
  "schema_version": "1",
  "tool_ids": ["read_v3a7f2e1...", "write_v8b1c4d2...", ...]
}
```
Model must remember schemas from turn 1 context.

### 4. Verification
```bash
python3 tools/tool_schema_cache.py verify
```
Compares cached IDs against current `TOOL_SCHEMAS` — exits 1 if mismatch (schemas changed, need re-init).

---

## Invariants

| Invariant | Why |
|-----------|-----|
| ID changes iff schema changes | Content-addressable — no manual version bumps |
| `schema_version` increments only on output format change | Consumers can parse safely |
| Cache is per-workspace (`.schema_cache/`) | Different workspaces may have different tool sets |
| All tools always listed in `tool_ids` | Model can reference any tool; parallel calls still work |

---

## Gotchas

| Issue | Mitigation |
|-------|------------|
| **Context compaction (`/compact`)** drops turn 1 → schemas lost | Re-run `first-turn` after compact, or pin turn 1 in context |
| **Subagents** need their own cache or inherit parent's | Pass parent's IDs to subagent prompt, or run `init` in subagent |
| **Schema changes** (new tool, param added) | Run `verify` → if mismatch, run `init` → next turn uses new IDs |
| **Model forgets schemas** (long session, context pressure) | Periodic `first-turn` refresh; or compress schemas instead |

---

## Integration Points

### In opencode prompt building
```python
# Pseudocode
if turn == 1:
    tools_block = run("tool_schema_cache.py first-turn")
else:
    tools_block = run("tool_schema_cache.py subsequent-turn")
prompt = f"{system}\n{history}\n{tools_block}\n{user_message}"
```

### In agent-coord.py (future)
Could add a `tools` subcommand that wraps this, or integrate into the prompt-building pipeline.

---

## Comparison

| Approach | Turn 1 | Turn 2+ | Parallel Calls | Reliability |
|----------|--------|---------|----------------|-------------|
| Full schemas every turn | 4,000 | 4,000 | ✅ | ✅ |
| **Schema caching** | 4,000 | **~200** | ✅ | ⚠️ (needs context) |
| Tool router | ~1,200 | ~1,200 | ✅ | ⚠️ (misroute risk) |
| Lazy-load (fetch on use) | ~200 | variable | ❌ | ❌ |

---

## References

- Implementation: `tools/tool_schema_cache.py`, this repo
- Related, in the Agents workspace: `library/tools/opencode-architecture.md` and `library/tools/agent-coordination.md`
- The original write-up notes were in the Agents workspace's `.agents/shared-notes.md`, which is git-ignored and since been refit to hold standing facts only — not a durable reference, which is part of why this doc was moved rather than left to point at it.

---

## Measuring Impact

### Baseline (Current State)

opencode already shows token usage per message in the message log. Run a typical session (5–10 turns with tool use) and record prompt tokens per turn.

| Turn | Prompt Tokens | Completion Tokens |
|------|---------------|-------------------|
| 1    | ~4,500        | ~2,000            |
| 2    | ~4,500        | ~2,000            |
| 3    | ~4,500        | ~2,000            |
| ...  | ...           | ...               |

Tools contribute ~3,000–4,000 tokens to every prompt.

### Required Integration (opencode)

Modify opencode's prompt builder to call the cache tool. Key integration points:

| Location | What to Find |
|----------|--------------|
| Prompt assembly | Code combining system + history + tools + user message |
| Tool schema injection | Where tool JSON schemas are serialized into prompt |
| Turn/session tracking | How opencode knows "this is turn N" |

**Likely files** (opencode internals):
- `packages/opencode/src/app/prompt/`
- `packages/opencode/src/app/agent/`
- `packages/opencode/src/app/completion/`

### Minimal Integration Prototype

```python
# In opencode's prompt builder
import os
import subprocess
from pathlib import Path

SCHEMA_CACHE = Path(os.environ.get("XLIB", "/path/to/XLib")) / "tools" / "tool_schema_cache.py"

def get_tools_block(session) -> str:
    has_schemas = _context_has_schema_block(session.history)
    is_turn_1 = len(session.history) == 0
    
    mode = "first-turn" if (is_turn_1 or not has_schemas) else "subsequent-turn"
    return subprocess.run(
        ["python3", str(SCHEMA_CACHE), mode],
        capture_output=True, text=True, check=True
    ).stdout

def _context_has_schema_block(messages) -> bool:
    for msg in messages[:3]:
        if "schema_version" in msg.content:
            return True
    return False
```

### Measurement Harness

```bash
#!/usr/bin/env bash
# measure_tokens.sh — compare same task with/without caching

TASK="Read AGENTS.md, list all .md files in doc/, summarize them"

echo "=== BASELINE ==="
opencode run --model nemotron-3-ultra-free --print-tokens "$TASK" 2>&1 | tee baseline.log

echo "=== WITH CACHE ==="
opencode run --model nemotron-3-ultra-free --print-tokens "$TASK" 2>&1 | tee cached.log

# Parse and compare
python3 << 'EOF'
import re

def parse_log(path):
    with open(path) as f:
        content = f.read()
    turns = re.findall(r'prompt.*?(\d+).*?completion.*?(\d+)', content, re.S)
    return [(int(p), int(c)) for p, c in turns]

base = parse_log("baseline.log")
cached = parse_log("cached.log")

print(f"{'Turn':<5} {'Baseline':>10} {'Cached':>10} {'Saved':>10} {'%':>6}")
for i, ((bp, bc), (cp, cc)) in enumerate(zip(base, cached), 1):
    saved = bp - cp
    pct = 100 * saved / bp if bp else 0
    print(f"{i:<5} {bp:>10} {cp:>10} {saved:>10} {pct:>5.1f}%")
EOF
```

### Metrics to Capture

| Metric | Target |
|--------|--------|
| Prompt tokens/turn (turn 2+) | ~200 (vs ~4,000 baseline) |
| Total session tokens (10 turns) | ~60% reduction |
| First-turn cost | Unchanged (~4,000) |
| Latency overhead | <50ms (subprocess call) |
| Tool misuse rate | <1% (model uses correct IDs) |

### Quick Simulation (No opencode Changes)

```bash
# Raw prompt size comparison
python3 << 'EOF'
import subprocess

FULL = subprocess.check_output(["python3", "tools/tool_schema_cache.py", "first-turn"])
IDS  = subprocess.check_output(["python3", "tools/tool_schema_cache.py", "subsequent-turn"])

print(f"Full schemas: {len(FULL)} bytes  ~{len(FULL)//4} tokens")
print(f"IDs only:     {len(IDS)} bytes   ~{len(IDS)//4} tokens")
print(f"Savings/turn: ~{(len(FULL)-len(IDS))//4} tokens")
EOF
```

**Expected output:**
```
Full schemas: 12000 bytes  ~3000 tokens
IDs only:      600 bytes   ~150 tokens
Savings/turn: ~2850 tokens
```

### Integration Checklist

- [ ] Fork/build opencode
- [ ] Add schema cache call in prompt assembly
- [ ] Track turn number / session state
- [ ] Detect `/compact` / `/new` → re-send `first-turn`
- [ ] Run identical tasks, compare token logs
- [ ] Test edge cases: subagents, compact, long sessions
