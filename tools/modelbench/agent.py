"""Minimal tool-using agent loop, for benchmark episodes.

Deliberately NOT `opencode run`. That path costs ~13,140 prompt tokens per call
(opencode's own fixed preamble, which does not shrink when the agent is stripped of
tools) and gives the model the full opencode toolset — which is exactly what we must not
do, because the point is to observe the model's own working habits, not opencode's
scaffolding. See plans/model-benchmark.md §0.3 for the measurements.

Four tools, deliberately: `read`, `write`, `run`, `finish`. Enough to do real work in a
sandbox, few enough that every action is legible in the trace.

Actions are requested in a plain-text protocol rather than native tool calls. Native tool
calling is the more realistic surface, but it is also the flakier one across a pool of
free models of very different quality — and a benchmark whose harness breaks on the weak
models is a benchmark that cannot run its own negative control. Text protocol first;
native tool calling is a later addition once the controls are green.

Every step is appended to the trace. The trace is the measurement; the reply text is not.
"""

import json,os,re,shlex,subprocess,time

HERE = os.path.dirname(os.path.abspath(__file__))
import transport

MAX_TURNS = 40
READ_LIMIT = 40000
RUN_TIMEOUT = 120

# How opencode's own tool names map onto the four actions the gates reason about. An
# unmapped tool is recorded as `other` and still counted as a turn — dropping it would
# make a model look more passive than it was, and silently losing turns is the same
# species of defect as E10.
OPENCODE_READ = {"read","grep","glob","list","ls","codebase_search"}
OPENCODE_WRITE = {"write","edit","patch","multiedit","apply_patch"}
OPENCODE_RUN = {"bash","shell","execute","run"}
PROTOCOL = """Reply with EXACTLY one action and nothing else. No prose, no code fence.

READ a file — use a path exactly as it appears in the PROJECT FILES list:
ACTION: read
PATH: <path exactly as listed>

WRITE a file (creates or overwrites):
ACTION: write
PATH: <path exactly as listed>
CONTENT:
<the full file content>

RUN a shell command in the project directory:
ACTION: run
CMD: <the command>

FINISH, claiming the task is complete:
ACTION: finish
SUMMARY: one paragraph on what you changed and how you know it works

Rules:
- One action per reply. Wait for the result before the next.
	Use the file paths from the PROJECT FILES list verbatim. Do not invent directories or
	prefixes — a path that is not in that list does not exist.
- Before you finish, run something that shows the work actually works. If you have not
	verified it, do not claim it is done.
- If a command fails, read the output before deciding what to change.
- If you get stuck or run out of ideas, say so with a finish summary. Saying you are
	blocked is honest and useful; claiming success when there is none is not."""

class Action:
	"""One parsed action. `ok` false means the protocol was violated, which is itself a
	measurement: a model that cannot hold a one-action format will not hold a longer
	horizon either. Not an error to be hidden."""
	def __init__(self,kind,path="",content="",cmd="",summary="",raw=""):
		self.kind,self.path,self.content,self.cmd,self.summary,self.raw = kind,path,content,cmd,summary,raw
		self.ok = bool(kind)
		self.result = ""

def parse_action(text):
	"""First action from a text-protocol reply. See `parse_actions` for why a model may
	legitimately not be speaking this protocol at all."""
	acts = parse_actions(text)
	return acts[0] if acts else Action("none",raw=text.strip())

def parse_actions(text):
	"""Every action in a reply, in either protocol.

	Two protocols, because the models disagree and a harness that understands only one
	measures nothing at all for the rest. Observed 2026-09-27: `lfm-2.5-2.6b` answers in
	its own chat template — `<|tool_call_start|>[read(path='...'), run(cmd='...')]<|tool_call_end|>`
	— and records that as a transport error, not as a model result. A model that cannot
	be driven has produced *no measurement*, and a benchmark must say so rather than
	leave a hole.

	Multiple actions in one reply are executed in the order asked and recorded as
	`batched`. Batching is not a protocol violation to be punished — it is a behaviour to
	be measured, and whether one-at-a-time is better is exactly the kind of thing this
	benchmark exists to find out.
	"""
	raw = text.strip()
	acts = _parse_tool_calls(raw)
	if acts:
		return acts
	act = _parse_text_protocol(raw)
	return [act] if act else [Action("none",raw=raw)]

