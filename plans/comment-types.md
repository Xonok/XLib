# Comment types

Standardize comment types by *visual pattern* so the purpose of a comment is
clear at a glance. Open item carried over from the style-guide split; settled
2026-09-06: the concern is the comment's looks, not metadata or review
markers.

## Why

When every comment looks like every other comment, a reader must parse the
text to learn whether it explains intent, warns about a pitfall, records a
decision, or marks a section. Distinct visual patterns let a reader skip the
wrong guesses: the purpose is declared before the words are read.

## Candidate types (to refine)

- **Why / narrative** — intent and background; e.g. header maps and the
  orchestrator comments in `style/common.md`'s Maps.
- **Pitfall / warning** — a sharp caution where a future reader will assume
  the wrong thing.
- **Decision rationale** — why X over Y; ties back to the spec's decisions.
- **Section marker** — structural label for long linear bodies (already
  sanctioned in `style/python.md`).
- **Non-literal marker** — TODO/FIXME/hack: must look temporary, stand out,
  and stay greppable.

## Keep separate

The bundler review's `%category` annotations (`%structure`, `%naming`,
`%bug`, `%question`, ...) are review-process tooling, not source comments.
They stay out of this plan.

## Decisions to settle

- How many types get fixed patterns; which live in `style/common.md` vs
  `style/<language>.md`.
- Pattern mechanism: leading keyword (`NOTE:`, `WARN:`), visual shape
  (alignment, leading marker, indent), or both.
- What an AI-followable rule looks like so generated comments follow the set.

## Status

Open. When settled, rules land in the style files; this plan then goes away.