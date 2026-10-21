#!/usr/bin/env python3
"""
Tests for bbprs.py — the triage predicates and the configuration they read.

Run with: python3 dev/xtest/xtest.py tools/bbprs/test/test_bbprs.py

bbprs had no test suite until ticket 3EEXMRK: the acceptance criteria could
only be checked by hand against the live API, which is exactly the situation in
which a wrong-but-confident answer survives. Everything here is fixture-based
and offline — the tool's network layer is never reached, because the bug that
ticket fixes is in how a participant record is *read*, and that needs no
network to prove.

The fixtures are shaped like real Bitbucket responses and `parse_pr` does the
mapping, so a test that hand-built a PullRequest would prove nothing about
what the API actually sends. The account is configured by the tests rather
than baked into the tool, so the fixtures pin a shape and not a name.

The absent-state normalizer is insurance, not an observed bug. An earlier
version of the ticket that this suite came from claimed Bitbucket sends "no
state" as the *string* "null" and that reading it naively would leave --check
permanently 0. That was not checked before it was asserted: across 175 open
and merged PRs (scanned 2026-10-01), `state` is always JSON null and the
string never appears. The API documentation's own participant example does
show `"state": "null"` as a string, so the normalizer keeps handling it — two
lines, no cost, and a truthy "null" would silently mean "handled". What the
tests below pin is that the normalizer treats every spelling of absence
identically. They do not claim the string form occurs.
"""
import json,os,sys,tempfile
from dataclasses import replace
from pathlib import Path

# xtest and the tool under test are found relative to this file rather than to
# the working directory: a test that passes from one directory and fails from
# another is worse than one that never runs.
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "dev" / "xtest"))
sys.path.insert(0, str(REPO))

import xtest
from tools.bbprs import bbprs

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ACCOUNT = "the-account"
ACCOUNT_UUID = "{aaaaaaaa-1111-4111-8111-111111111111}"
ACCOUNT_ID = "557058:aaaaaaaa-1111-4111-8111-111111111111"
NO_CONFIG = "/nonexistent/bbprs.json"

def load(name: str, account: str = ACCOUNT) -> bbprs.PullRequest:
	"""Build a PR from a fixture, through the same parse the live tool uses."""
	full = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
	return bbprs.parse_pr("a-repo", full, account)

class _env:
	"""Set environment variables for the length of a block, and put them back."""

	def __init__(self, **values):
		self.values = values
		self.saved = {}

	def __enter__(self):
		for key, value in self.values.items():
			self.saved[key] = os.environ.get(key)
			if value is None:
				os.environ.pop(key, None)
			else:
				os.environ[key] = value
		return self

	def __exit__(self, *_exc):
		for key, value in self.saved.items():
			if value is None:
				os.environ.pop(key, None)
			else:
				os.environ[key] = value
		return False

class _config_file:
	"""A configuration file in a temporary directory, for the length of a block."""

	def __init__(self, data):
		self.data = data
		self.dir = None
		self.path = None

	def __enter__(self):
		self.dir = tempfile.TemporaryDirectory()
		self.path = os.path.join(self.dir.name, "bbprs.json")
		with open(self.path, "w", encoding="utf-8") as fh:
			json.dump(self.data, fh)
		return self.path

	def __exit__(self, *_exc):
		self.dir.cleanup()
		return False

def exit_message(fn) -> str:
	"""The message of the SystemExit a call raises, or a marker if it raised none."""
	try:
		fn()
	except SystemExit as exc:
		return str(exc)
	return "<no exit>"

def test_a_flag_beats_the_environment():
	with _env(BBPRS_WORKSPACE="from-env", BBPRS_ACCOUNT="from-env"):
		config = bbprs.resolve_config("from-flag", ["a-repo"], "an-account", NO_CONFIG)
	xtest.equal(config.workspace, "from-flag", "the flag wins over the environment")

def test_the_environment_is_used_when_no_flag_is_given():
	with _env(BBPRS_WORKSPACE="from-env", BBPRS_REPOS="a-repo,b-repo", BBPRS_ACCOUNT="an-account"):
		config = bbprs.resolve_config(None, [], None, NO_CONFIG)
	xtest.equal(config.workspace, "from-env", "the environment names the workspace")
	xtest.equal(config.repos, ["a-repo", "b-repo"], "the environment names the repos")
	xtest.equal(config.account, "an-account", "the environment names the account")

def test_the_configuration_file_is_used_when_nothing_else_says():
	data = {"workspace": "from-file", "repos": ["a-repo"], "account": "an-account"}
	with _config_file(data) as path, _env(BBPRS_WORKSPACE=None, BBPRS_REPOS=None, BBPRS_ACCOUNT=None):
		config = bbprs.resolve_config(None, [], None, path)
	xtest.equal(config.workspace, "from-file", "the file names the workspace")
	xtest.equal(config.repos, ["a-repo"], "the file names the repos")
	xtest.equal(config.account, "an-account", "the file names the account")

