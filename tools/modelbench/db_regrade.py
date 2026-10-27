"""Re-grade a harness run from opencode's session database, without running the model.

**Why this exists.** The harness mapping consumes an EVENT STREAM — the JSON lines
`opencode run --format json` prints. A record stores the trace the mapping built from
that stream, and the stream itself, but a row whose mapping was broken cannot be
re-derived: the grades it carries were computed from events the mapping read wrongly,
and the events are gone. So the rows were thrown out and re-measured, which costs a
model call and a provider's quota.

**The events are not gone.** opencode keeps every session in its database: the prompt as
the user message, and for each assistant message the reasoning, the text and the tool
parts — with the tool's name, its input, its output and the command's exit code. So the
stream can be rebuilt from the session, and the LANDED mapping can be applied to it.

**The mapping is applied, not re-implemented.** That is the whole point. The mapping is
the code that turns a model's output into the trace the gates read, and it is what
`bench_version` hashes: a re-grade that used its own copy of the mapping would be a
measurement under a different instrument, and the corpus's guarantee — evaluation is a
pure function of stored measurement — would not hold. So the events are the INPUT, and
the mapping is the mapping.

**What the database stores, and where it differs from the stream.** Measured against
opencode 2.0.31 and its database, with a live `opencode run` as the reference:

| the stream printed | the database stores |
|---|---|
| `part.tool` | `part.name` |
| `state.output` (a string) | `state.content` (a list of text parts) |
| `state.metadata.metadata.exit` | `state.metadata.exit` — hoisted one level up |
| `step_finish` for every step | only for a step that made tool calls |
| tool calls in completion order | a message's parts in creation order |

Every one of those was a difference that would have silently moved a turn, and four of
the five are the kind that reads as "the model did something slightly different".
"""
import argparse,json,os,re,sqlite3,sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
	sys.path.insert(0,HERE)
import agent
import episodes_run
import trace
import transport

DB_PATH = os.path.expanduser("~/.local/share/opencode/opencode.db")
EXIT_SUFFIX = re.compile(r"^Exited with code -?\d+$")

def connect(path=DB_PATH):
	"""The session database, read-only.

	Read-only because the corpus's rule is that a measurement is not edited: a re-grade
	writes a NEW record beside the old one, and the database is the raw end of it.
	"""
	db = sqlite3.connect(f"file:{path}?mode=ro",uri=True)
	db.row_factory = sqlite3.Row
	return db

def output_of(state):
	"""The tool's output, as the event stream carried it.

	opencode's shell tool appends an 'Exited with code N' line to the content it
	renders, but the stream's `state.output` holds the output without it. The database
	stores only the rendered content, so the suffix is taken off again — otherwise the
	evidence for a verification would carry a line the stream never had.
	"""
	content = state.get("content")
	if content is None:
		content = state.get("output")
	items = [i.get("text","") for i in content if isinstance(i,dict)] if isinstance(content,list) else []
	if not items and isinstance(content,str):
		items = [content]
	if items and EXIT_SUFFIX.match((items[-1] or "").strip()):
		items = items[:-1]
	return "".join(items)

def completion_key(part):
	"""When a tool call finished.

	The stream printed a tool call when it COMPLETED, so parallel calls come out in
	completion order. The database keeps a message's parts in creation order — the order
	the model REQUESTED them — and for parallel calls those differ. The order decides
	which turn a write or a verification landed on, so it is not a detail.
	"""
	t = part.get("time") or {}
	st = part.get("state") or {}
	t2 = st.get("time") or {}
	for v in (t.get("completed"),t2.get("end"),t.get("ran"),t2.get("start"),
			t.get("created"),t2.get("start")):
		if isinstance(v,int):
			return v
	return 0

def tool_part(part):
	"""A tool part in the shape the event stream printed."""
	state = part.get("state") or {}
	meta = state.get("metadata") or {}
	return {"type":"tool","id":part.get("id"),"tool":part.get("name"),
		"state":{"status":state.get("status"),"input":state.get("input") or {},
			"output":output_of(state),
			"metadata":{"metadata":meta,"content":state.get("content") or []},
			"time":part.get("time") or {}}}

