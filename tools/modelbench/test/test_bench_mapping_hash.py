"""The fingerprint has to cover the MAPPING, not only the prompt.

`bench_version` is the corpus's guarantee that a record written before a change visibly
disagrees with one written after it. It covered the prompt and the episodes. It did
**not** cover the mapping — the code that turns opencode's event stream into the trace
the gates read — so a change to the mapping moved every grade without moving the
fingerprint.

**What that cost.** The opencode-2 upgrade broke the mapping in four ways (E19-E22) and
again in two (E26, E27), and every harness row measured under the broken mapping had to
be thrown out and re-measured — with nothing supposed to have noticed, because the thing
that had changed was not in the fingerprint.

So the mapping's source goes into the harness fingerprint. The tests here are about the
two ways that can go wrong:

  1. The mapping is not in the hash at all — the hole this ticket is about.
  2. The mapping is in the hash but the LIST of what the mapping is has gone stale, so
     a function added to the harness path is silently outside the fingerprint again.
     A list that rots is the same hole with a lid on it, so a test walks the call graph
     and says what is missing.

And one more: the fingerprint has to be visible in the row, because a fingerprint
nobody can see in the row is a fingerprint nobody can use.
"""
import inspect,os,re,subprocess,sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import agent
import episodes_run
import ledger
import transport

def _modules():
	"""The two modules the mapping is made of."""
	return {"agent":sys.modules["agent"],"transport":sys.modules["transport"]}

def _reachable(entry,modules):
	"""Every function of `modules` that `entry` can reach, as 'module.name'.

	Walked through the code objects' global names, so a call the source only mentions
	in a docstring is not a call. A function reached through a local variable would be
	missed — nothing here does that, and the list below is short enough to read.
	"""
	seen = set()
	def walk(fn,label):
		if label in seen: return
		seen.add(label)
		for name in fn.__code__.co_names:
			for mod_name,mod in modules.items():
				obj = getattr(mod,name,None)
				if inspect.isfunction(obj) and obj.__module__ == mod.__name__:
					walk(obj,f"{mod_name}.{name}")
	walk(entry,f"{entry.__module__}.{entry.__name__}")
	return seen

def test_a_change_to_the_mapping_moves_the_harness_fingerprint():
	saved = agent.mapping_source
	harness_before = agent.bench_version("harness")
	direct_before = agent.bench_version("http")
	agent.mapping_source = lambda names = None: "a mapping that is not the one"
	try:
		xtest.not_equal(agent.bench_version("harness"),harness_before,
			"a change to the mapping must move the harness fingerprint")
		xtest.equal(agent.bench_version("http"),direct_before,
			"the direct path's fingerprint must not depend on the harness mapping")
	finally:
		agent.mapping_source = saved

def test_the_mapping_carries_the_source_of_everything_it_names():
	blob = agent.mapping_source()
	for name in agent.HARNESS_MAPPING:
		obj = agent._mapping_object(name)
		xtest.true(obj is not None,f"{name} is named by the mapping but does not exist")
		if inspect.isfunction(obj):
			xtest.contains(inspect.getsource(obj),blob,
				f"the source of {name} must be in the fingerprint")
		else:
			xtest.contains(agent._canonical(obj),blob,
				f"the value of {name} must be in the fingerprint")

def test_the_mapping_list_covers_the_whole_harness_path():
	"""The list cannot rot silently: whatever the harness path calls is in it."""
	reachable = _reachable(agent.run_episode_harness,_modules())
	missing = sorted(reachable - set(agent.HARNESS_MAPPING))
	xtest.equal(missing,[],
		"the harness path reaches functions the mapping does not cover, so a change to "
		"them would move the grades without moving the fingerprint")

