# Coordination audit — the file-claim system

Audit date: 2026-10-21
Auditor: XLib/secretary-1
Audited state: working tree at `f8fb1a4` (~12:00 EEST)
Ticket: epiq `5S8FY10` (Todo, assigned to `opencode/secretary`)

## Summary

**The claim system prevents nothing at commit time, and the collision it was
written for is not currently happening. It should go. But the ticket bundles a
second decision with it, and that one is yours.**

Three findings, all measured rather than read off the ticket:

1. **Nothing checks a claim at commit time.** The pre-commit hook runs xlint;
	the pre-push hook validates ticket refs. Neither reads `claims.json`. A claim
	stops a cooperative agent that asks, and nothing else.
2. **The claim key is the path, and the path differs per worktree — so the same
	file can be claimed twice, by two agents who cannot see each other's claim.**
3. **0 of the 4 open branches modify the state files**, and `git merge-tree`
	between the two live branches is clean. The collision the proposal exists to
	prevent is not currently happening.

And the finding that cuts the other way: **the thing the claim system was
protecting is the one file set every session writes**, so removing the guard is
not free — it is only free if something else takes its place.

## What the system is

`tools/agent-coord.py` keeps `.agents/claims.json` (gitignored) — a map from an
agent id to the paths that agent has claimed. Five subcommands use it:
`claim`, `release`, `release-all`, `status`, `check-clean`. `AGENTS.md` says
*"Coordinate through `tools/agent-coord.py`: claim files before editing, release
when done, `status` to see who holds what"*, and `doc/working-tree.md` says to
run `check-clean` before a first edit.

`5S8FY10` proposes removing all five, on the grounds that **a worktree per
ticket makes the filesystem the boundary instead**, and that the claim system is
*"a second mechanism that is wrong exactly where it matters"*.

## The measurements

### 1. Nothing enforces a claim at commit time

The hooks are the only automated gates, and they do not read the claims:

| Gate | What it checks | Reads claims? |
|------|-----------------|----------------|
| `tools/hooks/pre-commit` | xlint on staged `.py`/`.md` | no |
| `tools/hooks/pre-push` | ticket-ref format and resolvability | no |

So the claim's whole force is that an agent asks. `cmd_claim` refuses a path
another agent holds — but the agent whose claim is refused can be the *only*
one that never asked, and then there is no refusal to receive.

**The 2026-10-21 incident is the shape of this.** Another session had a branch
checked out in the shared root; a state-file commit landed on their branch and
carried their already-staged files with it. The claim on
`personal/Xonok/STATUS.md` was held at the time and had no bearing on it —
because the shared **index**, not the shared **file**, was what carried the
work.

### 2. The same file can be claimed twice, and the two claims are invisible to each other

`.agents/` is gitignored (`.gitignore:2`), so a worktree does not get one.
Measured across the three live worktrees:

| Checkout | `.agents/` | `claims.json` |
|----------|------------|---------------|
| the root | yes | yes |
| `.work/JD9DWVN-bundle-traveller` | yes | yes |
| `/storage/worktrees/XLib-E2HSR7A` | **no** | **no** |
| `/storage/worktrees/XLib-SGZN1Y9` | **no** | **no** |

So the ticket's 2026-10-01 measurement — *"neither worktree has a `.agents/`
directory at all"* — is now **half** true, and the half that changed is the
worse one. **The two `claims.json` files are disjoint**, and a path inside one
carries the worktree prefix that the other does not. The worktree's claims
today, keyed by the absolute path of its own checkout:

	<that checkout>/tools/pybundle/bundler.py

The **same source file**, claimed from the root checkout, is keyed:

	<this checkout>/tools/pybundle/bundler.py

**Two claim keys for one file, in two claim stores.** The key is the resolved
absolute path (`claim_paths`, `agent-coord.py:659`), and a worktree changes
that path without changing the file — so the two agents holding them cannot
see each other's claim, and the conflict check, which compares key strings,
cannot fire.

An agent in a worktree with no `.agents/` gets **no claim at all** — and
nothing tells it so.

### 3. The collision the proposal exists to prevent is not currently happening

`5S8FY10` was written on 2026-10-01 against eight open branches and recorded
three tickets colliding on `personal/Xonok/STATUS.md` and two on
`tools/taskview/SPEC.md`. Measured today:

| Branch | commits ahead | modifies the state files? |
|--------|---------------|-----------------------------|
| `E2HSR7A-habit-cell` | 1 | no |
| `SGZN1Y9-code-mode-calls` | 1 | no |
| `fix/JD9DWVN-bundle-traveller` | 6 | no |
| `__epiq_state__` | 222 | no |

and `git merge-tree --write-tree` between the two live branches is **clean** —
exit 0, one tree, no conflict. The branches carry *stale copies* of the state
files (they were cut from an older master), which is not a conflict: git
resolves that in master's favour.

**So the case for the change is now a case for the principle, not for a live
defect.** That is a legitimate reason to make a rule. It is not a reason to
pretend there is a fire.

### 4. The tools are used by the secretary, and by nobody else

Across the eleven agent-note files, `check-clean` appears in the secretary's
notes (7 in `secretary-1`, 1 each in `secretary-4` and `secretary-5`) and in
**none** of the mechanic, planner, programmer or reviewer notes. `agent-coord.py
claim` appears **once** in all of them, in `planner-1`. The agents that edit
the most code never claim anything.

### 5. What the removal costs

