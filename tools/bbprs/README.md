# bbprs — read-only Bitbucket pull-request triage for agents

Triage open pull requests: what is waiting on you, and what of yours is going
stale. `bbprs.py` in this directory is the tool; this file is the briefing
that goes with it — how to configure it, the API shapes, and the traps that
each cost real time the first time somebody met them.

**The tool carries nothing about you.** The workspace, the repos and your
account are configuration, not constants, so the repository says nothing about
whose it is and the same checkout works for anybody with a Bitbucket account.

## Configuration

Three sources, and the first one that says something wins:

| Source | What it looks like |
|---|---|
| Command-line flag | `--workspace`, `--repo` (repeatable), `--account` |
| Environment | `BBPRS_WORKSPACE`, `BBPRS_REPOS` (comma-separated), `BBPRS_ACCOUNT` |
| File | `~/.config/bitbucket/bbprs.json` |

A value that none of them supplies is an error naming all three ways to supply
it. There is no default: a default here is one person's settings in a tool
that everybody else runs.

```json
{
	"workspace": "your-workspace",
	"repos": ["your-repo", "your-other-repo"],
	"account": "your-nickname"
}
```

**The account** is the nickname the API reports for you — which is not always
your display name — or its `uuid` or `account_id`. The two ids do not change
when a nickname does, so an account configured by its id keeps matching after a
rename. All three are read off any pull request you appear on:

```bash
curl -sS --netrc-file ~/.config/bitbucket/credentials -H 'Accept: application/json' \
  "$URL/pullrequests/1" | jq '.participants[].user | {nickname, uuid, account_id}'
```

The account is matched against the authors and the participants of every pull
request the tool fetches. When it matches nobody, the tool says so on stderr:
a mistyped account otherwise reads as "nothing is waiting on you", which is
the one answer that must never be wrong.

## Credentials

- **Path:** `~/.config/bitbucket/credentials`, mode `600`, netrc format.
- **Contents:** `machine api.bitbucket.org`, `login` = the Atlassian account
	email, `password` = the API token. `login` is the **email**, not the
	Bitbucket username.
- Use **`--netrc`**, never a bare `~/.netrc`: git reads `~/.netrc`
	automatically, so a token there can be silently used for pushes.
- The token is typed by its owner. **Never ask for it in chat, never print
	it, never `export` it, never put it in a repo or a notes file.** An
	exported secret leaks into every child process.
- Scopes needed: `read:repository:bitbucket` and `read:pullrequest:bitbucket`.
	Both are needed and **neither implies the other**. App passwords no longer
	exist in the UI; API tokens replaced them.
- `read:user:bitbucket` is **not** needed and not used. It would let the tool
	look up the authenticated account, but a token that only reads pull
	requests is a token that cannot do anything else, and asking for a third
	scope to learn the user's own name is a poor trade.

Creating the file, if it ever needs recreating:

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

## Usage

```
bbprs.py                      # triage the configured repos
bbprs.py --repo your-repo     # one repo
bbprs.py --mine               # only PRs you authored
bbprs.py --include-drafts     # colleagues' drafts too
bbprs.py --json               # machine-readable
bbprs.py --watch 300          # re-run every 5 minutes (for a tmux pane)
bbprs.py --check              # exit 1 if anything is blocked on you
```

`--check` exits 1 when a colleague's live pull request is waiting on your
review and 0 otherwise, so it can be a gate in a script.

## The relevance rule

**Only open PRs matter. Drafts matter only when they are your own.**
In the Bitbucket API a draft is `state: OPEN` *plus* a separate `draft: true`
field, so a plain `state=OPEN` query returns drafts too — and in one workspace
measured, 8 of the 16 pull requests it returned were drafts, three of the five
apparent "blockers" among them. Getting this wrong sends somebody to review
an unfinished draft.

## Endpoints

Base: `https://api.bitbucket.org/2.0/repositories/{workspace}/{repo}`

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

## The six traps

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
	reviewer has already answered report as `BLOCKED ON YOU` — the inverse of
	the truth, and a standing instruction to re-review a colleague's PR. Read
	`state`: `"changes_requested"` means the reviewer has done their part and
	the ball is with the author.

6. **`role` is `REVIEWER` only if explicitly added as a reviewer.** Anyone who
	interacts with a PR otherwise appears as `PARTICIPANT` — including the
	author, always. So a bare `PARTICIPANT` means *the reviewer commented on a
	PR they were never asked to review*, and they hold no approval right on it.
	Only a `REVIEWER` can be the blocker.

Traps 5 and 6 are the same class of mistake — a field read as the whole
truth — and they were found by `3EEXMRK`, whose fixtures are the tests in
`test/`.

## Read-only, and it stays that way

Perform GETs and nothing else. **Never post a comment, approve, decline,
merge or push with this token** — acting on a colleague's PR in your own name
is your decision, not an agent's. A tool that reads PRs is genuinely useful; a
tool that can merge is a hazard, and the token is scoped for reading in
practice.

## Tests

```
python3 dev/xtest/xtest.py tools/bbprs/test/test_bbprs.py
```

Offline and fixture-based: the triage predicates are pure functions over a
participant record, so none of this needs the network. The fixtures in
`test/fixtures/` are shaped like real API responses and go through
`parse_pr`, the same mapping the live code uses — a test that hand-built a
`PullRequest` would prove nothing about what Bitbucket actually sends. Each
fixture carries a `_comment` saying which case it pins and why.
