# METHOD — how to get a measurement you can still believe later

This file is the part of the model benchmark that is not about models. It is what a caller
has to do for the numbers `episodes_run.py` prints to mean anything, and it generalises to
any harness that measures an agent you cannot interview afterwards.

It was written after a day in which a benchmark was changed six times and every earlier
result was invalidated each time. Every rule below is one of those six.

## Measurement is not evaluation

- A **measurement** is one run of a benchmark at one time. Its validity is the whole game.
- **Evaluation** is processing many measurements into conclusions. It is long-term, it is
		where the meaning comes out, and it changes freely.
- A benchmark that measures well can turn out to be measuring something you did not want.
		**That is an evaluation problem, and it is fixed by adding a benchmark, never by changing
		one.**

## Change a benchmark only when it is wrong

**Changing a benchmark is the same act as deleting it and building a new one.** A benchmark
that was changed has nothing to do with the results older versions of it produced, so every
result already collected is lost, silently, at the moment of the edit.

- Reserve a change for a **bug** — something that makes a result which is not a measurement.
		A wrong prompt, a parser that drops a turn, a checker that reports a failure as a success.
- **Not** a reason: a new idea, a better metric, an uncomfortable result, or a benchmark
		turning out to be less useful than intended. Useless is still kept — it may be the useful
		one later, and deleting it destroys information.
- **Adding** a benchmark is always allowed. More measurements, clearer constraints.

### The rule that matters more than all of the above

> If benchmarks turn out wrong too often, the process for developing them is wrong and not
> trustworthy.

**The rate of defects is itself the finding.** Treat N defects fixed as good news only if N
was expected. Repeated surprise at the instrument means the instrument's development process
is what is under suspicion — not the latest bug.

## Fingerprint by content, never by hand

Each record carries `bench_version()` and `grade_version()`, both **hashed from the files
that define the measurement and the scoring**. A constant is forgotten; a hash cannot be.

The consequence is the point: a record written before a prompt edit **visibly disagrees**
with one written after it, so any comparison is either valid or obviously not. A hand-kept
version number gives you neither — it says whatever you last remembered to say.

`bench_version` covers the measurement side (protocol, episodes, parser); `grade_version`
covers the evaluation side (gates, grades). The split tells you the cost of a change before
you make it:

| Changed | Earlier results |
|---|---|
| the measurement side | **invalid** — the model was measuring something else |
| the evaluation side | **re-derivable** — the stored trace is still a measurement |

### The mapping is part of the measurement

The **mapping** is the code that turns a model's output into the trace the gates read. It
is as much a part of the measurement as the prompt is, so **its source is folded into
`bench_version`**.

It was not, and that is what let the opencode-2 upgrade break the harness path twice
(E19–E22, then E26–E27) without anything being supposed to notice: every harness row
measured under the broken mapping had to be thrown out and re-measured, because the thing
that had changed was not in the fingerprint.

**There is one mapping per transport, and the two fingerprints are independent.** A change
to the harness mapping does not move the direct path's fingerprint — otherwise every
finding the direct corpus carries would be invalidated by a change to a path it does not
use, which is the same mistake pointed the other way. The two mappings are not the same
shape, because the two paths are not: the harness path's input is opencode's *event
stream*, which is the instrument's own reading of what the model did, so the whole harness
transport is inside it; the direct path's input is the model's *reply text*, which is the
model's own words, so the mapping starts at the text.

A row also carries `mapping_version` — the mapping's own hash, alone — so a reader can
tell that the mapping moved the grades and not the prompt. A row measured before the
mapping was hashed carries none, and that is a fact about the row rather than a verdict on
it: the corpus's own per-model pages already say to treat those figures as a result on the
previous measurement.

The list of what the mapping is has to be kept honest, or the hole reopens with a lid on
it: a function added to a path and left out of the list would move the grades without
moving the fingerprint again. A test walks the call graph from each path's runner and
says what is missing.

## Store the raw data, or it was not a measurement

**A result that cannot be re-derived from stored data is a sample.** The cheapest possible
rule, and the one whose absence is hardest to notice:

- **Raw first, analysis second.** The record must carry the full turn list, plus whatever
		the subject said in its own words, so a scoring change is a script run rather than a
		re-measurement.
- **Keep the final on-disk state** beside the trace. Deleting it is what makes a broken run
		permanently undiagnosable.
- **Never write traces to `/tmp`.** It is wiped on reboot. This is not hypothetical: a
		quarter of one day's conclusions was lost exactly this way, and could never be re-audited.
		One directory per run wave, log beside the JSONL.
- **Never edit or delete a trace.** Corrections are new records beside old ones, and a
		superseded reading is named rather than overwritten.
