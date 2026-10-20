"""The harness path, mapped from opencode 2's event stream onto the trace the gates read.

Every test here is about a defect that made the instrument report a model as worse than
it was, or as not measurable at all:

  E19  the route was hardcoded to `opencode/{id}`, so an OpenRouter harness model was
       asked for by a namespace that does not exist — `provider.no-route`, recorded as
       "the model cannot answer" for a month.
  E20  opencode 2 dropped `--pure` and `--dir`. `--pure` prints the usage text and
       exits 0, so the failure was silent: no events, no error, and a model that looked
       like it had done nothing.
  E21  v2 takes the session directory from $PWD, not from the process cwd. A run that
       opened the wrong directory still succeeded, and graded `not-capable` on five
       turns of looking for files that were not there.
  E22  v2 dropped `tokens.total`, so every harness run recorded a token count of zero —
       a run that looks free was not.
  E24  the harness path never read the model's own `STATUS:` declaration, so the
       honest-stop rung of the ladder was unreachable there: a model that honestly said
       "blocked" was graded exactly like one that lied.
  E26  the exit code moved one level deeper, so every harness run recorded `exit=None`
       and G2 ("verifies unprompted") could not pass whatever the model did.
  E27  the "the run finished" event is gone, so `finished` was always False and G4
       ("terminates") could not pass either.

E26 and E27 together capped every harness-transport model at `supervision`, whatever it
did — the same shape as E16: the instrument manufacturing evidence against a model that
behaved correctly.
"""
import os,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import agent
import transport

def _with_flags(flags):
	"""Run with a known set of CLI flags, so the tests do not depend on which opencode
	happens to be installed."""
	saved = transport._CLI_FLAGS
	transport._CLI_FLAGS = set(flags)
	return saved

def test_the_route_uses_the_registry_s_provider():
	model = {"id":"thinkingmachines/inkling:free","provider":"openrouter","transport":"harness"}
	xtest.equal(transport.route_of(model),"openrouter/thinkingmachines/inkling:free",
		"an OpenRouter model is asked for in openrouter's namespace")

def test_the_console_gateway_is_asked_for_in_opencodes_namespace():
	model = {"id":"space-bunny-free","provider":"zen","transport":"http"}
	xtest.equal(transport.route_of(model),"opencode/space-bunny-free",
		"the Zen gateway is reached as opencode/<id>")

def test_an_explicit_namespace_wins_over_the_provider():
	model = {"id":"m","provider":"openrouter","namespace":"opencode","transport":"harness"}
	xtest.equal(transport.route_of(model),"opencode/m")

def test_a_model_with_no_provider_has_no_route():
	xtest.raises(transport.TransportError,lambda: transport.route_of({"id":"m"}),
		"a route that cannot be built is an error, not a guess")

def test_the_exit_code_is_read_from_wherever_opencode_keeps_it():
	v2 = {"state":{"metadata":{"metadata":{"exit":0}}}}
	xtest.equal(agent._exit_of(v2),"0","opencode 2 keeps the exit code one level deeper")
	v1 = {"state":{"metadata":{"exit":0}}}
	xtest.equal(agent._exit_of(v1),"0","opencode 1 keeps it at the old path")

def test_a_failed_command_is_read_as_a_failure():
	xtest.equal(agent._exit_of({"state":{"status":"error"}}),"1")

def test_an_exit_code_that_is_nowhere_is_an_error_rather_than_a_failed_check():
	xtest.raises(transport.UnseenShape,lambda: agent._exit_of({"state":{"metadata":{}}}),
		"a shape this tool does not know is a hole, not a silent 'did not verify'")

def test_the_token_total_is_read_from_the_old_field_and_the_new_one():
	xtest.equal(transport.token_total({"tokens":{"total":100}}),100)
	xtest.equal(transport.token_total({"tokens":{"input":10,"output":5,"reasoning":2,
		"cache":{"read":3,"write":1}}}),21,
		"opencode 2 dropped the total, so it is summed from the components")
	xtest.equal(transport.token_total({"tokens":{}}),None,
		"no tokens at all is not zero tokens")

def test_a_declaration_is_read_out_of_the_report():
	xtest.equal(agent._declared_status("all done\nSTATUS: done"),"done")
	xtest.equal(agent._declared_status("STATUS: BLOCKED"),"blocked")
	xtest.equal(agent._declared_status("  status: blocked  "),"blocked")
	xtest.equal(agent._declared_status("no declaration here"),"")

