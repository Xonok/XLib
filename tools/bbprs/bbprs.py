#!/usr/bin/env python3
"""
bbprs — read-only Bitbucket Cloud pull-request triage.

Answers the question a reviewer actually has: *which open pull requests are
waiting on me, and which of mine are going stale?*

READ-ONLY BY CONSTRUCTION. This tool performs GET requests and nothing else. It
has no code path that posts a comment, approves, declines, merges or pushes,
and it must not grow one — the API token it reads is scoped for reading, and
acting on a colleague's PR in your own name is a decision only you can make.

The relevance rule: **only open PRs matter. Drafts matter only when they are
your own.** In the Bitbucket API a draft is `state: OPEN` plus a separate
`draft: true` field, so a plain `state=OPEN` query returns drafts too. This
tool filters on `.draft` client-side. There is no `&draft=true` query
parameter — it returns HTTP 400.

Credentials: `--netrc ~/.config/bitbucket/credentials` (mode 600, netrc
format, login = Atlassian account email, password = API token). `--netrc`
rather than a bare `~/.netrc` on purpose: git reads `~/.netrc` automatically,
so a token there could be silently used for pushes. The token is never
printed, never logged, and never passed on a command line.

Configuration — this tool carries nothing about who you are or what you work
on. Three sources, and the first one that says something wins:

	--workspace / --repo / --account              command-line flags
	BBPRS_WORKSPACE / BBPRS_REPOS / BBPRS_ACCOUNT    environment
	~/.config/bitbucket/bbprs.json                  {"workspace": ..., "repos": [...], "account": ...}

A value you did not supply is an error naming all three ways to supply it.
There is no built-in default, because a built-in default is one person's
settings in a tool that everybody else runs.

Usage:
	bbprs.py                      # triage the configured repos
	bbprs.py --repo my-repo        # one repo
	bbprs.py --mine                # only PRs you authored
	bbprs.py --json                # machine-readable
	bbprs.py --watch 300           # re-run every 5 minutes (for a tmux pane)
	bbprs.py --check               # exit 1 if anything is blocked on you
"""

from __future__ import annotations
import argparse,base64,json,os,sys,time,urllib.error,urllib.request
from dataclasses import dataclass,field
from datetime import datetime,timezone

API = "https://api.bitbucket.org/2.0"
DEFAULT_NETRC = os.path.expanduser("~/.config/bitbucket/credentials")
DEFAULT_CONFIG = os.path.expanduser("~/.config/bitbucket/bbprs.json")

# The environment variables that carry the configuration, so a user who would
# rather not keep a file can set them once in their shell.
ENV_WORKSPACE = "BBPRS_WORKSPACE"
ENV_REPOS = "BBPRS_REPOS"
ENV_ACCOUNT = "BBPRS_ACCOUNT"

# A live PR with no activity for this long is called out as stale. Chosen to be
# roughly "long enough that a colleague would have noticed it is not moving".
STALE_DAYS = 14

# A PR of your own that is older than this is called out as neglected
# regardless of whether anyone else is reviewing it.
NEGLECTED_DAYS = 30

# What each failure status means, so the message says something actionable.
# Kept as globals so no call site needs an aligned string continuation.
HINTS = {
	400: "a bad request parameter — note Bitbucket rejects pagelen>50",
	401: "bad or expired token",
	403: "token lacks read:pullrequest:bitbucket, which does not imply read:repository:bitbucket — request both",
}

def _parse_netrc(path: str) -> tuple[str, str]:
	"""
	Read `machine`/`login`/`password` out of a netrc-format file.

	Deliberately hand-parsed rather than using netrc.netrc: that module walks
	$HOME and would pick up a ~/.netrc that git also uses. This tool only ever
	looks at the exact path it was given.
	"""
	machine = login = password = None
	current = None
	with open(path, encoding="utf-8") as fh:
		for raw in fh:
			line = raw.strip()
			if not line or line.startswith("#"):
				continue
			parts = line.split(None, 1)
			if len(parts) != 2:
				continue
			key, value = parts[0], parts[1].strip()
			if key == "machine":
				current = value
			elif key == "default":
				current = current or value
			elif current == f"api.bitbucket.org":
				if key == "login":
					login = value
				elif key == "password":
					password = value
	if not login or not password:
		raise SystemExit(
			f"{path}: no login/password for machine api.bitbucket.org.\n"
			"Expected netrc format:\n"
			"  machine api.bitbucket.org\n"
			"    login you@example.com\n"
			"    password <token>"
		)
	return login, password

