"""The prompt's own vocabulary can travel as data, beside the answers it describes.

The words that mark a prompt's general part, its deep dive and its glossary are facts
about that prompt. When they live only in a README's command line, a corpus drifts from
its own measurements the first time the command is edited and the output is not
re-checked — and the drift shows up as a *number* that is quietly wrong, which is the
worst kind of wrong there is: it is legible, it is plausible, and nobody looks at it
twice.

These tests cover the reading of the file and the way it combines with the words given
on the command line.
"""
import json,os,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import review_explanations as re_

def _write(obj):
	handle,path = tempfile.mkstemp(suffix=".json")
	with os.fdopen(handle,"w") as fh:
		json.dump(obj,fh)
	return path

def test_the_three_word_lists_are_read_and_lowercased():
	path = _write({"general":["Overview"],"deep":["Deep Dive"],"glossary":["Glossary"]})
	try:
		vocab = re_.read_vocabulary(path)
	finally:
		os.unlink(path)
	xtest.equal(vocab,{"general":["overview"],"deep":["deep dive"],"glossary":["glossary"]})

def test_a_missing_list_is_an_empty_list_and_not_an_error():
	path = _write({"deep":["complex"]})
	try:
		vocab = re_.read_vocabulary(path)
	finally:
		os.unlink(path)
	xtest.equal(vocab["general"],[])
	xtest.equal(vocab["deep"],["complex"])

def test_a_vocabulary_that_is_not_an_object_is_an_error():
	path = _write(["overview"])
	try:
		xtest.raises(ValueError,lambda: re_.read_vocabulary(path))
	finally:
		os.unlink(path)

def test_a_list_that_is_not_a_list_is_an_error():
	path = _write({"general":"overview"})
	try:
		xtest.raises(ValueError,lambda: re_.read_vocabulary(path))
	finally:
		os.unlink(path)

def test_the_vocabulary_decides_where_the_deep_dive_starts():
	"""The words are the prompt's own, so the split depends on which ones are given.

	Two answers, one prompt: the first says "Deep Dive", the second says "Complex Part".
	A checker that only knows the first reports the second as having no deep dive at
	all — and the second is the shortest answer, the one most likely under scrutiny.
	"""
	deep_dive = "General Overview\nThe general part of the answer.\n\nDeep Dive\nThe detailed part."
	complex_part = "General Overview\nThe general part of the answer.\n\nComplex Part\nThe detailed part."
	with tempfile.TemporaryDirectory() as d:
		for name,text in (("deep.md",deep_dive),("complex.md",complex_part)):
			with open(os.path.join(d,name),"w") as fh:
				fh.write(text)
		out = os.path.join(d,"m.json")
		import subprocess,sys as _sys
		repo = REPO
		cmd = [_sys.executable,os.path.join(repo,"tools","modelbench","review_explanations.py"),
			"--answers",d,"--repo",d,"--out",out,"--general-word","overview",
			"--deep-word","deep dive"]
		subprocess.run(cmd,capture_output=True,text=True,check=True)
		rows = {r["file"]:r for r in json.load(open(out))["rows"]}
	xtest.true(rows["deep.md"]["has_deep"],"the answer that says Deep Dive has one")

	xtest.equal(rows["complex.md"]["has_deep"],False,
		"an answer that says Complex Part has none, unless that word is given")

def test_the_file_and_the_command_line_words_are_combined_not_substituted():
	path = _write({"general":["general situation"],"deep":["deep dive"],"glossary":["glossary"]})
	try:
		vocab = re_.read_vocabulary(path)
	finally:
		os.unlink(path)
	xtest.equal(vocab["general"],["general situation"],
		"the file's words are read as they are")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
