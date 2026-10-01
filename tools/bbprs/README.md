# Bitbucket API for agents — briefing

Everything an agent needs to read pull requests for the mms work repos, plus
the four traps that each cost real time on 2026-09-28. Verified against the
live API that day.

**Companion tool:** `bbprs.py` in this directory does the triage part and
encodes traps 1–3. Use it first, drop to raw `curl` when you need the comment
or commit threads, which it does not fetch.

## Who and what

| | |
|---|---|
| Human's Bitbucket account | **`Kaarel Veldre`** — he is the author on his own PRs, and a reviewer on colleagues' |
| Workspace | `matchmysound` |
| Repos | `mms-frontend` (the Angular app — where the PRs live), `mms` (Django backend) |
| Base branch | `master` for the human's PRs; colleagues use **stacks**, so a PR's `destination` is often another branch, not `master` |

`gh` is irrelevant here — the remote is Bitbucket, not GitHub.

## Credentials

- **Path:** `~/.config/bitbucket/credentials`, mode `600`, netrc format.
- **Contents:** `machine api.bitbucket.org`, `login` = the Atlassian account
	email, `password` = the API token. `login` is the **email**, not the
	Bitbucket username.
- Use **`--netrc-file`**, never a bare `~/.netrc`: git reads `~/.netrc`
	automatically, so a token there can be silently used for pushes.
- The human types the token himself. **Never ask for it in chat, never print
	it, never `export` it, never put it in a repo or a notes file.** An exported
	secret leaks into every child process.
- Scopes present on the current token: `read:repository:bitbucket` and
	`read:pullrequest:bitbucket`. Both are needed and **neither implies the
	other**. App passwords no longer exist in the UI; API tokens replaced them.

The human's own setup command, if the file ever needs recreating:

```bash
mkdir -p ~/.config/bitbucket && chmod 700 ~/.config/bitbucket
read -r -s -p "Bitbucket API token: " TOKEN; echo
read -r -p "Atlassian account email: " EMAIL
umask 077
printf 'machine api.bitbucket.org\n  login %s\n  password %s\n' "$EMAIL" "$TOKEN" \
  > ~/.config/bitbucket/credentials
chmod 600 ~/.config/bitbucket/credentials
unset TOKEN
```

## The relevance rule

**Only open PRs matter. Drafts matter only when they are the human's own.**
On 2026-09-28, 8 of the 16 PRs returned by a plain `state=OPEN` query on
`mms-frontend` were drafts, and three of the five apparent "blockers" were
drafts — colleagues still working, not PRs waiting on a reviewer. Getting this
wrong sends someone to review an unfinished draft.

## Endpoints

Base: `https://api.bitbucket.org/2.0/repositories/matchmysound/mms-frontend`

| Need | Endpoint |
|---|---|
| List open PRs | `/pullrequests?state=OPEN&pagelen=50` |
| One PR, with participants | `/pullrequests/{id}` |
| Comment thread | `/pullrequests/{id}/comments?pagelen=50` |
| Commits on the branch | `/pullrequests/{id}/commits?pagelen=50` |
| Changes/diff | `/pullrequests/{id}/diff` or `/diffstat` |

```bash
curl -sS --netrc-file ~/.config/bitbucket/credentials -H 'Accept: application/json' \
  "$URL" | jq .
```

## The five traps

1. **Drafts come back inside `state=OPEN`.** A draft is `state: OPEN` *plus* a
	separate `draft: true` field, so the list endpoint returns them and you must
	filter on `.draft` client-side. There is **no `&draft=true` query
	parameter** — it returns HTTP 400.

2. **The list endpoint omits `participants` entirely.** The field is *absent*
	from every item, not empty. Trusting it makes every PR look unassigned and
	silently breaks the "who is blocking whom" question, because the
	blocked-on-me check becomes permanently false. **Fetch each PR
	individually** for participants. This is the trap most likely to make a tool
	confidently wrong rather than fail.

3. **`pagelen` maxes out at 50.** `pagelen=100` returns HTTP 400 with
	`{"error":{"message":"Invalid pagelen"}}`.

4. **`/pullrequests/{id}/commits` has no usable `size` field** — it comes back
	`null`. Count with `(.values | length)`, not `.size`.

