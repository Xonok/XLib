"""Marduk fits the pane it is in, including when there are more agents than rows.

The panel is a live list, so a list that runs past the bottom would scroll the
header away and leave the reader without the one line that says what they are
looking at. The body is capped and the agents it left out are counted.
"""
import io,os,re,sys
from contextlib import redirect_stdout
from unittest.mock import patch

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk import marduk as marduk_mod

def _marduk():
	with patch.object(marduk_mod.service,"resolve_url",return_value=""),patch.object(marduk_mod.service,"password",return_value="pw"):
		return marduk_mod.Marduk()

def _with_agents(count):
	m=_marduk()
	for i in range(count):
		m._on_new_session({"id":"ses_%02d"%i,"title":"agent-%02d"%i,"location":{"directory":"/w"}})
	return m

def _render(m,height,width=None):
	out=io.StringIO()
	with redirect_stdout(out):
		m._render(height=height,width=width)
	return [re.sub(r"\033\[[0-9;]*m","",line) for line in out.getvalue().splitlines()]

def _with_long_agents(count):
	m=_marduk()
	for i in range(count):
		m._on_new_session({"id":"ses_%02d"%i,"title":"a-rather-long-agent-role-%02d"%i,
			"location":{"directory":"/a/workspace/with/a/long/name"}})
	return m

def test_the_render_fits_the_height_it_is_given():
	lines=_render(_with_agents(30),10)
	xtest.true(len(lines)<=10,f"ten rows of room, got {len(lines)}")
	xtest.contains("=== Marduk (Live) ===","\n".join(lines))

def test_a_short_panel_says_how_many_agents_it_hid():
	lines=_render(_with_agents(30),10)
	xtest.contains("… +24 more","\n".join(lines))

def test_a_panel_too_short_for_the_body_keeps_the_header():
	lines=_render(_with_agents(30),2)
	xtest.true(len(lines)<=2,f"two rows hold the header and nothing else, got {len(lines)}")
	xtest.true(lines[0].endswith("=== Marduk (Live) ==="),f"the title survived: {lines!r}")

def test_the_render_never_exceeds_the_width_it_is_given():
	for width in (30,40,60,80):
		lines=_render(_with_long_agents(6),24,width)
		xtest.true(all(len(line)<=width for line in lines),
			f"a display of {width} columns must not run past {width}")

def test_a_narrow_panel_uses_the_compact_layout():
	lines=_render(_with_long_agents(1),24,40)
	body="\n".join(lines)
	xtest.contains("a-rather",body,"the role still names the agent")
	xtest.not_equal("a-rather-long-agent-role" in body,True,"the role is cut for a narrow pane")

def test_a_panel_one_row_high_keeps_the_title():
	lines=_render(_with_agents(30),1)
	xtest.equal(len(lines),1,"one row holds the title")
	xtest.true(lines[0].endswith("=== Marduk (Live) ==="),f"the title survived: {lines[0]!r}")

if __name__=="__main__":
	sys.exit(xtest.run(__file__))
