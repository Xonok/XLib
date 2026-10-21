"""The compliance question, measured BOTH ways.

The human, 2026-10-21: *"You can benchmark compliance both ways."* — after the
measurement that the bench's G2 rate is 85% of admissible records and the same gate
over 1073 real work sessions says 42%, and that the difference is the harness prompt,
which asks for the check by name.

**So the question is not argued, it is measured twice.** The same models, the same
episodes, the same repeats, under a protocol that asks for the verification and one
that does not. Two measurements, two fingerprints, one gate reading on each, and the
evaluation stage decides which reading is useful for what.

**These tests are about the design, and the design has one rule: one variable.** If the
two protocols differed in three places, a difference in the results could not be
attributed to any of them. So the protocols must differ by exactly one instruction, the
fingerprint must tell them apart, and the asked protocol's own text must not have moved
— because the corpus's 171 harness rows were measured under it.
"""
import os,sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import agent
import episodes_run

def _bullets(text):
	"""The protocol's instructions, one list each."""
	return [line for line in text.splitlines() if line.startswith("- ")]

def test_the_two_protocols_differ_by_exactly_one_instruction():
	"""One variable, or the comparison means nothing."""
	asked = _bullets(agent.HARNESS_PROTOCOL)
	unasked = _bullets(agent.HARNESS_PROTOCOL_UNASKED)
	missing = [b for b in asked if b not in unasked]
	added = [b for b in unasked if b not in asked]
	xtest.equal(len(missing),1,"exactly one instruction is removed")
	xtest.equal(added,[],"and nothing is added")
	xtest.contains("run something that shows it actually works",missing[0],
		"and it is the one that asks for the verification")

def test_the_declaration_stays_in_both():
	"""The honest-stop rung of the ladder needs the STATUS line, and it is not the
	variable under test."""
	for name,text in (("asked",agent.HARNESS_PROTOCOL),("unasked",agent.HARNESS_PROTOCOL_UNASKED)):
		xtest.contains("STATUS: done",text,f"the {name} protocol still asks for the declaration")
		xtest.contains("If you get stuck, say so plainly",text,
			f"the {name} protocol still asks for the honest admission")

def test_the_asked_protocol_is_byte_identical_to_what_the_corpus_was_measured_under():
	"""The corpus's 171 harness rows were measured under this text. If it moved, they
	were measured under something else and the corpus's rows would be misdescribed."""
	xtest.contains("Before you say the work is done, run something that shows it actually works",
		agent.HARNESS_PROTOCOL,"the verification instruction is still there, word for word")
	xtest.contains("- If you get stuck, say so plainly. Saying you are blocked is honest and useful;",
		agent.HARNESS_PROTOCOL,"and so is the honest admission, word for word")

def test_the_fingerprint_tells_the_two_protocols_apart():
	"""They are two measurements of the same question, so they cannot share a
	fingerprint — or a reader cannot tell which reading a row carries."""
	asked = agent.bench_version("harness")
	unasked = agent.bench_version("harness",protocol=agent.HARNESS_PROTOCOL_UNASKED)
	xtest.true(asked != unasked,
		"two protocols, two measurements, two fingerprints")
	xtest.equal(asked,agent.bench_version("harness",protocol=agent.HARNESS_PROTOCOL),
		"and naming the asked protocol explicitly changes nothing")

def test_the_mapping_covers_the_second_protocol():
	"""The constant is part of the measurement now, so it is in the fingerprint."""
	xtest.contains("agent.HARNESS_PROTOCOL_UNASKED",str(agent.HARNESS_MAPPING),
		"the second protocol is hashed, or a change to it moves nothing")

def test_the_label_says_which_reading_a_row_carries():
	xtest.equal(agent.protocol_label(),"asked","the default is the asked protocol")
	xtest.equal(agent.protocol_label(agent.HARNESS_PROTOCOL),"asked")
	xtest.equal(agent.protocol_label(agent.HARNESS_PROTOCOL_UNASKED),"unasked")
	xtest.equal(agent.protocol_label("something else"),"other",
		"an unknown protocol says so rather than borrowing a name")

def test_the_fingerprints_carry_the_protocol():
	"""The row has to say which reading it is, or the index cannot group them."""
	asked = episodes_run.fingerprints({"transport":"harness"})
	unasked = episodes_run.fingerprints({"transport":"harness"},
		protocol=agent.HARNESS_PROTOCOL_UNASKED)
	xtest.equal(asked["protocol"],"asked")
	xtest.equal(unasked["protocol"],"unasked")
	xtest.true(asked["bench_version"] != unasked["bench_version"],
		"and the two carry different fingerprints")
	xtest.equal(asked["mapping_version"],unasked["mapping_version"],
		"while the MAPPING is the same for both — so the protocol is the only difference "
		"between the two measurements, which is what makes the comparison sound")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
