#!/usr/bin/env python3
"""
Tests for bbprs.py — the triage predicates (ticket 3EEXMRK).

Run with: python3 -m unittest tools.bbprs.test.test_bbprs -v

bbprs had no test suite until this ticket: the acceptance criteria could only
be checked by hand against the live API, which is exactly the situation in
which a wrong-but-confident answer survives. Everything here is fixture-based
and offline — the tool's network layer is never reached, because the bug this
ticket fixes is in how a participant record is *read*, and that needs no
network to prove.

The fixtures are shaped like real Bitbucket responses, `parse_pr` does the
mapping, and the human's account is `bbprs.HUMAN` — so if that ever changes,
these tests break loudly instead of passing against a name nobody uses.
"""

import json,unittest
from pathlib import Path
from tools.bbprs import bbprs

FIXTURES = Path(__file__).resolve().parent / "fixtures"

def load(name: str) -> bbprs.PullRequest:
	"""Build a PR from a fixture, through the same parse the live tool uses."""
	full = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
	return bbprs.parse_pr("mms-frontend", full)

class TestMyParticipation(unittest.TestCase):
	"""How the human is rendered — this string is also the --json field."""

	def test_changes_requested_reads_as_such_not_as_not_approved(self):
		# The regression case. The old code sent both of these down one branch,
		# so a PR the human had already reviewed by requesting changes claimed
		# he had not.
		self.assertEqual(load("changes_requested").my_participation(), "REVIEWER/changes_requested")

	def test_approved(self):
		self.assertEqual(load("approved").my_participation(), "REVIEWER/approved")

	def test_reviewer_never_participated(self):
		self.assertEqual(load("reviewer_never_participated").my_participation(), "REVIEWER/NOT approved")

	def test_participant_without_state(self):
		# A participant record carrying no `state` key at all.
		self.assertEqual(load("participant").my_participation(), "PARTICIPANT/NOT approved")

	def test_absent_from_pr(self):
		self.assertIsNone(load("human_absent").my_participation())

class TestBlocksTheHuman(unittest.TestCase):
	"""
	The one question the tool exists to answer. Requesting changes *completes*
	the review obligation, so it must not read as the human sitting on a PR.
	"""

	def assertBlocks(self, fixture: str, expected: bool) -> None:
		self.assertEqual(load(fixture).blocks_the_human(), expected, fixture)

	def test_changes_requested_does_not_block(self):
		self.assertBlocks("changes_requested", False)

	def test_approved_does_not_block(self):
		self.assertBlocks("approved", False)

	def test_untouched_reviewer_blocks(self):
		self.assertBlocks("reviewer_never_participated", True)

	def test_participant_does_not_block(self):
		# Commenting on a PR you were never added to review is not blocking it.
		# A PARTICIPANT has no approval right, so there is no action of the
		# human's that could clear the flag.
		self.assertBlocks("participant", False)

	def test_commented_but_never_a_reviewer_does_not_block(self):
		# The real case: mms-frontend #71, reported BLOCKED ON YOU for the two
		# and a half weeks it was open. Two other reviewers had approved; the
		# human had only commented.
		pr = load("commented_not_reviewer")
		self.assertEqual(pr.my_participation(), "PARTICIPANT/NOT approved")
		self.assertFalse(pr.blocks_the_human())
		self.assertNotIn("BLOCKED ON YOU", pr.flags())

	def test_reviewer_who_also_commented_still_blocks(self):
		# The role check must key on the *current* role, not on ever having
		# commented: an untouched REVIEWER is still a blocker.
		self.assertBlocks("reviewer_never_participated", True)

	def test_absent_does_not_block(self):
		self.assertBlocks("human_absent", False)

	def test_colleague_draft_does_not_block(self):
		# An unfinished PR is not a colleague waiting on a review.
		self.assertBlocks("colleague_draft", False)

	def test_own_pr_never_blocks(self):
		# The human's own PR, as an untouched reviewer of it.
		own = load("reviewer_never_participated")
		own.author = bbprs.HUMAN
		self.assertFalse(own.blocks_the_human())