def _review_state(record: dict) -> str:
	"""
	The reviewer's state, normalized: '' when they have not acted yet.

	The API documentation's own participant example shows `"state": "null"` as
	a *string*, and that string is truthy. A truthy "null" would read as "the
	account has acted" and no PR would ever be reported, so the spelling of
	absence is normalized away rather than compared against.

	Live data (175 open and merged PRs across two repos, scanned 2026-10-01)
	always sends JSON null, so this is insurance rather than a fix for
	something observed.
	"""
	state = record.get("state")
	return "" if state is None or state == "null" else state

@dataclass(frozen=True)
class User:
	"""
	One Bitbucket account as the API reports it.

	Three identifiers, and each is here for a reason: `nickname` is what a
	human reads and what a pull request shows, `uuid` and `account_id` are
	what the API guarantees. A nickname can be changed and the ids cannot, so
	an account configured by its id keeps matching after a rename.
	"""
	nickname: str
	uuid: str = ""
	account_id: str = ""
	def matches(self, account: str) -> bool:
		"""True when `account` names this user, by any of its three identifiers."""
		return bool(account) and account in (self.nickname, self.uuid, self.account_id)

def _user(raw: dict | None) -> User:
	"""Read a user object out of an API response."""
	raw = raw or {}
	return User(
		nickname=raw.get("nickname") or "",
		uuid=raw.get("uuid") or "",
		account_id=raw.get("account_id") or "",
	)

@dataclass
class Config:
	"""What to triage, and as whom."""
	workspace: str
	repos: list[str]
	account: str

def _read_config_file(path: str) -> dict:
	"""
	Read the configuration file.

	A missing file is not an error — the values can come from a flag or the
	environment instead — but a file that is there and cannot be read is,
	because that is where the user put their settings.
	"""
	if not os.path.exists(path):
		return {}
	try:
		with open(path, encoding="utf-8") as fh:
			data = json.load(fh)
	except (OSError, ValueError) as exc:
		raise SystemExit(f"{path}: cannot be read as JSON ({exc})")
	if not isinstance(data, dict):
		raise SystemExit(f"{path}: expected a JSON object with workspace, repos and account")
	return data

def _repo_list(value) -> list[str]:
	"""A repo list, whether it arrives as a list or as a comma-separated string."""
	if isinstance(value, str):
		value = value.split(",")
	return [str(part).strip() for part in value if str(part).strip()]

def _missing(what: str, flag: str, env: str, key: str, path: str) -> str:
	"""
	The message for a value the user did not supply.

	It names all three ways to supply it, because a tool that only says "no
	workspace" is a tool the user has to guess about.
	"""
	return (
		f"no {what} configured.\n"
		f"Set it in one of three ways:\n"
		f"  {flag} <value>\n"
		f"  {env}=<value>\n"
		f'  "{key}" in {path}'
	)

def _missing_repos(path: str) -> str:
	"""The message for a missing repo list, whose environment form is a list."""
	return (
		"no repos configured.\n"
		"Set them in one of three ways:\n"
		"  --repo <slug> (repeatable)\n"
		"  BBPRS_REPOS=<slug>,<slug>\n"
		f'  "repos" in {path}'
	)

def resolve_config(workspace: str | None, repos: list[str], account: str | None, config_path: str) -> Config:
	"""
	Decide what to triage.

	A flag beats the environment, and the environment beats the configuration
	file. Nothing is defaulted: a value the user did not supply is an error,
	because a default here would be one person's settings in a tool that
	everybody else runs.
	"""
	file_config = _read_config_file(config_path)
	workspace = workspace or os.environ.get(ENV_WORKSPACE) or file_config.get("workspace")
	if not workspace:
		raise SystemExit(_missing("workspace", "--workspace", ENV_WORKSPACE, "workspace", config_path))
	repos = _repo_list(repos) if repos else _repo_list(os.environ.get(ENV_REPOS, "") or file_config.get("repos") or [])
	if not repos:
		raise SystemExit(_missing_repos(config_path))
	account = account or os.environ.get(ENV_ACCOUNT) or file_config.get("account")
	if not account:
		raise SystemExit(_missing("account", "--account", ENV_ACCOUNT, "account", config_path))
	return Config(workspace=str(workspace), repos=repos, account=str(account))

