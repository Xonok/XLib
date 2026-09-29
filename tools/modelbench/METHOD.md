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