def session_events(db,session_id):
	"""The event list for one session, as `opencode run --format json` printed it.

	Returns (events, info). `info` carries the four things the mapping reads off a
	run: whether it was killed, what it returned, and what the provider said.
	"""
	rows = db.execute("select seq,type,data from session_message where session_id=? order by seq",
		(session_id,)).fetchall()
	events = []
	err = None
	spoke = False
	failed = False
	for r in rows:
		d = json.loads(r["data"])
		if r["type"] == "assistant":
			if d.get("error"):
				# A step the provider refused. opencode prints it as an event, and the
				# CLI exits non-zero even when it recovers and finishes the session —
				# which is why a session that spoke after an error still reads as
				# unfinished.
				failed = True
				events.append({"type":"error","error":d["error"],"sessionID":session_id})
			content = d.get("content") or []
			events.append({"type":"step_start","sessionID":session_id})
			tools = 0
			for part in sorted(content,key=lambda p: 0 if p.get("type") != "tool" else completion_key(p)):
				pt = part.get("type")
				if pt == "text":
					events.append({"type":"text","part":{"text":part.get("text","")},"sessionID":session_id})
				elif pt == "reasoning":
					events.append({"type":"reasoning","part":{"text":part.get("text","")},"sessionID":session_id})
				elif pt == "tool":
					tools += 1
					events.append({"type":"tool_use","part":tool_part(part),"sessionID":session_id})
			if tools:
				# Only a step that made tool calls emits a step_finish. The final text
				# step carries none, which is why a session's last token total in the
				# stream is the last TOOL-CALLING step's.
				events.append({"type":"step_finish","part":{"tokens":d.get("tokens") or {},
					"reason":"tool-calls"},"sessionID":session_id})
			else:
				spoke = True
			continue
		if d.get("error"):
			err = d["error"]
			events.append({"type":"error","error":err,"sessionID":session_id})
	# The run's outcome. A session that ended on the model's final text, with no
	# refused step along the way, exited cleanly; one with a refused step did not, even
	# if it recovered; one that ended on neither was cut short, and saying so is better
	# than calling it a clean exit.
	returncode = 0 if (spoke and not failed and err is None) else None
	info = {"returncode":returncode,"timed_out":False,"stderr":"","provider_error":"","stdout":""}
	return events,info

def session_prompt(db,session_id):
	"""The prompt the session was actually given: its first user message."""
	r = db.execute("select data from session_message where session_id=? and type='user' order by seq limit 1",
		(session_id,)).fetchone()
	if not r:
		return ""
	return json.loads(r["data"]).get("text") or ""

def find_session(db,basename):
	"""The session that ran in a sandbox, by the sandbox's name.

	The name is the correspondence: the record carries the sandbox it ran in, and the
	session's directory is that sandbox. The record's own model id is the wrong thing to
	look it up by — the waves' state directories stopped corresponding to it in
	September, for the same reason the ledger's state lookup did.
	"""
	r = db.execute("select id from session_v2 where directory like ? order by time_created desc limit 1",
		("%/"+basename,)).fetchone()
	return r["id"] if r else None

def regrade(db,record,state_dir,episode,model=None):
	"""Re-grade one record from its session.

	`state_dir` is the run's retained final state — the checker has to read the model's
	final files, and the sandbox itself is gone. `record["sandbox"]` is what the mapping
	is given, because the mapping relativises the paths it reads against the sandbox the
	model worked in, and the state directory is a copy of it under another name.

	Returns (grade, failed_gates, trace, result), or None when the session is not in
	the database.
	"""
	base = os.path.basename(record["sandbox"])
	sid = find_session(db,base)
	if not sid:
		return None
	events,info = session_events(db,sid)
	prompt = session_prompt(db,sid)
	model = model or {"id":record.get("model"),"transport":"harness"}
	saved_stream = transport.harness_stream
	saved_prompt = agent._harness_prompt
	saved_plant = agent._plant_agent_definition
	# The mapping is applied unchanged; only its INPUTS come from the database.
	transport.harness_stream = lambda *a,**k: (events,info)
	agent._harness_prompt = lambda *a,**k: prompt
	agent._plant_agent_definition = lambda *a,**k: None
	try:
		raw = agent.run_episode_harness(model,episode["request"],record["sandbox"],
			max_turns=agent.MAX_TURNS)
	finally:
		transport.harness_stream = saved_stream
		agent._harness_prompt = saved_prompt
		agent._plant_agent_definition = saved_plant
	raw["root"] = state_dir
	result = trace.analyse(raw,baseline=episode["baseline"],episode=episode["name"])
	grade,failed = trace.grade(result)
	return grade,failed,raw,result