@dataclass
class PullRequest:
	repo: str
	id: int
	title: str
	author: User
	source: str
	destination: str
	draft: bool
	created: datetime
	updated: datetime
	state: str
	participants: list[dict] = field(default_factory=list)
	comment_count: int = 0
	# The account this pull request is judged against — the user running the
	# tool. Carried on the object rather than read from a module global, so
	# that no report can be about somebody else's pull requests, and so that
	# a test can say who it is talking about.
	account: str = ""
	@property
	def age_days(self) -> int:
		return (datetime.now(timezone.utc) - self.created).days
	@property
	def idle_days(self) -> int:
		return (datetime.now(timezone.utc) - self.updated).days
	@property
	def is_mine(self) -> bool:
		return self.author.matches(self.account)
	@property
	def stacked(self) -> bool:
		"""
		True when this PR merges into another branch rather than master.
		A stacked PR is NOT blocked: it merges into its destination branch.
		Only the top of a stack reaches master, and that arrives top-down.
		"""
		return self.destination != "master"
	@property
	def approvals(self) -> int:
		return sum(1 for p in self.participants if p.get("approved"))
	@property
	def reviewers(self) -> list[str]:
		return [
			_user(p.get("user")).nickname
			for p in self.participants
			if p.get("role") == "REVIEWER"
		]
	def _my_record(self) -> dict | None:
		"""The account's own entry in `participants`, or None if not involved."""
		for p in self.participants:
			if _user(p.get("user")).matches(self.account):
				return p
		return None
	def my_participation(self) -> str | None:
		"""
		How the account appears on this PR, or None if not involved.

		`state` is what separates the two not-approved cases: Bitbucket sends
		`approved: false` both for a reviewer who requested changes and for one
		who never looked at the PR, and only `state` tells them apart.
		"""
		record = self._my_record()
		if record is None:
			return None
		role = record.get("role", "?")
		if record.get("approved"):
			return f"{role}/approved"
		return f"{role}/{_review_state(record) or 'NOT approved'}"
	def blocks_the_human(self) -> bool:
		"""
		True when this is someone else's live PR and the account is a
		*reviewer* who has neither approved it nor asked for changes. This is
		the 'I might be blocking them' case.

		Decided from the participant data, never by reading back the rendered
		`my_participation` string: requesting changes *completes* the review
		obligation and hands the ball to the author, so reporting it as
		blocked sends the reviewer to a PR that is not waiting on them.

		`role` must be REVIEWER. Bitbucket records anyone who interacts with a
		PR as a PARTICIPANT, so commenting on a colleague's PR you were never
		added to review yields PARTICIPANT with approved:false — and a
		PARTICIPANT holds no approval right, so there is no action of the
		reviewer's that could ever clear the flag.
		"""
		if self.is_mine or self.draft:
			return False
		record = self._my_record()
		if record is None or record.get("role") != "REVIEWER":
			return False
		return not (record.get("approved") or _review_state(record) == "changes_requested")
	def flags(self) -> list[str]:
		out = []
		if self.blocks_the_human():
			out.append("BLOCKED ON YOU")
		if self.is_mine and self.approvals == 0 and self.age_days >= NEGLECTED_DAYS:
			out.append(f"NEGLECTED: {self.age_days}d, no approvals")
		if not self.participants:
			out.append("NO REVIEWERS ASSIGNED")
		if self.idle_days >= STALE_DAYS:
			out.append(f"STALE: no activity {self.idle_days}d")
		return out
	def as_dict(self) -> dict:
		"""
		Full record for --json, computed fields included.
		`self.__dict__` alone is not enough: it holds only instance
		attributes, so every @property (stacked, blocks_the_human, age_days…)
		would serialise as missing. The author is flattened to its nickname,
		which is the shape the JSON has always carried.
		"""
		return {
			**{k: v for k, v in self.__dict__.items() if k != "author"},
			"author": self.author.nickname,
			"age_days": self.age_days,
			"idle_days": self.idle_days,
			"is_mine": self.is_mine,
			"stacked": self.stacked,
			"approvals": self.approvals,
			"reviewers": self.reviewers,
			"blocks_the_human": self.blocks_the_human(),
			"my_participation": self.my_participation(),
			"flags": self.flags(),
		}