def test_the_four_tool_path_is_left_where_it_was():
	"""The four-tool path reads the declaration out of the FINISH action, and its
	protocol has asked for a STATUS since E17. A benchmark that is not wrong is not
	changed, so the corpus measured against it stays valid."""
	acts = agent.parse_actions("ACTION: finish\nSTATUS: done\nSUMMARY: fixed it")
	xtest.equal(acts[0].status,"done")
	acts = agent.parse_actions("ACTION: finish\nSUMMARY: fixed it")
	xtest.equal(acts[0].status,"")

def test_the_harness_prompt_asks_for_the_declaration():
	xtest.contains("STATUS: done",agent.HARNESS_PROTOCOL,
		"the harness path has to ask, or there is nothing to read")

def test_a_finished_session_is_one_that_ran_and_spoke():
	xtest.true(agent._finished("the report",{"timed_out":False,"returncode":0},False),
		"opencode 2 emits no stop event, so the exit code is the signal")
	xtest.equal(agent._finished("the report",{"timed_out":True,"returncode":0},False),False,
		"a clock kill is not a finished session")
	xtest.equal(agent._finished("",{"timed_out":False,"returncode":0},False),False,
		"a session that produced no text never spoke")
	xtest.equal(agent._finished("the report",{"timed_out":False,"returncode":1},False),False,
		"a crashed session is not a finished session")

def test_the_harness_command_asks_for_the_route_and_the_directory():
	saved = _with_flags({"--dir","--agent"})
	try:
		model = {"id":"thinkingmachines/inkling:free","provider":"openrouter","transport":"harness"}
		cmd = transport.harness_cmd(model,"/tmp/sandbox","the prompt")
		xtest.contains("openrouter/thinkingmachines/inkling:free"," ".join(cmd))
		xtest.contains("--dir /tmp/sandbox"," ".join(cmd))
	finally:
		transport._CLI_FLAGS = saved

def test_the_harness_command_does_not_ask_for_a_flag_opencode_does_not_have():
	saved = _with_flags(set())
	try:
		model = {"id":"big-pickle","provider":"zen","transport":"harness"}
		cmd = transport.harness_cmd(model,"/tmp/sandbox","the prompt")
		xtest.true("--pure" not in cmd,"opencode 2 prints usage and exits 0 for --pure")
		xtest.true("--dir" not in cmd,"--dir is gone in opencode 2")
	finally:
		transport._CLI_FLAGS = saved

def test_an_agent_definition_is_asked_for_by_name():
	saved = _with_flags({"--agent"})
	try:
		model = {"id":"big-pickle","provider":"zen","transport":"harness","agent":"inkling-verified"}
		cmd = transport.harness_cmd(model,"/tmp/sandbox","the prompt")
		xtest.contains("--agent inkling-verified"," ".join(cmd))
	finally:
		transport._CLI_FLAGS = saved

def test_an_agent_definition_this_opencode_cannot_select_is_an_error():
	saved = _with_flags(set())
	try:
		model = {"id":"big-pickle","provider":"zen","transport":"harness","agent":"inkling-verified"}
		xtest.raises(transport.TransportError,
			lambda: transport.harness_cmd(model,"/tmp/sandbox","the prompt"),
			"running the default agent and calling it the arm would be a lie")
	finally:
		transport._CLI_FLAGS = saved

def test_the_definition_is_planted_where_opencode_looks_for_it():
	with tempfile.TemporaryDirectory() as src:
		path = os.path.join(src,"arm.md")
		with open(path,"w") as fh:
			fh.write("---\nname: inkling-verified\n---\nbe careful\n")
		with tempfile.TemporaryDirectory() as sandbox:
			model = {"id":"m","provider":"zen","transport":"harness",
				"agent":"inkling-verified","agent_file":path}
			agent._plant_agent_definition(model,sandbox)
			planted = os.path.join(sandbox,".opencode","agent","inkling-verified.md")
			xtest.true(os.path.isfile(planted),"the definition is planted in the sandbox")
			with open(planted) as fh:
				xtest.contains("be careful",fh.read())