| Thing | Where | Size |
|-------|-------|------|
| `claim_paths`, `cmd_claim`, `cmd_release`, `cmd_release_all`, `cmd_status` | `tools/agent-coord.py:659`, `688`, `714`, `725`, `733` | ~58 lines |
| `cmd_check_clean` | `tools/agent-coord.py:1102` | ~30 lines |
| the `CLAIMS` constant and the claims state | `tools/agent-coord.py:9`, `.agents/claims.json` | — |
| five subparser registrations | `tools/agent-coord.py:1139–1149` | — |
| the rule | `AGENTS.md:7`, `AGENTS.md:37` | 2 rows |
| the check-clean step | `doc/working-tree.md` | 1 paragraph |

**One thing goes with it that is worth naming.** `5S8FY10` has sat for 20 days
partly because removing the claim system also removes the class of bug where
`news` wiped every agent's claims and the rule cursor (epi `K93Z39B`, PRs #47
and #50 — *"the claims-wipe is genuinely fixed"*). **If the claims go, that
whole class of repair stops being needed**, including the two PRs that fixed it.

## The options

### A — Delete the claim system, and change nothing else

What the ticket proposes, minus its second half. The filesystem is the
boundary; the state files are written by whoever is in the secretary seat.

*Fixes:* a mechanism that enforces nothing, over a file set it cannot see.
*Costs:* the state files have **no** guard at all. Two agents writing
`personal/Xonok/STATUS.md` at once is a silent last-writer-wins, and nothing
reports it. The `check-clean` step in `doc/working-tree.md` goes with it — and
that step is currently the *only* thing that stops an agent from editing a file
another session has uncommitted changes in, which the incident above shows is
not hypothetical.

### B — Delete the claim system, and adopt the merge-time state-file rule

What the ticket actually proposes. `personal/<person>/{STATUS,HISTORY,TASKS}.md`
are written by the secretary **at merge time**, not carried on feature
branches. That takes `STATUS.md` out of every branch's diff — which is where
all three of the ticket's original collisions came from.

*Fixes:* the collision class, by construction rather than by checking.
*Costs:* **it changes what a Done ticket is allowed to contain.** A ticket
whose work includes a state-file update can no longer carry it in the same
commit. The secretary becomes a merge-time step in every agent's workflow, and
the human's word has to say so in `AGENTS.md` or it will not happen.

### C — Keep the claim system, and make it real

Enforce it: the pre-commit hook reads `claims.json` and refuses a commit that
touches a path another agent holds. Fix the key to be repo-relative so a
worktree and the root agree.

*Fixes:* the silent last-writer-wins, for real.
*Costs:* a gate that can block a commit, and a false positive that stops
someone's work. **This is the opposite of the ticket's direction** and it is
listed because it is the option that keeps the protection.

### D — Keep the claim system as it is

*Costs:* an agent can believe it is protected and not be. That is the worst of
the four, because the belief is the dangerous part.

## The recommendation

**Option B, and it needs one line from you.**

The measurements support the ticket's direction: the claim system enforces
nothing, it cannot see across worktrees, and the tools are used by one seat out
of six. But the ticket's own text flags the second half as *"the part
worktrees do not replace"* — and that is where the decision is, because it
changes what a Done ticket may contain.

The question to settle is narrow:

> **Do `personal/<person>/{STATUS,HISTORY,TASKS}.md` get written by the
> secretary at merge time, instead of being carried on feature branches?**

If **yes**: Option B, and the rule goes into `AGENTS.md` and
`doc/working-tree.md` so every agent inherits it — with the merge-time step
made explicit, because a rule that only the secretary knows is a rule that only
the secretary follows.

If **no**: Option A, and the state files need *some* guard, because today the
only one they have is an advisory claim that two worktrees cannot see.

**A third possibility worth naming**, because it is cheap and it might be
enough: **keep `check-clean`, drop `claim`/`release`/`status`.** `check-clean`
is the one with teeth — it reads the *working tree*, so it works in any
checkout, sees across worktrees, and needs no shared state at all. The claim
system's key is the thing that is broken; `check-clean`'s key is the git status,
which is already per-checkout and correct.

## What was not decided here

- **The implementation.** Removing five subcommands from `tools/agent-coord.py`
	is programmer work, and the secretary does not write programs.
- **Whether the state files move to merge time.** That is the human's, and it
	is the whole of the ticket's open half.
- **The `news` repair.** If the claims go, epi `K93Z39B`'s two PRs become
	unnecessary — but they are already merged and fixing a live thing is not
	worth reverting. Whether to note that on that ticket is separate.

## Reproducing the measurements

	# 1. the hooks do not read claims
	grep -l claims tools/hooks/* # nothing
	cat tools/hooks/pre-commit tools/hooks/pre-push

	# 2. two disjoint claim stores, same file under two keys
	ls -d .work/*/.agents # the worktrees inside this checkout
	cat .agents/claims.json .work/*/.agents/claims.json
	# the worktrees made outside this checkout have no .agents/ at all;
	# .agents/machine-info.md says where they live

	# 3. no branch modifies the state files
	for b in $(git branch --format='%(refname:short)' | grep -v master); do
		echo "$b: $(git log master..$b --oneline -- personal/Xonok/ | wc -l)"
	done
	git merge-tree --write-tree --name-only E2HSR7A-habit-cell SGZN1Y9-code-mode-calls

	# 4. the tools are used by one seat
	grep -c "check-clean" .agents/agent-notes-*.md

	# 5. the size of the removal
	grep -n "^def cmd_claim\|^def cmd_release\|^def cmd_status\|^def cmd_check_clean" \
		tools/agent-coord.py
