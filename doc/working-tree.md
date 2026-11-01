# Working Tree

Don't change files that carry uncommitted changes you did not make. Before your first edit, run `python3 tools/agent-coord.py check-clean <path>` — `clean` means proceed, `dirty` means stop and name the blocked file. A file you created yourself earlier in the session is yours to keep editing. The human can override by explicit instruction.

## No state-file exception here

The per-person state files live in the private Agents workspace at `personal/<person>/XLib/`; this checkout carries none, so there is nothing here to exempt from the dirty-file rule. The exemption and its reasoning are in that workspace's own working-tree rule (`KK8RRNQ`, 2026-10-28).

## The root checkout stays on `master`

**Agents must not move the main (root) checkout off `master`.** No `git switch`, no changing HEAD, no checking out another branch in it — unless the human explicitly authorizes it in the current conversation. The human always works on `master`; other branches are for agent work when they need them, and the human only goes to another branch when they explicitly want to.

This rule is about **branch movement**, not about avoiding changes. Editing files on `master` is normal and expected; the human does most of their work there. Worktrees (`.work/<ticket>-<slug>`) exist for work that might break something — the human's system, or a tool they depend on — not as a default for routine work. If you need a different branch, make a worktree; do not move the checkout the human is standing in. (Human, 2026-11-01.)

## The boundary is the worktree

**Work in a worktree, one per ticket.** `git worktree add .work/<ticket>-<slug> -b fix/<ticket>-<slug> master` gives you your own checkout, so two agents cannot edit one file in one place, and a commit in one cannot land on another's branch. The root checkout is shared, and so is its **index**: a commit made there can carry another session's staged work under your subject. That happened on 2026-10-21, and the recovery kept both works.

**There is no file-claim mechanism.** This repository had one until 2026-10-21 — `agent-coord.py claim`, `release`, `release-all` and `status` — and it was retired (epiq `5S8FY10`, ruled by the human). Two measurements said it had to go: it keyed claims by absolute path, which a worktree changes without changing the file, so the same file could be claimed twice in two disjoint claim stores and the conflict check could not fire; and nothing checked a claim at commit time, so it protected nothing.

`check-clean` stays, and it is the guard that remains: it reads the **working tree**, so it needs no shared state, works in any checkout, and sees across worktrees. The claim system's key was the thing that was broken, and `check-clean` has no key.

## Who writes the state files

**Not a feature branch.** The state files are written by the secretary, at merge time, in the Agents workspace. A Done ticket does not carry them — the rule and its reason are in `doc/state-files-history.md`.

## `git checkout` is banned

**Never run `git checkout`.** Use `git switch` to change branch and `git restore` to change a file. This is a blanket ban until further notice, not a preference to weigh case by case.

`git checkout` is two unrelated commands sharing one name, and the second is the hazard. `git checkout <branch>` switches branches. `git checkout -- <file>` and `git checkout <commit> -- <file>` overwrite the working-tree copy from the index or from a commit — which **discards uncommitted edits, silently, with no warning and nothing to undo**. Both are one keystroke apart in the muscle memory of the branch form. An agent reaching for `git checkout <file>` to undo its own last edit gets every other uncommitted edit in that file destroyed instead, which is what happened here: `tools/marduk/marduk.py` lost a session's worth of fixes to one such command and was only caught because the test suite failed 21 tests (`.agents/agent-notes-secretary-1.md`, 2026-10-16).

The replacements are not merely safer by convention, they are structurally incapable of the accident:

- `git switch -- f.txt` fails with `fatal: invalid reference: f.txt` (exit 128). `git switch` has no file-restoring form, so the destructive version cannot be typed at all.
- `git restore` *does* overwrite a file — that is its only job — so when it is what you want, saying it means you meant it.

| Instead of | Use |
|---|---|
| `git checkout <branch>` | `git switch <branch>` |
| `git checkout -b <branch>` | `git switch -c <branch>` |
| `git checkout -` | `git switch -` |
| `git checkout --detach <commit>` | `git switch --detach <commit>` |
| `git checkout -- <file>` | `git restore <file>` |
| `git checkout <commit> -- <file>` | `git restore --source <commit> <file>` |

