# Personal Data in a Public Repository

`Xonok/XLib` is **public** (`gh repo view Xonok/XLib` → `visibility: PUBLIC`).
So everything in it is readable by anyone, including the board: the board is
committed to the `__epiq_state__` branch of this repository.

The human's ruling, 2026-10-22:

> Personal details should not be in the repo. Remove them from history and then
> let's figure out ways to prevent this from happening again. These particular
> details aren't sensitive, so it's fine if careful checking of git logs can
> reveal them. The issue is more a matter of principle.

and, on what the repository is for:

> XLib is a project for building public libraries and tools, so anything that
> oversteps that goal by bringing in details that don't matter to the task, or
> are overly revealing should not be included here.

**Narrowed on 2026-10-28, value by value, when the check began refusing commits
in the private workspace.** What he owns is his to publish: *"My private projects
are fine to mention"*, and his email address is allowed *"because it's in git
anyway"*. What is not: his legal name (*"My name no, internet name yes"*), his
colleagues' names, and anything belonging to the employer — a private project is
excluded when it is *work*, not when it is private. Machine-local paths leave for
a different reason: *"that's just because they should be in machine info"*.

## What may not appear in a tracked file, a ticket, or a commit message

1. **Anything that belongs to someone else's work** — the employer, its
		workspace, the projects in it, and anything a tool was written for under an
		employer. **The owner's own private projects are his to name** (his ruling,
		2026-10-28: *"My private projects are fine to mention"*); work is not his to
		publish.
2. **Anything that identifies another person** — a colleague's name is personal
		data too, and it was published here without their knowing.
3. **The owner's legal name.** His handle is not personal data and is allowed,
		and so is his email address, which is already in every commit in the public
		history.
4. **Anything that only makes sense on this machine** — a home path, an account
		name, a private domain. This one is a placement rule rather than a privacy
		rule: those values belong in the git-ignored `machine-info.md` of the
		workspace, never in a tracked file.
5. **Anything that does not matter to the task, or is overly revealing.** A
		repository for public libraries and tools carries the tools' own subject
		matter, not the owner's surroundings.

## Where those values live instead

Outside the repository, in a file the repository never sees:

- a tool's settings — `~/.config/bitbucket/bbprs.json`, mode 600, untracked;
- **the list the check reads** — `~/.config/xlib/personal-details.txt`, one
	literal per line, `#` for a comment, mode 600.

**The token list is outside the repository on purpose.** A check that kept the
forbidden strings in the repository would be the leak it exists to prevent.
The repository says where the list is; the list holds the values.

## How a record says it

The record keeps the meaning and drops the value:

> the tool hardcoded the account, the workspace and the repo list, and a public
> repository that states them states whose it is

not the three of them. The same holds for a document that used a project of
someone else's as an example: it says what the example was *for*, and the example
is one anybody could have written.

## The check

`tools/xlint/_personal.py` scans tracked files for the tokens and reports
`file:line`. It runs in `xlint.py` — so the **pre-commit hook**, which already
runs xlint on the staged `.py`, `.md` and `.sh` files, refuses the commit.

- **Only tracked files.** An untracked file is not published, and a draft may
	carry a value while it is being written.
- **A machine without the list has no protection.** The list is per machine;
	the environment variable `XPERSONAL_DETAILS` points it elsewhere.
- **The check sees the token as a whole word.** A short token does not fire
	inside a longer name that begins with it, and a value spelled differently is
	a value the list does not hold. The check is a net, not a proof.

## The board

The board is a published file, so the same rule applies to a ticket
description and to a comment.

- **Check the text before writing it**: `python3 tools/check-personal.py
	--text` reads it on stdin and exits 1 if it carries an identifier.
- **The pending writes are checked** by `tools/epiq-pending.py`, which the
	workflow already says to run after every board write. A pending file is an
	actor's unsynced writes — the one place where a value can still be caught
	before it is published.
- **The pre-push hook cannot be the gate.** The board's push does not run it:
	the hook rejects the state branch's `[sync|branch:…]` subjects, and the
	branch is up to date on the remote anyway, so epiq pushes past it.

## What is exempt

- **The git history.** By the human's ruling: *"it's fine if careful checking
	of git logs can reveal them."* Rewriting published history would also
	rewrite every commit hash the board's commit-linking reads.

**Nothing in the tracked tree is exempt.** The per-person state files moved to
the private Agents workspace on 2026-10-28 (`KK8RRNQ`); the folder and the
in-repo exemption went with them. The check has no `personal/` exemption left.

## Where this came from

`PNAJ6D0` removed the hardcoded settings from `tools/bbprs/bbprs.py`, and the
record of that fix kept them — one line of the then-tracked `HISTORY.md` quoted
the reviewer's real name, the private workspace slug and the private repo
names, in a public repository. The rule is the answer to that: the values live
outside the repository, the record says what they were for, and the check
catches the next one.