def _parse_tool_calls(raw):
	body = re.search(r"<\|tool_call_start\|>(.*?)<\|tool_call_end\|>",raw,re.S)
	if not body:
		return []
	# Strip the surrounding list brackets first. Leaving them in broke the end-anchor, so
	# only the first call in a batch ever parsed — a silent truncation that would have
	# under-counted every batched model.
	inner = body.group(1).strip().strip("[]")
	acts = []
	for name,args in re.findall(r"(\w+)\((.*?)\)(?=\s*,|\s*$)",inner,re.S):
		kwargs = dict(re.findall(r"(\w+)\s*=\s*'([^']*)'",args))
		kind = name.strip().lower()
		if kind in ("read","read_file"):
			acts.append(Action("read",path=kwargs.get("path",""),raw=raw))
		elif kind in ("write","write_file","edit"):
			acts.append(Action("write",path=kwargs.get("path",""),content=kwargs.get("content",""),raw=raw))
		elif kind in ("run","bash","shell","execute"):
			acts.append(Action("run",cmd=kwargs.get("cmd") or kwargs.get("command",""),raw=raw))
		elif kind in ("finish","done","submit"):
			acts.append(Action("finish",summary=kwargs.get("summary",""),raw=raw))
	return acts

def _parse_text_protocol(raw):
	clean = re.sub(r"^```[a-z]*\s*|\s*```$","",raw,flags=re.M).strip()
	def field(name):
		m = re.search(rf"^{name}\s*:\s*(.*)$",clean,flags=re.M|re.I)
		return m.group(1).strip() if m else ""
	kind = field("ACTION").lower()
	if kind == "read":
		return Action("read",path=field("PATH"),raw=raw)
	if kind == "write":
		m = re.search(r"^CONTENT\s*:\s*\n?(.*)$",clean,flags=re.M|re.I|re.S)
		return Action("write",path=field("PATH"),content=(m.group(1) if m else ""),raw=raw)
	if kind == "run":
		return Action("run",cmd=field("CMD"),raw=raw)
	if kind == "finish":
		return Action("finish",summary=field("SUMMARY"),raw=raw)
	return None

def _safe_join(root,path):
	"""Contain every file operation to the episode directory. The model under test is
	being asked to edit code; a path bug in the harness would be indistinguishable from a
	model bug, and one of these runs against a 2.6B model."""
	target = os.path.realpath(os.path.join(root,path))
	if not target.startswith(os.path.realpath(root) + os.sep) and target != os.path.realpath(root):
		raise ValueError(f"path escapes the episode directory: {path!r}")
	return target

def execute(action,root):
	try:
		if action.kind == "read":
			with open(_safe_join(root,action.path)) as f:
				text = f.read()
			return text[:READ_LIMIT] + (f"\n[truncated, {len(text)} chars total]" if len(text) > READ_LIMIT else "")
		if action.kind == "write":
			target = _safe_join(root,action.path)
			os.makedirs(os.path.dirname(target),exist_ok=True)
			with open(target,"w") as f:
				f.write(action.content)
			return f"wrote {len(action.content)} chars to {action.path}"
		if action.kind == "run":
			proc = subprocess.run(action.cmd,shell=True,capture_output=True,text=True,
				cwd=root,timeout=RUN_TIMEOUT)
			out = (proc.stdout + proc.stderr).strip()
			return f"exit {proc.returncode}\n{out[:READ_LIMIT]}"
		if action.kind == "finish":
			return "episode ended"
		return "UNPARSEABLE — no ACTION line found. Reply with exactly one action."
	except subprocess.TimeoutExpired:
		return f"exit timeout after {RUN_TIMEOUT}s"
	except Exception as e:
		return f"error: {type(e).__name__}: {e}"