def state_dir_for(src,record,state_root):
	"""The retained final state of a run, by trying the names it can have.

	The state directory is named after the trace file, which is named after the
	registry key — but the waves have not all used the same naming, so a record's state
	can be under the trace's stem, under the model's name, or under the stem with a
	suffix the trace file carries and the state directory does not. Every prefix of the
	stem is tried, longest first, so a naming that has not been seen before still
	finds its state.
	"""
	if record.get("state"):
		named = os.path.join(os.path.dirname(src),record["state"])
		if os.path.isdir(named):
			return named
	stem = os.path.basename(src)
	if stem.endswith(".jsonl"):
		stem = stem[:-len(".jsonl")]
	repeat = record.get("repeat") if record.get("repeat") is not None else 0
	parts = stem.split("--")
	candidates = ["--".join(parts[:i]) for i in range(len(parts),0,-1)]
	candidates.append(f'{record.get("model")}--{record.get("episode")}')
	for name in candidates:
		guess = os.path.join(state_root,f"{name}--{repeat}")
		if os.path.isdir(guess):
			return guess
	return None

def main():
	p = argparse.ArgumentParser(description="Re-grade harness records from opencode's session database")
	p.add_argument("--traces",required=True,help="a trace file, or a directory of them")
	p.add_argument("--state",help="where the retained state lives; default: <traces dir>/state")
	p.add_argument("--db",default=DB_PATH)
	p.add_argument("--out",help="where to write the re-graded records")
	p.add_argument("--only-disagree",action="store_true",
		help="report only the records whose grade changed")
	args = p.parse_args()

	files = []
	if os.path.isdir(args.traces):
		for name in sorted(os.listdir(args.traces)):
			if name.endswith(".jsonl"):
				files.append(os.path.join(args.traces,name))
	else:
		files = [args.traces]
	db = connect(args.db)
	episodes = {}
	out = open(args.out,"a") if args.out else None
	try:
		for path in files:
			for line in open(path):
				line = line.strip()
				if not line:
					continue
				record = json.loads(line)
				if not isinstance(record,dict) or record.get("transport") != "harness":
					continue
				episode_name = record.get("episode")
				if episode_name not in episodes:
					episodes[episode_name] = episodes_run.load_episode(episode_name)
				state_dir = state_dir_for(path,record,args.state or os.path.join(os.path.dirname(path),"state"))
				if not state_dir:
					print(f"{path}: no retained state for repeat {record.get('repeat')}")
					continue
				got = regrade(db,record,state_dir,episodes[episode_name])
				if got is None:
					print(f"{path}: no session for {record.get('sandbox')}")
					continue
				grade,failed,raw,result = got
				same = grade == record.get("grade")
				if same and args.only_disagree:
					continue
				print(f"{os.path.basename(path)} repeat {record.get('repeat')} "
					f"{record.get('model')} {episode_name}: "
					f"{record.get('grade')} -> {grade} {'(same)' if same else '(CHANGED)'}")
				if out:
					out.write(json.dumps({"episode":episode_name,"model":record.get("model"),
						"transport":"harness","sandbox":record.get("sandbox"),
						"grade":grade,"failed_gates":failed,
						**episodes_run.fingerprints({"transport":"harness"}),
						"regraded_from":"opencode session database",
						"stored_grade":record.get("grade"),
						"trace":{"turns":raw.get("turns",[]),"finished":raw.get("finished"),
							"claim":raw.get("claim"),"status":raw.get("status"),
							"n_turns":raw.get("n_turns"),"usage":raw.get("usage"),
							"prompt":raw.get("prompt"),"session":record.get("sandbox")},
						"provenance":result.get("provenance",{}),
						**result}) + "\n")
					out.flush()
	finally:
		if out:
			out.close()

if __name__ == "__main__":
	main()
