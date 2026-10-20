"""The fingerprint has to cover the MAPPING, not only the prompt.

`bench_version` is the corpus's guarantee that a record written before a change visibly
disagrees with one written after it. It covered the prompt and the episodes. It did
**not** cover the mapping — the code that turns a model's output into the trace the
gates read — so a change to the mapping moved every grade without moving the
fingerprint.

**What that cost.** The opencode-2 upgrade broke the harness mapping in four ways
(E19-E22) and again in two (E26, E27), and every harness row measured under the broken
mapping had to be thrown out and re-measured — with nothing supposed to have noticed,
because the thing that had changed was not in the fingerprint.

So the mapping's source goes into the fingerprint. The tests here are about the three
ways that can go wrong:

  1. The mapping is not in the hash at all — the hole this ticket is about.
  2. The mapping is in the hash but the LIST of what the mapping is has gone stale, so
     a function added to a path is silently outside the fingerprint again. A list that
     rots is the same hole with a lid on it, so a test walks the call graph and says
     what is missing.
  3. **The two paths' fingerprints are not independent** — a change to the harness
     mapping must not invalidate a direct row, or every finding the direct corpus
     carries is invalidated by a change to a path it does not use. That is the same
     mistake pointed the other way, and it is the one this workspace's corpus is
     actually made of.

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
	"""The two modules the mappings are made of."""
	return {"agent":sys.modules["agent"],"transport":sys.modules["transport"]}

def _reachable(entry,stop=()):
	"""Every function of the two modules that `entry` can reach, as 'module.name'.

	Walked through the code objects' global names, so a call the source only mentions
	in a docstring is not a call. A function reached through a local variable would be
	missed — nothing here does that, and the lists are short enough to read.

	`stop` names the functions that belong to the other path: the two transports share
	`transport.call_chat`, which branches on the transport, so the direct path's call
	graph reaches the harness's functions through it. The walk stops there and does not
	demand them, because they are hashed as part of the other path's fingerprint.
	"""
	modules = _modules()
	seen = set()
	def walk(fn,label):
		if label in seen: return
		seen.add(label)
		if label in stop:
			return
		for name in fn.__code__.co_names:
			for mod_name,mod in modules.items():
				obj = getattr(mod,name,None)
				if inspect.isfunction(obj) and obj.__module__ == mod.__name__:
					walk(obj,f"{mod_name}.{name}")
	walk(entry,f"{entry.__module__}.{entry.__name__}")
	return seen

def test_a_change_to_the_mapping_moves_the_fingerprint():
	"""Both paths, and the direct one is the half this was about."""
	saved = agent.mapping_source
	for transport_name,entry in (("harness",None),("http",None)):
		before = agent.bench_version(transport_name)
		agent.mapping_source = lambda names=None,transport_name=None: "a mapping that is not the one"
		try:
			xtest.not_equal(agent.bench_version(transport_name),before,
				f"a change to the {transport_name} mapping must move its fingerprint")
		finally:
			agent.mapping_source = saved

def test_the_two_fingerprints_are_independent():
	"""A change to the harness mapping must not move the direct path's fingerprint.

	Otherwise every finding the direct corpus carries is invalidated by a change to a
	path it does not use — the same mistake the harness half was careful not to make.
	"""
	saved_harness = agent.HARNESS_MAPPING
	saved_direct = agent.DIRECT_MAPPING
	direct_before = agent.bench_version("http")
	harness_before = agent.bench_version("harness")
	agent.HARNESS_MAPPING = saved_harness + ("agent._walk",)
	try:
		xtest.equal(agent.bench_version("http"),direct_before,
			"a change to the harness mapping must not move the direct fingerprint")
		xtest.not_equal(agent.bench_version("harness"),harness_before,
			"but it must move the harness fingerprint")
	finally:
		agent.HARNESS_MAPPING = saved_harness
	agent.DIRECT_MAPPING = saved_direct + ("agent._walk",)
	try:
		xtest.equal(agent.bench_version("harness"),harness_before,
			"a change to the direct mapping must not move the harness fingerprint")
		xtest.not_equal(agent.bench_version("http"),direct_before,
			"but it must move the direct fingerprint")
	finally:
		agent.DIRECT_MAPPING = saved_direct

def test_the_mapping_carries_the_source_of_everything_it_names():
	for transport_name in ("harness","http"):
		blob = agent.mapping_source(transport_name=transport_name)
		for name in agent.mapping_for(transport_name):
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
	reachable = _reachable(agent.run_episode_harness,stop=agent.OTHER_TRANSPORT)
	missing = sorted(reachable - set(agent.HARNESS_MAPPING))
	xtest.equal(missing,[],
		"the harness path reaches functions the mapping does not cover, so a change to "
		"them would move the grades without moving the fingerprint")

def test_the_mapping_list_covers_the_whole_direct_path():
	"""The same for the direct path — the half this ticket was about."""
	reachable = _reachable(agent.run_episode,stop=agent.OTHER_TRANSPORT)
	missing = sorted(reachable - set(agent.DIRECT_MAPPING) - set(agent.OTHER_TRANSPORT))
	xtest.equal(missing,[],
		"the direct path reaches functions the mapping does not cover, so a change to "
		"them would move the grades without moving the fingerprint")
	for name in agent.OTHER_TRANSPORT:
		xtest.true(name not in agent.DIRECT_MAPPING,
			f"{name} is the other path's code, so it is not the direct path's mapping")
		xtest.true(name not in _reachable(agent.run_episode_harness),
			f"{name} must be unreachable from the harness path too, or it belongs in "
			"the harness mapping and the harness's own check will say so")

def test_the_mapping_covers_every_constant_the_path_reads():
	"""A constant is part of the measurement too: the wrong tool name mapped, or a
	different session length, changes what a grade means."""
	modules = _modules()
	for transport_name in ("harness","http"):
		listed = set(agent.mapping_for(transport_name))
		missing = []
		for name in listed:
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
			f"the {transport_name} path reads constants its mapping does not cover")

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

def test_the_fingerprint_does_not_move_on_its_own():
	"""A set's repr depends on its iteration order, and Python randomises string
	hashing per process — so two runs of unchanged code could disagree about what
	they were measured under. A fingerprint that moves by itself is the invisible
	invalidation this hash exists to prevent."""
	code = ("import sys;sys.path.insert(0,%r);import agent;"
		"print(agent.bench_version('http'),agent.bench_version('harness'),"
		"agent.mapping_version('http'))" % os.path.join(REPO,"tools","modelbench"))
	seen = []
	for seed in ("0","1"):
		env = dict(os.environ,PYTHONHASHSEED=seed)
		proc = subprocess.run([sys.executable,"-c",code],capture_output=True,text=True,env=env)
		xtest.equal(proc.returncode,0,f"the probe failed: {proc.stderr}")
		seen.append(proc.stdout.strip())
	xtest.equal(seen[0],seen[1],
		"two runs of the same code must agree on the fingerprint")

def test_the_mapping_version_names_the_mapping_and_nothing_else():
	for transport_name in ("harness","http"):
		version = agent.mapping_version(transport_name)
		xtest.true(version.startswith("map-"),"the mapping has its own fingerprint")
		xtest.not_equal(version,agent.bench_version(transport_name),
			"the mapping is part of the measurement, not the whole of it")
	xtest.equal(agent.mapping_version(),agent.mapping_version("http"),
		"no transport named is the direct path")
	xtest.raises(transport.TransportError,lambda: agent.mapping_version("carrier-pigeon"),
		"a transport with no mapping has no mapping fingerprint either")

def test_an_unknown_transport_is_an_error():
	"""A run under a transport with no mapping could not be fingerprinted, and a
	fingerprint that quietly measured it with the wrong one is worse than none."""
	xtest.raises(transport.TransportError,lambda: agent.bench_version("carrier-pigeon"),
		"an unknown transport must not be measured with the wrong mapping")

def test_the_record_carries_the_mapping_version():
	for transport_name in ("harness","http"):
		prints = episodes_run.fingerprints({"id":"m","provider":"zen","transport":transport_name})
		xtest.equal(prints["mapping_version"],agent.mapping_version(transport_name),
			"the row says which mapping produced it")
		xtest.true("bench_version" in prints and "grade_version" in prints)

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