def test_the_environment_beats_the_configuration_file():
	data = {"workspace": "from-file", "repos": ["from-file"], "account": "from-file"}
	with _config_file(data) as path, _env(BBPRS_WORKSPACE="from-env", BBPRS_REPOS="from-env", BBPRS_ACCOUNT="from-env"):
		config = bbprs.resolve_config(None, [], None, path)
	xtest.equal(config.workspace, "from-env", "the environment wins over the file")
	xtest.equal(config.account, "from-env", "the environment wins over the file")

def test_the_repos_come_from_a_comma_separated_environment_variable():
	with _env(BBPRS_REPOS="a-repo, b-repo ,,c-repo"):
		config = bbprs.resolve_config("a-workspace", [], "an-account", NO_CONFIG)
	xtest.equal(config.repos, ["a-repo", "b-repo", "c-repo"], "the list is split and trimmed")

def test_a_repo_list_in_the_file_may_be_a_string():
	data = {"workspace": "a-workspace", "repos": "a-repo,b-repo", "account": "an-account"}
	with _config_file(data) as path, _env(BBPRS_REPOS=None):
		config = bbprs.resolve_config(None, [], None, path)
	xtest.equal(config.repos, ["a-repo", "b-repo"], "a string is split the same way")

def test_a_missing_workspace_is_an_error_naming_the_three_ways():
	with _env(BBPRS_WORKSPACE=None):
		message = exit_message(lambda: bbprs.resolve_config(None, ["a-repo"], "an-account", NO_CONFIG))
	xtest.contains("--workspace", message, "the flag is named")
	xtest.contains("BBPRS_WORKSPACE", message, "the environment variable is named")
	xtest.contains('"workspace" in', message, "the configuration file key is named")

def test_a_missing_repo_list_is_an_error_naming_the_three_ways():
	with _env(BBPRS_REPOS=None):
		message = exit_message(lambda: bbprs.resolve_config("a-workspace", [], "an-account", NO_CONFIG))
	xtest.contains("--repo", message, "the flag is named")
	xtest.contains("BBPRS_REPOS", message, "the environment variable is named")
	xtest.contains('"repos" in', message, "the configuration file key is named")

def test_a_missing_account_is_an_error_naming_the_three_ways():
	with _env(BBPRS_ACCOUNT=None):
		message = exit_message(lambda: bbprs.resolve_config("a-workspace", ["a-repo"], None, NO_CONFIG))
	xtest.contains("--account", message, "the flag is named")
	xtest.contains("BBPRS_ACCOUNT", message, "the environment variable is named")
	xtest.contains('"account" in', message, "the configuration file key is named")

def test_a_configuration_file_that_is_not_json_is_an_error():
	with tempfile.TemporaryDirectory() as directory:
		path = os.path.join(directory, "bbprs.json")
		with open(path, "w", encoding="utf-8") as fh:
			fh.write("{not json")
		message = exit_message(lambda: bbprs.resolve_config(None, [], None, path))
	xtest.contains("cannot be read as JSON", message, "the file is named as the problem")

def test_the_account_matches_a_participant_by_nickname():
	pr = load("reviewer_never_participated", "the-account")
	xtest.equal(pr.my_participation(), "REVIEWER/NOT approved", "the nickname finds the record")

def test_the_account_matches_a_participant_by_uuid():
	pr = load("reviewer_never_participated", ACCOUNT_UUID)
	xtest.equal(pr.my_participation(), "REVIEWER/NOT approved", "the uuid finds the record")

def test_the_account_matches_a_participant_by_account_id():
	pr = load("reviewer_never_participated", ACCOUNT_ID)
	xtest.equal(pr.my_participation(), "REVIEWER/NOT approved", "the account id finds the record")

def test_an_account_that_matches_nobody_is_not_involved():
	pr = load("reviewer_never_participated", "somebody-else")
	xtest.equal(pr.is_mine, False, "a stranger's PR is not yours")
	xtest.equal(pr.my_participation(), None, "and you are not in it")

def test_an_account_that_matched_nobody_is_reported():
	prs = [load("reviewer_never_participated")]
	xtest.equal(bbprs.account_seen(prs, ACCOUNT), True, "the account is in the data")
	xtest.equal(bbprs.account_seen(prs, "somebody-else"), False, "a stranger is not")

def test_the_report_says_which_workspace_and_account_it_ran_as():
	config = bbprs.Config(workspace="a-workspace", repos=["a-repo"], account="an-account")
	out = bbprs.render_report([], 0, config)
	xtest.contains("workspace: a-workspace", out, "the workspace is named")
	xtest.contains("account: an-account", out, "the account is named")

def test_changes_requested_reads_as_such_not_as_not_approved():
	# The regression case. The old code sent both of these down one branch,
	# so a PR the account had already reviewed by requesting changes claimed
	# it had not.
	xtest.equal(load("changes_requested").my_participation(), "REVIEWER/changes_requested")

def test_approved():
	xtest.equal(load("approved").my_participation(), "REVIEWER/approved")

