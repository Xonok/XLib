# patch — review the change set before I merge it

`CHANGES.diff` is a change set against `patchlib`. It adds a word count and touches the
tokenizer, the slug rule, truncation and the two statistics helpers. I wrote the tests
that come with it, and they pass — but they were written by the same person who wrote the
change, so a passing suite is not a review.

**Review the change set against `SPEC.md` and write your findings to `REVIEW.md`.**

One finding per line, in exactly this form:

```
FINDING: <path>:<line> — <one sentence saying what is wrong>
```

`<path>` is the file in the change set (`patchlib/stats.py`), and `<line>` is the line
number **in the changed file** — the line a reviewer would point at in a code review.
Only report things that make the change set wrong against the spec. Do not report style
preferences, missing tests, or ideas for other features; a finding that is not a defect in
the change is a false positive and counts against the review.

**Do not edit the code or the tests.** This is a review, not a repair; if something is
wrong, say where and why. `check.py` is the acceptance check — do not edit it either.

You may run the project's tests if you want; they pass, and that is not the answer.