5. **`approved: false` is ambiguous — only `state` tells the two apart.** A
	reviewer who **requested changes** and a reviewer who **never looked** both
	arrive as `approved: false`, so reading that boolean alone makes a PR the
	human has already answered report as `BLOCKED ON YOU` — the inverse of the
	truth, and a standing instruction to re-review a colleague's PR. Read
	`state`: `"changes_requested"` means the human has done his part and the
	ball is with the author. Worse, Bitbucket spells "no state" as JSON `null`
	*and* as the string `"null"` on different records; the string is truthy, so
	normalize it before comparing. Ticket `3EEXMRK`; the regression is
	`mms-frontend` #79.

## Read-only, and it stays that way

Perform GETs and nothing else. **Never post a comment, approve, decline,
merge or push with this token** — acting on a colleague's PR in the human's
name is his decision, not an agent's. A tool that reads PRs is genuinely
useful; a tool that can merge is a hazard, and the token is scoped for reading
in practice.

## The concrete task: PR#70

`note-viewer-part-staff-switch` (#70, author Timo Tambet). **The human has
already reviewed this once.** The question is *not* "review it again" — it is
**whether the five points he raised were actually dealt with**.

The five points are his comments on 2026-09-18, all in **Estonian** (so does
the surrounding discussion, and the commit messages — an agent must be able to
read Estonian to do this job):

```bash
curl -sS --netrc-file ~/.config/bitbucket/credentials -H 'Accept: application/json' \
  'https://api.bitbucket.org/2.0/repositories/matchmysound/mms-frontend/pullrequests/70/comments?pagelen=50' \
  | jq -r '.values[] | select(.user.nickname=="Kaarel Veldre")
  | "#\(.id) \(.created_on[0:16])\n\(.content.raw)\n"'
```

**Why an independent pass is warranted.** Every one of the five points has a
same-day commit whose message *claims* to answer it:

| Review point (2026-09-18) | Commit claiming to address it |
|---|---|
| waiting on a complex structure is a bad idea | "Wait for note-viewer IO.readFile before switching part staves." |
| NV already coalesces resize, so `visualUpdateDepth` should go | "Drop visualUpdateDepth; NV already coalesces resize…" |
| what happens when the timesig changes mid-piece? | "Scale note-map times piecewise so a mid-score timesig does not stretch earlier notes." |
| race condition with the deferred load | "Keep the part dropdown closed until the deferred MIDI default load starts." |
| should `prepareMidiEtalon` be here too? | "Rebuild the MIDI etalon when switching parts so matching uses the visible staves" |

**A commit message claiming to address a point is not evidence that it does.**
That gap is the entire job: for each point, read the code as it is now and
decide whether it was actually addressed, partially addressed, or missed. The
human explicitly asked for "one way or another", which includes a legitimate
"rejected, and here is why".

**#70 is a stacked PR and it IS mergeable — into a branch, not into master.**
A pull request merges into its *destination*, whatever that happens to be, so
#70 can be approved and merged into `note-viewer-renderer-switch` as soon as
the points are addressed. Do not describe it as blocked. The stack is:

```
master <- #41 exercise-view (Anton)                    DRAFT
  <- #46 exercise-view-ai-temp-fb (Anton)        DRAFT
  <- #62 note-viewer-renderer-switch (Timo)       DRAFT
  <- #70 note-viewer-part-staff-switch (Timo)     LIVE — the human reviews this
```

The cost of the stack is coordination, not a hard block: merging onto a base
that is itself a draft means the work rides on a branch that keeps moving, and
the chain reaches `master` only from the top down. The human is aware the
process is suboptimal and is running with it for now — do not propose
unpicking the stack.

So the pass has a real action behind it: report the state of the five points so
the human can approve and merge. Anton Slavin has already approved #70; the
human has not.

Report per point: **addressed / partially / missed / rejected-with-reason**,
each with the file and line evidence, and say plainly if a point is ambiguous.
Do not post the findings to Bitbucket — hand them to the human.

## Tests

```
python3 -m unittest tools.bbprs.test.test_bbprs -v
```

Offline and fixture-based: the triage predicates are pure functions over a
participant record, so none of this needs the network. The fixtures in
`test/fixtures/` are shaped like real API responses and go through
`parse_pr`, the same mapping the live code uses — a test that hand-builds a
`PullRequest` would prove nothing about what Bitbucket actually sends. Each
fixture carries a `_comment` saying which case it pins and why.