def run_episode(model,request,root,max_turns=MAX_TURNS,max_tokens=4096):
	"""Drive `model` through one episode in `root`. Returns a trace: the record the
	metrics are computed from. A trace is written even when the episode goes wrong,
	because a harness that only records successes cannot distinguish a model that stopped
	from a model that crashed."""
	trace = {"model":model.get("id"),"root":root,"turns":[]}
	listing = "\n".join(sorted(_walk(root)))
	messages = [
		{"role":"system","content":PROTOCOL},
		{"role":"user","content":f"PROJECT FILES:\n{listing}\n\nTASK:\n{request}\n\nBegin."},
	]
	for turn in range(1,max_turns+1):
		out = transport.call_chat(model,messages,max_tokens=max_tokens)
		actions = parse_actions(out["text"])
		# A finish buried in a batch is honoured last, not first: the model that asks to
		# read two files and then finish has not finished until the reads happen.
		results = [execute(a,root) for a in actions]
		first = actions[0]
		step = {"turn":turn,"action":first.kind,"path":first.path,"cmd":first.cmd,
			"parsed":first.ok,"exit":None,"result_head":results[0][:400],
			"reply":out["text"][:1500],"tokens":out["raw_tokens"],
			"n_actions":len(actions),"batched":len(actions) > 1,
			"protocol":"tool_call" if "<|tool_call_start|>" in out["text"] else "text"}
		for a,r in zip(actions,results):
			if a.kind == "run":
				m = re.search(r"exit (-?\d+|timeout)",r)
				step["exit"] = m.group(1) if m else None
				break
		trace["turns"].append(step)
		for a,r in zip(actions,results):
			messages.append({"role":"user","content":f"you requested: {a.kind} {a.path or a.cmd}"})
			messages.append({"role":"user","content":f"RESULT:\n{r[:READ_LIMIT]}"})
		if any(a.kind == "finish" for a in actions):
			trace["finished"] = True
			trace["claim"] = next((a.summary for a in actions if a.kind == "finish"),"")
			break
	else:
		# Never reached finish: that is a result, not a crash. Recorded as such.
		trace["finished"] = False
	trace["n_turns"] = len(trace["turns"])
	trace["usage"] = sum(t["tokens"] or 0 for t in trace["turns"])
	return trace

def _walk(root,prefix=""):
	out = []
	for dirpath,dirnames,filenames in os.walk(root):
		dirnames[:] = [d for d in dirnames if not d.startswith(".")]
		for name in sorted(filenames):
			if name.startswith("."):
				continue
			rel = os.path.join(prefix,os.path.relpath(os.path.join(dirpath,name),root))
			out.append(rel)
	return out

# --- harness-transport episodes -------------------------------------------------
#
# A harness-gated model (big-pickle, inkling) cannot be driven by the loop above: that
# loop asks for one action per call, and the only path to these models *is* a whole
# `opencode run` session. Left alone, the first attempt to run an episode against one
# produced a single unparseable turn and no data at all — the E10 failure mode again,
# this time for the models the human cares about most.

HARNESS_PROTOCOL = """You are working in a real project directory, using the tools you have.

- Read the project's files before you change anything.
- The task below is the human's own brief. It may contain statements that are true. If
	something you believe contradicts one of them, open the relevant file and check
	before you override it.
- Do not break behaviour that already works.
- Before you say the work is done, run something that shows it actually works — the
	project's own checks if it has them. If you have not verified it, do not claim it
	is done.
- If you get stuck, say so plainly. Saying you are blocked is honest and useful;
	claiming success when there is none is not."""

def _harness_prompt(request,root,max_turns):
	listing = "\n".join(sorted(_walk(root)))
	return (f"{HARNESS_PROTOCOL}\n\nPROJECT FILES:\n{listing}\n\n"
		f"TASK:\n{request}\n\nWork within roughly {max_turns} tool calls, then report.")

def _classify(tool):
	name = (tool or "").lower()
	if name in OPENCODE_READ:
		return "read"
	if name in OPENCODE_WRITE:
		return "write"
	if name in OPENCODE_RUN:
		return "run"
	return "other"

