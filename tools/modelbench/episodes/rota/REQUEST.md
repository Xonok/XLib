# rota — write the tests this library never had

I wrote this rota library by hand, and I trust the behaviour: the pay rules and the
schedule rules are what the office has been using. What it has never had is a test suite,
and I am about to change the internals, so I need one that would notice if I broke
something.

**Write the tests under `tests/`.** They must:

- **pass against the code as it is now** — a test that fails today is a wrong test, not a
	finding;
- **be a real suite, not one giant test** — at least six test methods, one per behaviour,
	so a failure says which rule broke;
- **catch a regression** — if I change one of the rules, at least one test must fail.

**Do not change the implementation.** It is correct by construction; if a test disagrees
with it, the test is wrong. `SPEC.md` states the rules and the worked examples.

Run `python3 -m unittest discover -s tests -t .` to check your work. `check.py` is the
acceptance check — do not edit it either.
