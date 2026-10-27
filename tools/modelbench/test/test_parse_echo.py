"""E33 — the loop's own status messages must not become part of a written file.

The four-tool loop appends `you requested: …` and `RESULT: …` messages to the conversation
after every action. A model can echo them back in its next reply, and the write parser used
to capture everything from `CONTENT:` to the end of the reply, so the echo became part of
the file and produced a SyntaxError in code the model did not write.

Measured 2026-10-27 on the first stockroom calibration (`nemotron-ultra`) and in two landed
billing traces of `gemini-3.1-flash-lite` — one of them a write whose file was later
rewritten, one a `not-measurable` repeat. The same failure shape as E18, whose bound at the
next action header is kept.
"""
import os,sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import agent

def test_a_write_payload_ends_at_the_echoed_request_line():
	reply = ('ACTION: write\nPATH: cli.py\nCONTENT:\nprint("ok")\n\n'
		'you requested: run python3 check.pyRESULT:\nexit 0\npass\n')
	action = agent.parse_action(reply)
	xtest.equal(action.content.strip(),'print("ok")',
		"the harness message after the payload is not part of the file")

def test_a_result_header_alone_also_ends_the_payload():
	reply = "ACTION: write\nPATH: x.py\nCONTENT:\nvalue = 1\nRESULT:\nexit 0\n"
	action = agent.parse_action(reply)
	xtest.equal(action.content.strip(),"value = 1",
		"the echoed RESULT block is not part of the file")

def test_a_real_second_action_still_batches():
	reply = "ACTION: write\nPATH: x.py\nCONTENT:\nprint(1)\nACTION: read\nPATH: x.py\n"
	action = agent.parse_action(reply)
	xtest.equal(action.content.strip(),"print(1)","E18's bound is unchanged")
	xtest.true(action.batched,"a second action is still recorded as a batch")

def test_a_payload_without_an_echo_is_unchanged():
	reply = "ACTION: write\nPATH: x.py\nCONTENT:\nline one\nline two\n"
	action = agent.parse_action(reply)
	xtest.equal(action.content,"line one\nline two","the ordinary case is untouched")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
