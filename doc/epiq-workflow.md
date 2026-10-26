# Epiq Workflow

Rules specific to how the epiq board is used in this workspace.

## Identity

**Every Epiq action is the agent's, never the human's.** Take the board identity with `epiq_actor_assume` on your own session's MCP server, before the first board call, and again after a server restart. Announcing the name in chat changes nothing: without the assume call, every board write is signed with the human's identity.

- The identity is `opencode/<agent-name>` — the role, **without the slot number**. A name is permanent once it has authored anything; never rename yourself mid-session.
- **Never take a human name or email as a board identity or contributor address.** Acting under the human's identity signs the agent's actions with their name, and claiming their email links their commits to the agent.
- **The human's identity is looked up from git identity — `git config user.name` / `user.email` — never assumed from commit logs or history.** Commits are authored under that configured identity and history carries other contributors too, so an author line is not evidence of who did the work; a different address in history stays unconfirmed until the human claims it.

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

**The commit hook says the same thing from the other side.** A freshly filed
ticket's ref is in the actor's pending log, so `validate-ticket-ref.py` cannot
find it and refuses the commit — correctly, because a ref nobody else can
resolve should not pass. It now names the cause rather than the symptom:

```
ERROR: Ticket ref 'F35YDRX' was filed but not yet synced
```

The plain message — *"Invalid ticket ref"* — is true and useless: the ticket
exists, it just has not been synced, and an agent reading it has nothing to act
on but re-reading the ticket's own title.
