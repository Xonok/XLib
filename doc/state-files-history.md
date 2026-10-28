# State Files and History

`STATUS.md` states the present: current state, current blockers, current next action. No dated retrospective narrative, no "previously", no "this was wrong because", no superseded states, no "Recently done" section — all of that is `HISTORY.md`. A one-line pointer (`(why: HISTORY.md 2026-09-27)`) is allowed when the reason is load-bearing *right now*.

Finished items are appended to `HISTORY.md` and the status file's open list simply loses them. History is append-only: entries are never rewritten or removed without the human's sign-off, and a correction is a new entry naming the one it supersedes. The Agents workspace holds the full policy and the entry format; see its `plans/history-files.md`.

## Where they live

**Not in this repository.** `Xonok/XLib` is public, so this repository's state files are tracked in the private Agents workspace at `personal/<person>/XLib/{STATUS,HISTORY}.md` — the per-repo subfolder there keeps the one-history-per-person-per-repo split. The root `STATUS.md` symlink and the in-repo `personal/` folder are gone (human's ruling, 2026-10-28; epi `KK8RRNQ`). The dirty-file exemption for them lives with the files, in the Agents workspace's own working-tree rule.

## Who writes them, and when

**The state files are written by the secretary, at merge time. A feature branch does not carry them.**

The files are written where they live, in the Agents workspace; this repository's checkout carries neither, so `doc/working-tree.md` has no exemption for them. `TASKS.md` is not written at all — the taskview store is the record.

The reason is a collision, not a preference. `STATUS.md` is written by every session in the workspace, so it was the file every branch's diff touched — and that is where the conflicts came from: three branches on one evening each carrying a different `STATUS.md`, and one conflicting hunk. The claim system that was meant to prevent it could not. It keyed claims by absolute path, which a worktree changes without changing the file, so two agents could hold the same file and neither could see the other's claim; and nothing checked a claim at commit time, so it protected nothing that the filesystem was not already protecting.

So the rule is: **a Done ticket does not carry `STATUS.md` or `HISTORY.md`.** The work lands in its own branch and its own commit, and the state files are written afterwards — from the ticket and the commit — by the secretary. The agent that did the work says what changed, and a comment on the ticket is enough.

**What this costs an agent**, stated plainly: a ticket that would have carried a state-file update now carries a note instead, and the update happens one step later. That is paid once, and what it buys is that `STATUS.md` — the file every session writes — leaves every branch's diff.

(Ruled by the human, 2026-10-21. Ticket epiq `5S8FY10`; the measurements are in `doc/audits/2026-10-21-claim-system.md`.)