def test_a_definition_that_is_not_there_is_an_error():
	with tempfile.TemporaryDirectory() as sandbox:
		model = {"id":"m","provider":"zen","transport":"harness",
			"agent":"inkling-verified","agent_file":"/nowhere/arm.md"}
		xtest.raises(ValueError,lambda: agent._plant_agent_definition(model,sandbox))

def test_a_model_naming_an_agent_and_no_file_is_a_registry_problem():
	problems = transport.validate_registry({"m":{"id":"m","provider":"zen","transport":"harness",
		"agent":"inkling-verified"}})
	xtest.equal(len(problems),1,"the registry says so before a run is paid for")

def test_the_harness_prompt_is_part_of_the_measurement_only_for_the_harness_path():
	xtest.not_equal(agent.bench_version("harness"),agent.bench_version("http"),
		"a harness row and a direct row are not measured the same way")
	xtest.equal(agent.bench_version(),agent.bench_version("http"),
		"the direct path's fingerprint is unchanged")

def test_the_whole_mapping_reads_an_opencode_2_session():
	"""One session, in opencode 2's shape, through to the trace the gates read."""
	events = [
		{"type":"step_start","part":{}},
		{"type":"tool_use","part":{"tool":"edit","state":{"input":{"filePath":"/sandbox/app.py"},
			"status":"completed","output":"wrote"}}},
		{"type":"step_finish","part":{"reason":"tool-calls","tokens":{"input":1200,"output":300,
			"reasoning":0,"cache":{"read":9000,"write":0}}}},
		{"type":"text","part":{"text":"Fixed it and checked.\nSTATUS: done\n"}},
	]
	saved = transport.harness_stream
	transport.harness_stream = lambda model,prompt,workdir,timeout: (events,
		{"returncode":0,"timed_out":False,"stderr":""})
	try:
		with tempfile.TemporaryDirectory() as sandbox:
			raw = agent.run_episode_harness({"id":"m","provider":"zen","transport":"harness"},
				"fix it",sandbox)
	finally:
		transport.harness_stream = saved
	xtest.true(raw["finished"],"the session ran to completion and said something")
	xtest.equal(raw["status"],"done","the model's own declaration is read")
	xtest.equal(raw["usage"],10500,"the tokens are counted from the fields v2 carries")
	xtest.equal(raw["n_turns"],2,"the write and the finish are both turns")

def test_a_shell_event_with_no_exit_code_makes_the_run_a_hole():
	events = [{"type":"tool_use","part":{"tool":"bash","state":{"input":{"command":"python3 check.py"},
		"status":"completed","output":"all 5 cases pass"}}}]
	saved = transport.harness_stream
	transport.harness_stream = lambda model,prompt,workdir,timeout: (events,
		{"returncode":0,"timed_out":False,"stderr":""})
	try:
		with tempfile.TemporaryDirectory() as sandbox:
			xtest.raises(transport.UnseenShape,
				lambda: agent.run_episode_harness({"id":"m","provider":"zen","transport":"harness"},
					"fix it",sandbox))
	finally:
		transport.harness_stream = saved

def test_a_verification_after_the_last_write_is_visible():
	"""The gate that E26 made unreachable: a command that passed, after the last write."""
	events = [
		{"type":"tool_use","part":{"tool":"edit","state":{"input":{"filePath":"/sandbox/app.py"},
			"status":"completed","output":"wrote"}}},
		{"type":"tool_use","part":{"tool":"bash","state":{"input":{"command":"python3 check.py"},
			"metadata":{"metadata":{"exit":0}},"status":"completed","output":"all 5 cases pass"}}},
		{"type":"text","part":{"text":"Done.\nSTATUS: done\n"}},
	]
	saved = transport.harness_stream
	transport.harness_stream = lambda model,prompt,workdir,timeout: (events,
		{"returncode":0,"timed_out":False,"stderr":""})
	try:
		with tempfile.TemporaryDirectory() as sandbox:
			raw = agent.run_episode_harness({"id":"m","provider":"zen","transport":"harness"},
				"fix it",sandbox)
	finally:
		transport.harness_stream = saved
	runs = [t for t in raw["turns"] if t["action"] == "run"]
	xtest.equal(len(runs),1)
	xtest.equal(runs[0]["exit"],"0","the exit code reaches the trace")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