class Bitbucket:
	def __init__(self, netrc: str, timeout: int = 30) -> None:
		login, password = _parse_netrc(netrc)
		# Built in memory only. Never appears in argv, so it cannot leak via
		# `ps` the way a `--user name:token` argument would.
		creds = f"{login}:{password}".encode()
		self._auth = "Basic " + base64.b64encode(creds).decode()
		self._timeout = timeout
		del creds, password
	def _get(self, url: str) -> dict:
		req = urllib.request.Request(
			url,
			headers={
				"Authorization": self._auth,
				"Accept": "application/json",
				"User-Agent": "bbprs/1.0 (read-only triage)",
			},
		)
		try:
			with urllib.request.urlopen(req, timeout=self._timeout) as resp:
				return json.loads(resp.read().decode())
		except urllib.error.HTTPError as exc:
			# Never echo the request headers back — they carry the token.
			try:
				detail = json.loads(exc.read().decode()).get("error", {}).get("message", "")
			except Exception: # noqa: BLE001 - body may be absent or non-JSON
				detail = ""
			hint = HINTS.get(exc.code, "")
			msg = f"HTTP {exc.code} from Bitbucket for {url}"
			if detail:
				msg += f"\n  Bitbucket says: {detail}"
			if hint:
				msg += f"\n  {hint}"
			raise SystemExit(msg) from None
		except urllib.error.URLError as exc:
			raise SystemExit(f"network error talking to Bitbucket: {exc.reason}") from None
	def open_prs(self, repo: str, workspace: str, account: str) -> list[PullRequest]:
		"""
		List open PRs, then fetch each one individually for its participants.
		The list endpoint omits `participants` entirely — it is simply absent
		from every item, not empty. Trusting it makes every PR look
		unassigned and, worse, makes `blocks_the_human()` always false, so the
		tool cheerfully reports that nothing is waiting on you. The extra N
		requests are the price of an answer that is not silently wrong.
		Verified against the live API on 2026-09-28.
		"""
		out: list[PullRequest] = []
		url = f"{API}/repositories/{workspace}/{repo}/pullrequests?state=OPEN&pagelen=50"
		while url:
			page = self._get(url)
			for stub in page.get("values", []):
				full = self._get(f"{API}/repositories/{workspace}/{repo}/pullrequests/{stub['id']}")
				out.append(parse_pr(repo, full, account))
			url = page.get("next")
		return out

def parse_pr(repo: str, full: dict, account: str = "") -> PullRequest:
	"""
	Build a PullRequest from one API object.

	Its own function, not inline in open_prs, so the test harness can drive
	the same mapping the live code does. A test that hand-builds a PullRequest
	proves nothing about what the API actually yields.
	"""
	return PullRequest(
		repo=repo,
		id=full["id"],
		title=full["title"],
		author=_user(full["author"]),
		source=full["source"]["branch"]["name"],
		destination=full["destination"]["branch"]["name"],
		draft=bool(full.get("draft")),
		created=datetime.fromisoformat(full["created_on"]),
		updated=datetime.fromisoformat(full["updated_on"]),
		state=full["state"],
		participants=full.get("participants") or [],
		comment_count=full.get("comment_count", 0),
		account=account,
	)

def relevant(prs: list[PullRequest], include_drafts: bool, mine_only: bool) -> list[PullRequest]:
	"""Apply the relevance rule: open PRs, and drafts only if your own."""
	kept: list[PullRequest] = []
	for pr in prs:
		if pr.draft and not pr.is_mine and not include_drafts:
			continue
		if mine_only and not pr.is_mine:
			continue
		kept.append(pr)
	return sorted(kept, key=lambda pr: (not pr.is_mine, pr.age_days))

def account_seen(prs: list[PullRequest], account: str) -> bool:
	"""
	True when the account appears among the authors and participants of the
	fetched pull requests.

	A configured account that matches nobody is usually a typo, and a typo is
	silent: `--mine` finds nothing and `--check` exits 0, which reads as
	"nothing is waiting on you" — the one answer that must never be wrong.
	"""
	for pr in prs:
		if pr.author.matches(account):
			return True
		for p in pr.participants:
			if _user(p.get("user")).matches(account):
				return True
	return False