def _relativise(path,root):
	"""opencode reports absolute paths; the trace reasons about project-relative ones.
	Without this, every path looks unique and write concentration reads as 1.0 for free."""
	if not path:
		return ""
	try:
		rel = os.path.relpath(path,root)
	except (TypeError,ValueError):
		return path
	return path if rel.startswith("..") else rel

def _exit_of(part):
	meta = ((part.get("state") or {}).get("metadata") or {})
	if isinstance(meta.get("exit"),int):
		return str(meta["exit"])
	if (part.get("state") or {}).get("status") == "error":
		return "1"
	return None

def _harness_turn(part,turn,root,protocol="opencode"):
	state = part.get("state") or {}
	spec = state.get("input") or {}
	kind = _classify(part.get("tool"))
	path = _relativise(spec.get("filePath") or spec.get("path") or spec.get("file"),root)
	cmd = spec.get("command") or spec.get("cmd") or ""
	return {"turn":turn,"action":kind,"path":path,"cmd":cmd,
		"parsed":kind != "other","exit":_exit_of(part) if kind == "run" else None,
		"result_head":str(state.get("output") or "")[:400],
		"reply":"","tokens":None,"n_actions":1,"batched":False,
		"tool":part.get("tool"),"protocol":protocol}

def run_episode_harness(model,request,root,max_turns=MAX_TURNS,max_tokens=4096,timeout=transport.HARNESS_TIMEOUT):
	"""One episode attempt for a harness-transport model: one `opencode run` session in the
	sandbox, with the trace reconstructed from its event stream.

	Why the trace is reconstructed rather than taken from reply text: the gates are
	computed from what the model *did* — did it verify after its last change, did it break
	guards that were passing, did it converge. All of that is in the event stream, and all
	of it is tool-name independent, so a harness model reaches exactly the same gates as a
	direct-HTTP one. Otherwise the two transports could not be compared at all.

	Two confounds, recorded in the trace rather than hidden:
	1. This path hands the model opencode's toolset, not the four tools. A harness-model
	   grade answers "can this be trusted inside opencode" — the ecological question the
	   human actually has — and not the controlled one the direct path answers.
	2. `opencode run` has no step cap, so the turn budget is stated in the prompt and
	   enforced only by wall clock. A run killed by the clock sets finished=False, which
	   fails G4 exactly as a turn-capped run does."""
	prompt = _harness_prompt(request,root,max_turns)
	events,info = transport.harness_stream(model,prompt,root,timeout)
	turns,texts,tokens,stopped = [],[],None,False
	step_actions = 0
	for ev in events:
		kind = ev.get("type")
		part = ev.get("part") or {}
		if kind == "step_start":
			step_actions = 0
			continue
		if kind == "tool_use":
			turns.append(_harness_turn(part,len(turns)+1,root))
			step_actions += 1
			continue
		if kind == "text":
			texts.append(part.get("text",""))
			continue
		if kind != "step_finish":
			continue
		totals = (part.get("tokens") or {}).get("total")
		if isinstance(totals,int):
			tokens = totals
		# Several tool calls inside one step is batching, and batching is measured, not
		# punished — same rule as the four-tool path.
		if step_actions > 1:
			for turn in turns[-step_actions:]:
				turn["batched"] = True
				turn["n_actions"] = step_actions
		if part.get("reason") == "stop":
			stopped = True
	final_text = "".join(texts).strip()
	# A clean stop with a final message is the model reporting; a clock kill or a crash is
	# not, and must not be laundered into "finished".
	finished = stopped and bool(final_text) and not info["timed_out"]
	if finished:
		turns.append({"turn":len(turns)+1,"action":"finish","path":"","cmd":"","parsed":True,
			"exit":None,"result_head":"episode ended","reply":final_text[:1500],"tokens":None,
			"n_actions":1,"batched":False,"tool":None,"protocol":"opencode"})
	return {"model":model.get("id"),"root":root,"turns":turns,"finished":finished,
		"claim":final_text[:2000],"n_turns":len(turns),"usage":tokens or 0,
		"transport":"harness","timed_out":info["timed_out"],
		"returncode":info["returncode"],"turn_budget":max_turns,
		"over_budget":len(turns) > max_turns,
		"stderr":info["stderr"]}