## `git reset --hard` and `git reset --merge` are banned

**Never run `git reset --hard` or `git reset --merge`.** Plain `git reset` is allowed, but read the next section before you use it — it is safe in a way that is not obvious, and dangerous in a way that is silent.

The two banned forms are the worktree-touching ones, and they are banned for the same reason `git checkout -- <file>` is: they overwrite files from a commit and discard what was in them, with no warning and nothing to undo. Measured 2026-10-19 in a scratch repository holding one tracked file with an uncommitted edit, one file staged as new, and one untracked file:

| command | the uncommitted edit | the staged-new file | the untracked file |
|---|---|---|---|
| `git reset <commit>` (mixed, the default) | survives | survives, but **becomes untracked** | survives |
| `git reset --soft <commit>` | survives | survives, still staged | survives |
| `git reset --merge <commit>` | survives | **deleted from disk** | survives |
| `git reset --keep <commit>` | survives (it aborts if the edit would be hit) | deleted from disk | survives |
| `git reset --hard <commit>` | **reverted to the committed content** | **deleted from disk** | survives |
| `git reset <commit> -- <path>` | survives | survives, still staged | survives |

**`git reset --hard` is worse than `git checkout -- <file>` in two ways.** It takes the whole tree rather than one file, and it **moves HEAD**, so it can orphan a commit that was never pushed. Measured: after `git reset --hard` to an older commit, the newer commit was reachable from no branch at all and survived only in the reflog, where it is subject to `gc.reflogExpire` — 90 days by default. This is the shape that ran against this repository on 2026-10-19 at 17:50:06, and it cost nothing **only because the work had already been pushed**.

**`git reset --merge` is banned too, and it is the one nobody suspects.** It reads like a gentler `--hard` — "keeps the files that have local changes" — and it does keep an edited file. But it **deletes a file that is staged as new**, because such a file is identical in the index and in the working tree, so "keep what differs between index and working tree" does not apply to it. Measured: deleted from disk, no warning.

### Plain `git reset` is not banned, and here is why

**It does not touch the working tree.** Every uncommitted edit survives it, and an untracked file is untouched. That is the answer to "is it dangerous", and it is the opposite of what the name suggests.

What plain `git reset` resets is the **index**, and that has a cost in a shared checkout: **a file another agent has staged becomes untracked**, so the commit that follows silently omits it. Measured: with `c.txt` staged, `git commit` included it; after a plain `git reset`, the same `git commit` included only `b.txt`, and `c.txt` sat untracked with no error and no warning. So it is dangerous, but the danger is **silent rather than destructive** — which is the harder kind to notice and the easier kind to cause by accident.

Use the form that says what you meant:

| Instead of | Use |
|---|---|
| `git reset <commit>` to move HEAD | `git reset --soft <commit>` — moves HEAD, leaves index and worktree alone |
| `git reset <commit> -- <file>` to unstage one file | `git restore --staged <file>` |
| `git reset --hard <commit>` | **banned** — `git switch` to move, `git restore` for a file, `git worktree add` for other work |
| `git reset --merge <commit>` | **banned** — it deletes staged-new files from disk |

## Prefer a worktree to switching at all

The ban is not a claim that changing branch is always the right move. Frequently it is the wrong one. The usual reason to want a different branch is to work on something *else*, and `git worktree add <path> <branch>` gives you that without touching the checkout you are standing in — so another agent's in-progress work, the human's uncommitted edits, and your own all stay exactly where they are. Running two pieces of work in two worktrees is the normal case here, not the exception; opencode can even move a session into a worktree it just created (`opencode.session_move`).

So the order is: **worktree first**, `git switch` only when moving the current checkout is genuinely what you want. The ban stands regardless — `git switch` is at least a command that will not take your work with it.
