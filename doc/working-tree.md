# Working Tree

Don't change files that carry uncommitted changes you did not make. Before your first edit, run `python3 tools/agent-coord.py check-clean <path>` — `clean` means proceed, `dirty` means stop and name the blocked file. A file you created yourself earlier in the session is yours to keep editing. The human can override by explicit instruction.

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

## Prefer a worktree to switching at all

The ban is not a claim that changing branch is always the right move. Frequently it is the wrong one. The usual reason to want a different branch is to work on something *else*, and `git worktree add <path> <branch>` gives you that without touching the checkout you are standing in — so another agent's in-progress work, the human's uncommitted edits, and your own all stay exactly where they are. Running two pieces of work in two worktrees is the normal case here, not the exception; opencode can even move a session into a worktree it just created (`opencode.session_move`).

So the order is: **worktree first**, `git switch` only when moving the current checkout is genuinely what you want. The ban stands regardless — `git switch` is at least a command that will not take your work with it.