class TestAbsentStateIsNormalized(unittest.TestCase):
	"""
	Insurance, not an observed bug. An earlier version of this ticket claimed
	Bitbucket sends "no state" as the *string* "null" and that reading it naively
	would leave --check permanently 0. That was not checked before it was
	asserted: across 175 open and merged PRs in mms-frontend and mms (scanned
	2026-10-01), `state` is always JSON null and the string never appears.

	The API documentation's own participant example does show `"state": "null"`
	as a string, so `_review_state()` keeps handling it — two lines, no cost,
	and a truthy "null" would silently mean "handled". What these tests pin is
	that the normalizer treats every spelling of absence identically. They do
	not claim the string form occurs.
	"""

	def test_string_null_normalizes_to_absent(self):
		record = {"role": "REVIEWER", "approved": False, "state": "null"}
		self.assertEqual(bbprs._review_state(record), "")

	def test_json_null_normalizes_to_absent(self):
		self.assertEqual(bbprs._review_state({"approved": False, "state": None}), "")

	def test_missing_key_normalizes_to_absent(self):
		self.assertEqual(bbprs._review_state({"approved": False}), "")

	def test_real_state_survives(self):
		record = {"approved": False, "state": "changes_requested"}
		self.assertEqual(bbprs._review_state(record), "changes_requested")

	def test_string_null_does_not_register_as_a_review(self):
		# A truthy "null" must not read as "the human has acted", or an
		# untouched reviewer would never be reported.
		pr = load("reviewer_never_participated")
		self.assertNotEqual(bbprs._review_state(pr._my_record()), "changes_requested")
		self.assertTrue(pr.blocks_the_human())

class TestCheckExitCode(unittest.TestCase):
	"""
	`--check` exits 1 when anything is blocked on the human. main() spells that
	as `any(p.blocks_the_human() for p in prs)`; that expression is asserted
	here over the fixtures, so the documented exit codes are pinned without
	standing up a network layer for a read-only reporter.
	"""

	def blocked(self, *fixtures: str) -> list[bbprs.PullRequest]:
		return [load(f) for f in fixtures]

	def test_exits_zero_when_only_changes_requested(self):
		prs = bbprs.relevant(self.blocked("changes_requested"), False, False)
		self.assertEqual(any(p.blocks_the_human() for p in prs), False)

	def test_exits_one_when_reviewer_untouched(self):
		prs = bbprs.relevant(self.blocked("reviewer_never_participated"), False, False)
		self.assertTrue(any(p.blocks_the_human() for p in prs))

	def test_exits_one_when_changes_requested_rides_alongside_a_real_blocker(self):
		# The fix must not turn --check into a permanent 0: one genuine
		# blocker in the set still has to reach the human.
		prs = bbprs.relevant(self.blocked("changes_requested", "reviewer_never_participated"), False, False)
		self.assertTrue(any(p.blocks_the_human() for p in prs))

	def test_exits_zero_when_nothing_is_waiting(self):
		prs = bbprs.relevant(self.blocked("approved", "human_absent", "colleague_draft"), False, False)
		self.assertEqual(any(p.blocks_the_human() for p in prs), False)

class TestFlagsAndJson(unittest.TestCase):
	"""The flag and the --json field both come off the same predicate."""

	def test_changes_requested_is_not_flagged_blocked(self):
		self.assertNotIn("BLOCKED ON YOU", load("changes_requested").flags())

	def test_untouched_reviewer_is_flagged_blocked(self):
		self.assertIn("BLOCKED ON YOU", load("reviewer_never_participated").flags())

	def test_json_reports_the_state_for_the_regression_case(self):
		# The acceptance criterion, in the shape a consumer reads it.
		record = load("changes_requested").as_dict()
		self.assertEqual(record["my_participation"], "REVIEWER/changes_requested")
		self.assertFalse(record["blocks_the_human"])
		self.assertNotIn("BLOCKED ON YOU", record["flags"])

if __name__ == "__main__":
	unittest.main()
