# Epiq Workflow

Rules specific to how the epiq board is used in this workspace.

## Per-actor writes

`epiq_sync` drains **only the calling actor's own** event log. Every actor writes to its own `~pending*.jsonl` in the state worktree, which `.epiq/events/.gitignore` never commits; the drain happens when a process running *as that actor* syncs.

So an actor whose process has exited strands its writes permanently, and nothing reports it. Two consequences:

- **Sync before the session ends.** A board write that has not been synced is not durable, and `epiq_sync` returning `skipped: true` means *nothing new to commit*, not *nothing to do*.
- **Check for other actors' stranded events** with `python3 tools/epiq-pending.py` (exits 1 if any project has undrained events). It reports stranded events per actor and, more importantly, board nodes that committed events reference but whose creation was never committed — a clone cannot resolve those. Run it when a board state looks wrong, when `epiq_sync` skips unexpectedly, or at session start.

Draining another actor's events needs a session that assumes that identity, which rewrites who the drain is attributed to. Ask the human before doing it.

## Sync twice

**A sync that reports `skipped: true` has not drained anything, so sync again.**

The pending log has to be finalised before it is flushed into the committed log,
and the flush is what commits it — so the first `epiq_sync` after a board write
can skip while the events are still only in the pending file. Measured twice on
2026-10-20: the first sync after a write returned `skipped: true` with the
events still pending, and a later call drained and pushed them; on another
occasion it skipped twice in a row before draining.

**So the rule is: write to the board, sync, check, and sync again while the
check still says so.** The check is `python3 tools/epiq-pending.py`, and the
line that matters is:

```
epiq project 01M3BVEC...: no stranded events (8 events in flight, not yet synced)
  these writes are not durable: run epiq_sync again until this line is gone
```

**"in flight, not yet synced" means the writes have not happened.** They sit in
the actor's pending log, which `.epiq/events/.gitignore` never commits, and if
that process exits they are stranded permanently — only a session running as
that actor can drain them.

The rule is there because the failure is invisible. A skipped sync reads like a
successful one, and the board looks right on screen, because the events are in
the actor's own memory and the pending log is not part of what a reader sees.
**A board write that was never synced is a write that did not happen** — and
the usual symptom is a ticket that reads as shipped on this machine and as
never-started on every other one.

**Never end a session with "events in flight".** It is the one line in the
check that says your own work is still only in a file.
