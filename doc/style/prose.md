# Prose style

Rules for how an agent explains technical things to the human. `style/common.md`
covers legibility of the code itself; this covers the explanation of it.

## Why this file exists

Technical explanations fail in one specific way: every word is correct and the
whole thing doesn't correspond to anything. That happens when the explanation
describes what code of that shape usually does instead of tracing the code in
front of it, and skips the intermediate states it assumes are obvious. Nothing
is wrong at the word level, so the result reads as plausible and is useless.

Ordinary prose survives a skim; a correct explanation of code is a chain with no
slack in it, so one inferred step turns everything after it into decoration. The
fix is to make the explanation checkable against the artifact — a claim that
can't be checked is a claim that can't be trusted.

## Cite identifiers

- Name the actual function, variable, file and line: `read_all` appends to
	whatever `_cursor` already held; it doesn't reset it.
- A claim with no identifier behind it is a description of a category of code,
	not of this code.

## Trace, don't summarize

- Step through and show the value at each step. The states that look obvious are
	the ones the reader cannot check, and they are the reason they asked.
- A summary is acceptable as a follow-up to a trace, never instead of one.

## Mark inference

- Say which parts you read and which you inferred. Unmarked inference is
	indistinguishable from a wrong reading, so the reader cannot tell what to
	check.
- "I inferred this from the usual shape of such code" is a normal thing to
	write. Concealing it is the defect.

## Make it falsifiable

- State what would have to change for the answer to differ. "If the caller
	passes an empty list, this branch never runs" can be checked in one read;
	"it handles the edge cases" cannot be checked at all.
- An explanation with nothing falsifiable in it has not been verified against
	anything.

## Answer the question that was asked

- "What does this do" means this file, this function, in the context of its
	callers — not what this kind of function usually does.
- If only part of it got answered, say which part, and what is left.

## Which model explains

- Explanation work goes to a model that reasons step by step. A small model
	asked to explain a chain will narrate a plausible conclusion instead, and no
	prompting makes that traceable. The dispatch table is in `AGENTS.md`; the
	small workers listed there are for bulk and repeated work.
