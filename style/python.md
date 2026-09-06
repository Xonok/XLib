# Python style

Rules specific to Python. Read `style/common.md` for the language-independent
rules; this file only adds Python-specific rules.

## Formatting

- Code is indented with tabs.
- Function definitions and calls stay on one line.
- No double newlines; one blank line separates functions; related globals stay
  together as one block.
- No trailing whitespace.
- Prefer concise code, but do not make it complicated just to be concise.
- Use intermediate variables to break up complex logic; use spaces to break
  math into simpler parts, and don't pad spaces as a blanket rule.

## Imports

- Imports go on one line: plain imports are comma-joined
  (`import argparse,ctypes,os`), names from the same module are comma-joined
  (`from X import Y,Z`), no space after a comma. Dotted names get their own
  line.
- One statement per line (no `;`); no blank lines between imports. Imports
  from meaningfully different categories (stdlib vs repo-local) are separated
  without an empty line between them.
- No wildcard imports.

## Naming

- If exactly one variable of a type (as the domain understands the type) is in
  scope, its name is exactly the type: `lines`. With several of the type, add
  a qualifier after it: `path_config`, not `config_path`.
- Keep names chunk-readable: the stable prefix (usually the type) comes first,
  then the distinguishing part, so similar names align and read as groups
  (`ship_hp_max_this` / `ship_hp_min_this`).
- Prefer descriptive over single letters where meaning isn't obvious
  (`line_len` over `n`); `i`/`j`/`n` are fine as true iterators and counters.
- Name things for what they are or return, not a vague idea of what they do.
- Internal helpers start with `_`, so they're distinct from the API surface at
  a glance.

## Type hints

- Types are marked as type hints, never as default values
  (`def f(config: str | None = None)`, not `def f(config=None)` to mean "str").
  Defaults-as-types hide information from standard tooling even when a human
  reads the intent.
- A default value that already expresses the type makes the hint unnecessary:
  `def f(sep=",", sort_order="ascending")` needs no annotations.
- Optional arguments are a different case: they change how the function works,
  so `None` is a meaningful option, not an absence of a choice. Those get
  explicit hints (`config: str | None = None`).
- Annotate where the name doesn't carry the type or the contract is
  non-obvious; boilerplate annotations everywhere are overkill.

## Imperative shape

- Guard clauses per `style/common.md`.
- Avoid long functions when possible. The tipping point: does the body read
  naturally as one linear sequence, or as several functions composed together?
  If it composes, split it. A genuinely linear sequence (hand-built tables,
  state machines) stays long and is broken into titled sections: one short
  comment naming the section, not narrating the code.

## Declarative where it reads well

- Use comprehensions, `enumerate`, `zip`, `itertools` when they read as one
  chunk; don't force them where a plain loop reads clearer.
- Conditional expressions (`a if b else c`) read worse to this reader than
  JS's `b ? a : c`; keep them short and simple, and prefer an early return or
  a plain `if` for anything longer.