def test_reviewer_never_participated():
	xtest.equal(load("reviewer_never_participated").my_participation(), "REVIEWER/NOT approved")

def test_participant_without_state():
	# A participant record carrying no `state` key at all.
	xtest.equal(load("participant").my_participation(), "PARTICIPANT/NOT approved")

def test_absent_from_pr():
	xtest.equal(load("human_absent").my_participation(), None)

def test_changes_requested_does_not_block():
	xtest.equal(load("changes_requested").blocks_the_human(), False)

def test_approved_does_not_block():
	xtest.equal(load("approved").blocks_the_human(), False)

def test_untouched_reviewer_blocks():
	xtest.equal(load("reviewer_never_participated").blocks_the_human(), True)

def test_participant_does_not_block():
	# Commenting on a PR you were never added to review is not blocking it.
	# A PARTICIPANT has no approval right, so there is no action of yours
	# that could clear the flag.
	xtest.equal(load("participant").blocks_the_human(), False)

def test_commented_but_never_a_reviewer_does_not_block():
	# The real case: a PR reported BLOCKED ON YOU for the two and a half
	# weeks it was open. Two other reviewers had approved; the account had
	# only commented.
	pr = load("commented_not_reviewer")
	xtest.equal(pr.my_participation(), "PARTICIPANT/NOT approved")
	xtest.equal(pr.blocks_the_human(), False)
	xtest.not_equal("BLOCKED ON YOU" in pr.flags(), True)

def test_reviewer_who_also_commented_still_blocks():
	# The role check must key on the *current* role, not on ever having
	# commented: an untouched REVIEWER is still a blocker.
	xtest.equal(load("reviewer_never_participated").blocks_the_human(), True)

def test_absent_does_not_block():
	xtest.equal(load("human_absent").blocks_the_human(), False)

def test_colleague_draft_does_not_block():
	# An unfinished PR is not a colleague waiting on a review.
	xtest.equal(load("colleague_draft").blocks_the_human(), False)

def test_own_pr_never_blocks():
	# Your own PR, as an untouched reviewer of it.
	own = replace(load("reviewer_never_participated"), author=bbprs.User(nickname=ACCOUNT))
	xtest.equal(own.blocks_the_human(), False)

def test_a_string_null_normalizes_to_absent():
	xtest.equal(bbprs._review_state({"role": "REVIEWER", "approved": False, "state": "null"}), "")

def test_a_json_null_normalizes_to_absent():
	xtest.equal(bbprs._review_state({"approved": False, "state": None}), "")

def test_a_missing_key_normalizes_to_absent():
	xtest.equal(bbprs._review_state({"approved": False}), "")

def test_a_real_state_survives():
	xtest.equal(bbprs._review_state({"approved": False, "state": "changes_requested"}), "changes_requested")

def test_a_string_null_does_not_register_as_a_review():
	# A truthy "null" must not read as "the account has acted", or an
	# untouched reviewer would never be reported.
	pr = load("reviewer_never_participated")
	xtest.not_equal(bbprs._review_state(pr._my_record()), "changes_requested")
	xtest.equal(pr.blocks_the_human(), True)

def test_check_exits_zero_when_only_changes_requested():
	prs = bbprs.relevant([load("changes_requested")], False, False)
	xtest.equal(any(p.blocks_the_human() for p in prs), False)

def test_check_exits_one_when_a_reviewer_is_untouched():
	prs = bbprs.relevant([load("reviewer_never_participated")], False, False)
	xtest.equal(any(p.blocks_the_human() for p in prs), True)

def test_check_exits_one_when_changes_requested_rides_alongside_a_real_blocker():
	# The fix must not turn --check into a permanent 0: one genuine blocker
	# in the set still has to reach the reviewer.
	prs = bbprs.relevant([load("changes_requested"), load("reviewer_never_participated")], False, False)
	xtest.equal(any(p.blocks_the_human() for p in prs), True)

def test_check_exits_zero_when_nothing_is_waiting():
	prs = bbprs.relevant([load("approved"), load("human_absent"), load("colleague_draft")], False, False)
	xtest.equal(any(p.blocks_the_human() for p in prs), False)

def test_changes_requested_is_not_flagged_blocked():
	xtest.not_equal("BLOCKED ON YOU" in load("changes_requested").flags(), True)

def test_untouched_reviewer_is_flagged_blocked():
	xtest.equal("BLOCKED ON YOU" in load("reviewer_never_participated").flags(), True)

def test_json_reports_the_state_for_the_regression_case():
	# The acceptance criterion, in the shape a consumer reads it.
	record = load("changes_requested").as_dict()
	xtest.equal(record["my_participation"], "REVIEWER/changes_requested")
	xtest.equal(record["blocks_the_human"], False)
	xtest.not_equal("BLOCKED ON YOU" in record["flags"], True)

def test_json_carries_the_author_as_a_nickname():
	# The JSON has always carried the author as a nickname; the account
	# object behind it must not change that shape.
	record = load("changes_requested").as_dict()
	xtest.equal(record["author"], "the-author")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
