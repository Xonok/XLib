# Python style

Rules specific to Python. Read `style/common.md` for the language-independent
rules; this file only adds Python-specific rules.

## Formatting

- Code is indented with tabs.
- Function definitions and calls stay on one line. A definition that cannot fit is
	avoided; when it is unavoidable the spill becomes ordinary indentation, not
	alignment — arguments on separate lines one tab deeper than the `def`, and the
	closing `)` on its own line at the `def`'s own indent (`BSFQYPF`).
- No double newlines; one blank line separates functions; related globals stay
	together as one block.
- Methods within a class have no empty lines between them.
- A file ends with exactly one newline, after real content: no trailing blank line,
	and no missing final newline (`BX56XRY`).
- No trailing whitespace.
- A mid-line double space is a typo. Use one space between tokens and after commas.
- Prefer concise code, but do not make it complicated just to be concise.
- Use intermediate variables to break up complex logic; use spaces to break
	math into simpler parts, and don't pad spaces as a blanket rule.

## Imports

- Imports go on one line: plain imports are comma-joined
	(`import argparse,ctypes,os`), names from the same module are comma-joined
	(`from X import Y,Z`), no space after a comma. Dotted names get their own
	line, and so do aliased ones (`import os as o`) — they are avoided where the
	plain name is clear enough.
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
- **API functions (public entry points) MUST have type hints on all parameters
	and return values.** Internal code only needs them where the name doesn't
	carry the type or the contract is non-obvious.

## Comments

- A comment goes on the line immediately before what it explains. A comment on the
	same line as a `def` or a `class` is not allowed at all; it goes above (`HRCQSV4`).
- Comments are for why, not what or how. What and how are the code's job, and a
	comment restating them is a second copy to fall out of step.
- An inline comment on ordinary code is allowed only where a run of consecutive
	lines each carry one, so there is a column to read. That is rare, and rare for a
	reason: only "why" comments exist to be inlined, and most code has no "why" to
	record next to it. Where the run exists, the comments are one space from the
	code unless there is the column to line up against (`BSFQYPF`).

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

## Docstrings

- Module docstrings are prose: a short description of what the module provides,
	followed by a blank line, then any context a caller needs. No structural
	markers (`Args:`, `Returns:`) — those are for functions.
- Function docstrings follow the same principle: one prose paragraph describing
	what the function does and why it exists. If parameters or return values need
	explaining, write it in prose; avoid `Args:`/`Returns:` sections unless the
	contract is genuinely non-obvious.
- No alignment columns in docstrings. If a run of consecutive lines each has an
	inline comment, the column rule from *Comments* applies; otherwise, one space
	from the code.
- Docstrings are not exempt from the alignment rule: spaces are never used for
	alignment anywhere in this repo (`BSFQYPF`).
- Class docstrings describe what the class represents, not a list of methods.
- Private (`_*`) functions and classes do not require docstrings; their names
	are the contract.
