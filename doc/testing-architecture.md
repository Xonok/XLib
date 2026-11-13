# Testing Architecture

How a test is built in this repository. This file is the rule. The argument for
the shape — the alternatives and what each one fails to establish — is reference
material kept outside this repository, not policy. What is here is the how, with
as much why as a rule needs to be judged in a case it did not anticipate.

## The shape

A test is four parts, and each part owns one job:

```
driver (impure)  →  observation (a value)  →  judge (pure)  →  cases (data)
```

- **Driver** — builds the situation: creates the world, ticks it, opens the
	socket, loads the file. It owns everything impure, and it asserts nothing.
- **Observation** — what the run produced, as a value that could be written to a
	file or printed: a snapshot, an event list, a parsed document. It holds no
	handles into live state.
- **Judge** — a function from observation to verdict. It is pure and total: it
	reads only the observation, and it returns a verdict for any observation it is
	handed. An empty verdict is a pass; each entry names an invariant that failed.
- **Cases** — checked-in data. A case is an observation and the verdict it must
	produce. A case whose expected verdict is not empty is a red case.

The observation is what makes the other three work. Because the judge sees only a
value, a case can hand it an observation from a real run or one fabricated to be
wrong. Because the judge never sets up, a failure has one possible cause.

## Rules

**The judge returns a verdict; it does not raise.** An empty verdict is a pass,
and each entry names the invariant. A judge that raises cannot be told apart from
a case whose setup was wrong, and an expected exception is only as precise as the
exception. A verdict is data, so the case can state exactly which verdict it
wants.

**The judge is total.** It returns a verdict for malformed, empty and truncated
observations too. A judge that assumes well-formed input can only be reached
through the driver, and then its cases cannot be fabricated.

**The judge never builds the situation.** If it needs a value, the value belongs
in the observation.

**The judge checks the spec, not the code.** Constants, orderings, counts,
conservation, round trips, exact values from the requirement. A judge that
recomputes the implementation's formula is a replay, and a replay agrees with the
bug.

**The driver asserts nothing.** A driver failure is a harness fault, not a case
result, and it must not be reported as one.

**The observation carries everything the judgement needs.** A judge that has to
read a live object, re-run the code or consult the clock has an observation that
is too thin. Widen it.

**Every case states its expected verdict, and red cases are checked in.** The
expectation lives with the case; the same judge runs against passing and failing
observations unchanged. A red proof is a case, not a run: a transcript of a run
that has since been discarded is not evidence that anything fails.

**Red is per case, never per suite.** A red run over a whole suite says nothing
about an individual test — a vacuous test passes while the others fail around it.
The unit of proof is the case.

**A failure is pinned to a named verdict.** "It raised" is not a result. A case
that accepts any failure is `except: pass` with a comment claiming it is
handled.

**A requirement with no observable difference is rewritten.** If no observation
separates the required behaviour from a plausible wrong one, the requirement is a
wish. Either the observation grows or the requirement does.

**Invariants are preconditions, not requirements.** "It builds", "it runs", "the
gate passes" hold for every test. Each gets one check at the harness level, and
none gets a case per behaviour.

**Where the input domain is real, cases come from it.** Files, wire bytes, maps,
scores: capture the inputs that exist rather than inventing examples. A captured
case is one nobody wrote to match the judge.

**A wrong implementation that passes means the observation is too coarse.** If a
plausible wrong implementation produces an observation the judge accepts, either
the observation cannot see the difference — widen it — or the behaviour is
internal, and then it is not observable and not a red-green requirement.

## Worked example

```python
# Driver: impure, no assertions.
def drive_aligned(ticks = 10):
	w = make_world(ALIGNED_SHIPS)
	for _ in range(ticks):
		tick(w)
	return {"ships": snapshot(w), "events": list(w.events)}

# Judge: pure and total, returns the violated invariants.
def judge_beam_hits_first(obs):
	first, behind = obs["ships"]
	bad = []
	if first["hull"] == first["hull_max"]:
		bad.append("first ship not hit")
	if behind["hull"] != behind["hull_max"]:
		bad.append("beam passed through to the ship behind")
	return bad

# Cases: the expected verdict is data. The red ones are fabricated observations.
RUNS = [
	("aligned, beam fires", drive_aligned(), []),
	("first ship untouched", {"ships": [FULL, FULL], "events": []},
		["first ship not hit"]),
	("beam passes through", {"ships": [HIT_FIRST, HIT_BOTH], "events": []},
		["beam passed through to the ship behind"]),
]

for name, obs, expected in RUNS:
	got = judge_beam_hits_first(obs)
	if got != expected:
		raise AssertionError(f"{name}: {got!r} != {expected!r}")
```

The two red cases need no mutation and no temporary copy; they are the same judge
given observations a broken implementation would produce. When a red case cannot
be written, that is the signal that the observation is too thin — not that the
behaviour needs a mutation instead.

## Applying it

New tests are written in this shape. Existing tests migrate when they are
touched; the tests already in the old shape are not a reason to add more.

- **Timing is not an observation.** A case that asserts "fast enough" belongs to
	the benchmark, which has its own gate and its own noise rules.
- **A judge that needs another case's state is two cases.** Cases are independent
	of each other, not merely run independently.
- **One judgement per case, compared exactly.** This replaces "one assertion per
	test": the case is what must name one thing, and it names it by the full verdict
	it expects.
