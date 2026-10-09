# Epiq Workflow

Rules specific to how the epiq board is used in this workspace.

## Per-actor writes

`epiq_sync` drains **only the calling actor's own** event log. Every actor writes to its own `~pending*.jsonl` in the state worktree, which `.epiq/events/.gitignore` never commits; the drain happens when a process running *as that actor* syncs.

So an actor whose process has exited strands its writes permanently, and nothing reports it. Two consequences:

- **Sync before the session ends.** A board write that has not been synced is not durable, and `epiq_sync` returning `skipped: true` means *nothing new to commit*, not *nothing to do*.
- **Check for other actors' stranded events** with `python3 tools/epiq-pending.py` (exits 1 if any project has undrained events). It reports stranded events per actor and, more importantly, board nodes that committed events reference but whose creation was never committed — a clone cannot resolve those. Run it when a board state looks wrong, when `epiq_sync` skips unexpectedly, or at session start.

Draining another actor's events needs a session that assumes that identity, which rewrites who the drain is attributed to. Ask the human before doing it.
