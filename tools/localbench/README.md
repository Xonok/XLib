# localbench — measure local models as shell calls

Runs `xprompt` against short, deterministic task fixtures and records what the model did.
This is the instrument for the on-machine pool in `Agents/library/ai/local-models/`; it is
deliberately **not** `modelbench`, which measures trust inside a large agent loop. Here the
call is small state in, short answer out, at most a few tool turns — the shape a local model
is actually fast enough for.

## Running

```sh
python3 tools/localbench/run.py \
	--model qwen2.5-3b-opt --repeats 2 \
	--out /path/to/runs/2026-10-30-pilot \
	--option num_ctx=8192 --option num_thread=4
```

Options that matter: `--task FAMILY` and `--case NAME` narrow the suite, `--xprompt PATH`
chooses the binary (default `$XPROMPT`, then `$XLIB/tools/xprompt`, then `xprompt`), `--host`
drives a second Ollama server, `--think` enables thinking (default off), `--keep` keeps the
sandboxes, `--no-final` skips the stored final state.

Every invocation warms the model once with the same host/options/think as the runs, because
a cold load otherwise lands inside the first scored call.

## The task format

`tasks/<family>/<case>/` holds:

| File | Meaning |
|---|---|
| `task.json` | `family`, `case`, `kind` (`stdout` or `state`), `prompt` or `prompt_file`, `tools`, `max_turns`, `timeout_s`, `options`, `verify_command`, `note` |
| `fixture/` | copied into a fresh sandbox for each run |
| `check.py` | the deterministic checker; reads `LB_STDOUT`, `LB_TASK_DIR`, `LB_META`, prints one JSON object and exits 0/1; **exit 2 means the checker itself failed** |
| `reference.txt` / `reference/` | a known-good answer or state |
| `broken.txt` / `broken/` | a deliberately wrong answer or state |

**No task is usable until `selftest.py` is green**: the reference must pass, the broken
state must fail, and empty output must fail. That is what makes a task's verdict mean
something — without it a model failing a broken checker looks like a model that cannot do
the work.

The checker reports two independent things:

- `ok` — the answer is right, read tolerantly (JSON may be fenced, an answer may be in prose).
- `contract_clean` — the output is directly consumable (whole stdout parses, exact shape, no
	preamble). A model can be capable and still unusable in a pipeline; both are recorded.

`verify_command` applies to `state` tasks: the run's `verified` is true when a `bash` call
matching that regex happens after the last `write` call. It records whether the model checked
its own work, not whether the work was right.

## What a run records

`<out>/<runid>/meta.json`, with `stdout.txt`, `stderr.txt` and `final/` beside it:

- identity: model, family, case, repeat, started, `bench_version` (hash of the task set and
	runner), `xprompt_sha256`;
- effective `options`, `tools`, `max_turns`, `think`;
- the shell contract: `exit_code`, `timed_out`, `wall_time_s`;
- the model's behaviour: `turns`, `tool_calls` with `source: native|parsed`;
- Ollama's own metrics: `prompt_tokens`, `eval_tokens`, `prefill_s`, `gen_s` and the two
	tok/s, from `prompt_eval_*` / `eval_*` in the final stream chunk;
- the checker: `ok`, `contract_clean`, `reason`, `detail`, `checker_error`;
- `verified`, `final_state_kept`, `xprompt_error`.

`bench_version` changes when a task file or `run.py` changes, so rows measured under
different instruments never look identical.

## Ledger

```sh
python3 tools/localbench/ledger.py \
	--runs /path/to/runs --out ledger.jsonl --markdown corpus.md
```

One JSON line per run, sorted deterministically; the markdown is one row per model × family.
`--check` re-runs every checker against the stored `final/` in a throwaway copy. A stored row
keeps its result: a disagreement means the checker changed, and that is a new instrument
version, not a rewrite of history. A run without `final/` is `state_missing`, not a
disagreement.

## Adding a task

1. Write the fixture, prompt and checker.
2. Write a reference that passes and a broken state that fails.
3. Run `python3 tools/localbench/selftest.py` — all three scenarios must be green.
4. If the task is deliberately fuzzy (a summary), say so in `note`; it is reported
	separately and never treated as a hard capability gate.

Fixtures are data, not project code: `.xlintignore` exempts `fixture/`, `broken/` and
`reference/`, because deliberately buggy files should not be forced into repository style.

## Tests

`python3 tools/test/test_localbench.py` — unit tests for the version hash, ledger grouping,
checker parsing and the state-missing path. No model required.

## Operations measurements

`ops.py` answers the other half of the question — speed, memory and concurrency:

```sh
python3 tools/localbench/ops.py --models m1,m2 --out DIR
python3 tools/localbench/ops.py --concurrency m1,m2,m3 --out DIR
```

The first warms each model, measures prefill/generation at roughly 100/1,000/4,000 prompt
tokens with a fixed 40-number answer, and records `/api/ps` size and VRAM after load. The
second warms the set, measures each solo, then three rounds of all models at once, recording
per-call wall time and load average. These are operating measurements, not capability scores;
they are kept beside the task ledger rather than in it on purpose.
