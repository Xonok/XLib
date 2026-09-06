# Full code analysis plan

Deploy full code analysis tooling — a step beyond xlint's style rules. SonarQube
is one candidate; others may be better in some ways. Status: needs discussion.

## Context

- Silent AI-code failures (compile, run, pass tests, still subtly wrong) need
  catching beyond the human review. A full code analysis tool catches many
  such issues mechanically.
- Earlier thread (2026-09-06): long-term want = type checking *without running*
  too, but that need may be served better by a full code analysis tool that
  also catches many other issues.
- Current state: `xlint` only (style checks; see `xlint/`). The typechecking
  plan (`plans/typechecking.md`) is runtime validation of data, not static
  analysis of source — separate concern.

## Candidates

- **SonarQube** — full self-hosted server (needs a DB + JVM), broad rule set
  across many languages, web dashboard, quality gates. Heavy; likely overkill
  for this repo size, but the canonical "full analysis" reference point.
- **ruff** — Python only; fast, zero-config, thousands of rules (pyflakes,
  pycodestyle, bugbear, PLUS selectable plugin families), also a formatter.
  Lightweight, CLI-friendly, trivially added to the release/lint loop.
- **pyright / mypy** — static typing; pyright has better inference, no runtime
  cost; mypy needs install/complex config. Pairs with the type-hint rules in
  `style/python.md`.
- **semgrep** — pattern-based rule engine; catches cross-file/local patterns,
  not just per-file style. Useful once there are project-specific bugs we want
  to ban.
- **bandit** — security-only (Python). Narrow; probably not needed given
  repo scope.

## What needs discussion

- Server (SonarQube) vs. lightweight CLI (ruff family): weight, integration,
  and whether a dashboard is wanted at all.
- When it runs: pre-release gate, per-session, or CI/once-in-a-while — must not
  block ongoing development (project constraint).
- Rule-level fit: which rule families actually catch XLib-silent-failure-class
  bugs (unused names via mangling? wrong defaults? shadowed scopes?) rather
  than reconfirming style rules xlint already enforces.
- Interaction with the legibility pass (`style/common.md`) and the bundler:
  analysis runs on the dev folder, before or after bundling?
- Whether static typing (pyright/mypy) should ride along with this or wait for
  the runtime typechecking library to define its types first.

## Open questions for the other agent

- What does xlint currently *not* check that a real analyzer would catch on
  this codebase today (run something like `ruff` read-only over `xlib/`,
  `tools/`, `pybundle/`)? That list is the concrete payoff for the discussion.
- Which of these fit the workspace constraint "no pip packages installed /
  no new heavyweight deps"?