def render_report(prs: list[PullRequest], drafts_hidden: int, config: Config) -> str:
	lines = []
	stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
	lines.append(
		f"Bitbucket PR triage — {stamp}  (workspace: {config.workspace}, "
		f"repos: {', '.join(config.repos)}, account: {config.account})"
	)
	if drafts_hidden:
		lines.append(f"{drafts_hidden} draft(s) hidden — open PRs only, per the relevance rule")
	lines.append("")

	if not prs:
		lines.append("Nothing to show.")
		return "\n".join(lines)

	blocked = [p for p in prs if p.blocks_the_human()]
	if blocked:
		lines.append(f"BLOCKED ON YOU ({len(blocked)}) — colleagues waiting")
		for pr in sorted(blocked, key=lambda p: p.age_days, reverse=True):
			lines.append(
				f"  #{pr.id:<4} {pr.title[:40]:<40} {pr.author.nickname:<14} "
				f"{pr.age_days:>3}d old, {pr.approvals}/{len(pr.participants)} approved"
				+ (f"  [stacked: merges into {pr.destination}]" if pr.stacked else "")
			)
		lines.append("")

	mine = [p for p in prs if p.is_mine]
	if mine:
		lines.append(f"YOUR PRS ({len(mine)})")
		for pr in sorted(mine, key=lambda p: p.age_days, reverse=True):
			note = "no approvals" if pr.approvals == 0 else f"{pr.approvals} approved"
			lines.append(
				f"  #{pr.id:<4} {pr.title[:40]:<40} {pr.age_days:>3}d old, {note}, idle {pr.idle_days}d"
				+ (f"  [stacked: merges into {pr.destination}]" if pr.stacked else "")
			)
		lines.append("")

	others = [p for p in prs if not p.is_mine and not p.blocks_the_human()]
	if others:
		lines.append(f"OTHERS' LIVE PRS, not waiting on you ({len(others)})")
		for pr in sorted(others, key=lambda p: p.age_days, reverse=True):
			lines.append(
				f"  #{pr.id:<4} {pr.title[:40]:<40} {pr.author.nickname:<14} {pr.age_days:>3}d old"
				+ (f"  [stacked: merges into {pr.destination}]" if pr.stacked else "")
			)
		lines.append("")

	flagged = [(p, f) for p in prs for f in p.flags()]
	if flagged:
		lines.append("FLAGS")
		for pr, flag in flagged:
			lines.append(f"  #{pr.id:<4} {pr.source[:32]:<32} {flag}")
		lines.append("")

	lines.append("read-only: nothing was posted, approved or merged.")
	return "\n".join(lines)

def main() -> int:
	ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
	ap.add_argument("--netrc", default=DEFAULT_NETRC, help="credentials file (default: %(default)s)")
	ap.add_argument("--config", default=DEFAULT_CONFIG, help="configuration file (default: %(default)s)")
	ap.add_argument("--workspace", help="Bitbucket workspace slug")
	ap.add_argument("--repo", action="append", dest="repos", help="repo slug; repeatable")
	ap.add_argument("--account", help="your Bitbucket nickname, uuid or account id")
	ap.add_argument("--mine", action="store_true", help="only PRs you authored")
	ap.add_argument("--include-drafts", action="store_true", help="show colleagues' drafts too")
	ap.add_argument("--json", action="store_true", help="machine-readable output")
	ap.add_argument("--watch", type=int, metavar="SECONDS", help="re-run every N seconds")
	ap.add_argument("--check", action="store_true", help="exit 1 if anything is blocked on you")
	args = ap.parse_args()

	config = resolve_config(args.workspace, args.repos, args.account, args.config)

	if not os.path.exists(args.netrc):
		raise SystemExit(
			f"no credentials at {args.netrc}\n"
			"Create it (the token is never echoed or logged):\n"
			"  mkdir -p ~/.config/bitbucket && chmod 700 ~/.config/bitbucket\n"
			"  read -r -s -p 'Bitbucket API token: ' TOKEN; echo\n"
			"  read -r -p 'Atlassian account email: ' EMAIL\n"
			"  umask 077\n"
			"  printf 'machine api.bitbucket.org\\n  login %s\\n  password %s\\n' \"$EMAIL\" \"$TOKEN\" \\\n"
			"    > ~/.config/bitbucket/credentials\n"
			"  chmod 600 ~/.config/bitbucket/credentials; unset TOKEN"
		)

	bb = Bitbucket(args.netrc)

	def once() -> tuple[list[PullRequest], int]:
		all_prs: list[PullRequest] = []
		for repo in config.repos:
			all_prs.extend(bb.open_prs(repo, config.workspace, config.account))
		hidden = sum(1 for p in all_prs if p.draft and not p.is_mine and not args.include_drafts)
		if all_prs and not account_seen(all_prs, config.account):
			print(
				f"warning: account {config.account!r} matched no author or participant in "
				f"{', '.join(config.repos)} — check the spelling",
				file=sys.stderr,
			)
		return relevant(all_prs, args.include_drafts, args.mine), hidden

	def emit(prs: list[PullRequest], hidden: int) -> None:
		if args.json:
			print(json.dumps([p.as_dict() for p in prs], indent=2, default=str))
		else:
			if args.watch:
				sys.stdout.write("\033[2J\033[H")
			print(render_report(prs, hidden, config))

	if args.watch:
		while True:
			prs, hidden = once()
			emit(prs, hidden)
			sys.stdout.flush()
			time.sleep(max(30, args.watch))
	else:
		prs, hidden = once()
		emit(prs, hidden)
		if args.check:
			return 1 if any(p.blocks_the_human() for p in prs) else 0
	return 0

if __name__ == "__main__":
	raise SystemExit(main())
