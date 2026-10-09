# Subagent Dispatch

Use `python3 tools/agent-coord.py dispatch <category>` to get the correct worker:

| Category | Worker | Use for |
|----------|--------|---------|
| `coding` | `worker-north-mini-code` | Implementation |
| `reasoning` | `worker-nemotron-ultra` | Deep analysis, architecture |
| `bulk` | `worker-nemotron-lightning` | Speed-critical, repetitive |
| `general` | `worker-longcat` | Text, agentic tasks |

Main model (big-pickle) does planning, clarification, and assumption-auditing directly — do not dispatch these. Dispatch non-trivial work; do simple edits directly. Never re-add `worker-muse-spark` (Meta trains on prompts).