- **Storage is cheap; silent loss is the risk.** A week of traces is under a megabyte. That
		is not a reason to compress, aggregate or prune, and pruning is a recorded decision with a
		stated reason, never housekeeping.

### Three parts, kept apart

The work here has three parts, and the point of keeping them apart is that **a benchmark can
be built later over measurements already collected**:

| | What it is | Where it lives | How it changes |
|---|---|---|---|
| **Measurement** | the actual run: the prompt, the turns, the model, the settings, the timestamps, the raw output, the final state | the record's `trace` block | a new run |
| **Benchmark** | the bar: the episode, the checker, the gates, the ladder | `episodes/`, `trace.py` | `bench_version` moves — earlier results are invalid |
| **Evaluation** | the synthesis: what the measurement means against the bar | the record's gates, grade and detail; the ledger | `grade_version` moves — earlier results are re-derivable |

**The measurement is the part that has to stand on its own.** It must not depend on the
benchmark or the evaluation being the way they are today, because the point of storing it is
that somebody can look at it later and ask a question the present benchmark does not ask. So
the record carries: the prompt as the model saw it, every turn whole, the model's own words,
the provider's own response, the settings, the timestamps, the hash of the episode content
it ran against, and where its final state is kept.

**Nothing stored is cut short.** The reply used to be truncated at 1500 characters and the
tool output at 400, and the cut was not harmless: the checker's own verdict is the evidence
for G2, and a report longer than 1500 characters is most of a report. The human's rule, and
it is the safe default: **keep as much data as possible. Deciding that some data is
irrelevant can easily be done after the fact, but the reverse is impossible.**

**And much of it can be restored from elsewhere.** opencode keeps every session in its own
database — the prompt, the reasoning, the tool calls and their outputs — so a record that
names its session can have its raw data restored, and a record can be joined to one. The
copy in the record is still kept: the database is on one machine and the corpus is in git.

## The instrument's defects are not findings about the subject

**A harness failure is a hole in the run, never a finding about the model.** This is the rule
that exists because the alternative has repeatedly manufactured evidence *against* a subject
that never did anything wrong.

The worst version of it, kept here because it will happen again: a checker that builds its
cases at module import can be killed by an ordinary edit from the subject, then reports zero
cases — which, read as a score, is a subject that failed every single check, with a long list
of broken guards as the evidence.

Therefore, on every run, before quoting anything:

- **Is the case set non-empty?** A zero-length result is a hole, not a score of zero.
- **Is the turn count non-zero?** A run that produced nothing is not a bad run.
- **Is there a declared verdict?** If the grade accuses the subject of overclaiming, the
		accusation must be checkable against its own words.
- **Was the result actually produced by the harness**, or by a rate limit, a timeout, or a
		parser that gave up? All three are holes, and all three are manufactured by whoever ran it.

Keep the catalogue. Entries accumulate, including the false alarms, because a defect class you
have seen once will come back wearing a different ID.

## Two checks on anything that is supposed to know

- **A negative probe is not evidence of absence.** A transport-level availability check
		false-negatives some models, and it will happily contradict a real run made hours later on
		the same day. Only an actual measurement counts. A column fed by probes is worse than no
		column: it looks authoritative.
- **Check a new checker three ways** — it must fail on the broken input, pass on the correct
		fix, and fail on the *careless* fix. Better still, never hand-type the expected values:
		derive them from an independent reference implementation written deliberately differently
		(other arithmetic, another traversal order) and cross-check every literal. A hand-written
		ground truth is wrong often enough to be its own error class.

## Aggregate at read time, never into a document

Count a corpus from its stored records every time it is read. A count typed into a document
is a count that will be stale, and the day it is wrong nobody will know which of the two
sources to trust.

**Publish counts from one generated index, not from six prose files.** `ledger.py` builds
one row per run and renders the table; a new measurement should cost an append to the index
and nothing else. If it also requires rewriting prose in several places, the prose is where
the numbers leaked, and it will drift again — the failure mode is invisible precisely
because each individual document looks well-sourced.

**Keep the results somewhere the tool does not reach.** The instrument belongs in the shared
library, because that is where it can be reused. The corpus does not: it is mutable, it grows
without bound, and it is specific to one project's criterion. Keep the two apart and pass
paths at the command line rather than hard-coding either, so a caller is never required to
have anything of yours in order to run the tool.

## When a scoring change cannot be applied to data you already have

**The storage is wrong, not the change.** That single sentence is the whole reason to keep
raw turns: it is the difference between fixing a gate in an afternoon and losing a day of
measurement to the same defect.
