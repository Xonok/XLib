"""
Personal identifiers in tracked files, and the token list they are checked against.

The rule this implements is in `doc/personal-data.md`: a public repository for
public libraries and tools carries nothing that identifies the person who owns
it, the private projects they work on, the colleagues they work with, or the
machine they work on.

**The token list lives outside the repository**, in
`~/.config/xlib/personal-details.txt` — one literal per line, `#` for a
comment. A check that kept the forbidden strings in the repository would be the
leak it exists to prevent, so the list is per machine, untracked, and the
repository says only where to find it. The environment variable
`XPERSONAL_DETAILS` points it somewhere else.

A machine without the list has no protection from this check. That is a fact
the rule file states rather than hides.
"""

import os,re
from pathlib import Path

DEFAULT_TOKEN_FILE = "~/.config/xlib/personal-details.txt"
ENV_TOKEN_FILE = "XPERSONAL_DETAILS"

# Files under these prefixes are exempt while epiq `KK8RRNQ` is open. The
# per-person state files are the owner's work log *about private work* — an
# entry records which private repository's proxy discards a request, and it is
# worthless without it — so scrubbing them in place would gut forty-odd
# records to satisfy a rule. The exemption ends when that ticket is ruled on:
# the folder moves to the private Agents repository, or the records are
# scrubbed and the exemption goes with them.
EXEMPT_PREFIXES = ("personal/",)

# A word character for the boundary test: a letter, a digit, and the four
# characters that join a word into a longer name. A short token must not match
# inside a longer name that begins with it, and a path token must not match
# inside a longer path.
_WORD = r"\w./-"

def token_path() -> Path:
	"""Where the token list is: the environment override, else the default."""
	override = os.environ.get(ENV_TOKEN_FILE)
	return Path(os.path.expanduser(override if override else DEFAULT_TOKEN_FILE))

def load_tokens(path=None) -> list:
	"""The tokens, read from the list file. Empty when there is no list file.

	An absent list is not an error: a machine that has not set one up gets a
	quiet check rather than a crash in the middle of a commit.
	"""
	target = Path(path) if path else token_path()
	try:
		text = target.read_text(encoding="utf-8")
	except OSError:
		return []
	tokens = []
	for line in text.splitlines():
		value = line.strip()
		if value and not value.startswith("#"):
			tokens.append(value)
	return tokens

def _pattern(token: str):
	"""A regex matching the token as a whole word, whatever its case.

	The boundary is "not adjacent to a word character", so a token that is part
	of a longer name does not match: a short token does not fire inside a
	longer name that begins with it, and a token containing a space fires when
	its first word appears.
	"""
	return re.compile(r"(?<![" + _WORD + r"])" + re.escape(token) + r"(?![" + _WORD + r"])",
		re.IGNORECASE)

def is_exempt(path) -> bool:
	"""True when the file is under an exempt prefix, relative to the repository."""
	text = str(path)
	for prefix in EXEMPT_PREFIXES:
		if prefix in text or text.startswith(prefix.rstrip("/")):
			return True
	return False

def find(lines, tokens) -> list:
	"""The personal identifiers in `lines`, as (line number, token) pairs."""
	report = []
	for index, line in enumerate(lines, start=1):
		for token in tokens:
			if _pattern(token).search(line):
				report.append((index, token))
	return report

def check(lines, path) -> list:
	"""The personal identifiers in a tracked file, as xlint problems.

	Only tracked files: an untracked file is not published, and a draft is
	allowed to carry a value while it is being written.
	"""
	tokens = load_tokens()
	if not tokens:
		return []
	if is_exempt(path):
		return []
	return [(index, "personal identifier in a tracked file — this repository is public; "
		"keep the value out of it and say what it was")
		for index, _token in find(lines, tokens)]