def test_the_mapping_covers_every_constant_the_harness_path_reads():
	"""A constant is part of the measurement too: the wrong tool name mapped, or a
	different session length, changes what a grade means."""
	modules = _modules()
	listed = set(agent.HARNESS_MAPPING)
	missing = []
	for name in agent.HARNESS_MAPPING:
		obj = agent._mapping_object(name)
		if not inspect.isfunction(obj): continue
		for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]*",inspect.getsource(obj)):
			if not word.isupper(): continue
			for mod_name,mod in modules.items():
				value = getattr(mod,word,None)
				if value is None or inspect.isfunction(value) or inspect.isclass(value):
					continue
				if inspect.ismodule(value): continue
				if f"{mod_name}.{word}" in listed: continue
				missing.append(f"{mod_name}.{word}")
	xtest.equal(sorted(set(missing)),[],
		"the harness path reads constants the mapping does not cover")

def test_the_fingerprint_does_not_move_on_its_own():
	"""A set's repr depends on its iteration order, and Python randomises string
	hashing per process — so two runs of unchanged code could disagree about what
	they were measured under. A fingerprint that moves by itself is the invisible
	invalidation this hash exists to prevent."""
	code = ("import sys;sys.path.insert(0,%r);import agent;"
		"print(agent.bench_version('harness'),agent.mapping_version('harness'))"
		% os.path.join(REPO,"tools","modelbench"))
	seen = []
	for seed in ("0","1"):
		env = dict(os.environ,PYTHONHASHSEED=seed)
		proc = subprocess.run([sys.executable,"-c",code],capture_output=True,text=True,env=env)
		xtest.equal(proc.returncode,0,f"the probe failed: {proc.stderr}")
		seen.append(proc.stdout.strip())
	xtest.equal(seen[0],seen[1],
		"two runs of the same code must agree on the fingerprint")

def test_a_stale_name_is_written_down_rather_than_skipped():
	blob = agent.mapping_source(("agent.no_such_function",))
	xtest.contains("MISSING",blob,
		"a name that resolves to nothing must show up, not quietly remove itself "
		"from the fingerprint")

def test_a_source_that_cannot_be_read_is_an_error():
	"""A fingerprint that quietly omits part of the measurement is worse than none: it
	says a row was measured under something it was not."""
	saved = agent.inspect.getsource
	def unreadable(obj):
		raise OSError("could not get source code")
	agent.inspect.getsource = unreadable
	try:
		xtest.raises(agent.MappingUnreadable,lambda: agent.mapping_source(),
			"the run becomes a hole rather than a result with a wrong number on it")
	finally:
		agent.inspect.getsource = saved

def test_the_mapping_version_names_the_mapping_and_nothing_else():
	version = agent.mapping_version("harness")
	xtest.true(version.startswith("map-"),"the mapping has its own fingerprint")
	xtest.not_equal(version,agent.bench_version("harness"),
		"the mapping is part of the measurement, not the whole of it")
	xtest.equal(agent.mapping_version("http"),None,
		"the direct path has no mapping hash yet, and says so rather than implying "
		"a coverage that is not there")
	xtest.equal(agent.mapping_version(),None)

def test_the_record_carries_the_mapping_version():
	prints = episodes_run.fingerprints({"id":"m","provider":"zen","transport":"harness"})
	xtest.equal(prints["mapping_version"],agent.mapping_version("harness"),
		"the row says which mapping produced it")
	xtest.true("bench_version" in prints and "grade_version" in prints)
	direct = episodes_run.fingerprints({"id":"m","provider":"zen","transport":"http"})
	xtest.equal(direct["mapping_version"],None)

def test_the_ledger_row_carries_the_mapping_version():
	saved = getattr(ledger,"args",None)
	ledger.args = type("Args",(),{"check":False})()
	try:
		row = ledger._row("/tmp","wave/run.jsonl",1,
			{"model":"m","episode":"invoicer","repeat":1,"grade":"autonomy",
			"gates":{},"failed_gates":[],"bench_version":"bench-abc",
			"grade_version":"grade-abc","mapping_version":"map-abc",
			"detail":{"checker":{"cases":[1]}}},{})
	finally:
		if saved is None: del ledger.args
		else: ledger.args = saved
	xtest.equal(row["mapping_version"],"map-abc",
		"the index carries the mapping, so a reader can see it without the trace file")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
