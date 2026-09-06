# Typechecking system

Type system with custom type support; candidate to also serve as the schema library. Decision on merging is deferred but this plan assumes one library unless a reason to split appears.

## Goal

Check/validate data against types, where types can be built-in or user-defined. Works standalone and inside command-runner for automatic argument validation.

## Design direction

- A type describes data and knows how to check it: built-ins (str, int, bool, float, lists, dicts, optional, unions, enums...), plus a way to define new types (custom checker, likely with a declarative form).
- One honest answer for "check a value against type T" — used both for validation and (later) command argument parsing.
- Nested/recursive structures must work and give useful error messages ("which field failed, why").

## Merge decision (typechecking vs schema)

- Same library `typechecking` covers: describe data, validate data, custom types, reusable in command-runner.
- If merging: "schema" is just the name given to a composed type used for describing whole documents.
- If splitting later: the type layer is shared, schema composes types plus serialization concerns (CSV/logdb round-trips).
- logdb and command-runner will assume whichever interface wins — decide during phase 1.

## Consumers

- command-runner (validate incoming args, build help from type descriptions)
- logdb (schema-described config)
- CSV (stringly-typed checkers as custom types, if useful)
- testing (the library could drive assertions)

## Type declaration friction

Custom types are declared by importing them. When a type only matters to one
function, the import cost tempts authors back to expressing types as default
arguments (which standard tooling does not understand). A global type registry
— types usable by name without an import — would remove that friction if it
can be designed without scope leakage. Candidate, not decided.

## Order

Phase 1 item 3 (skeleton first; the requirements from consumers later).

## Refinement: three validation modes + error collection

xschema is runtime checking for untrusted data (network, disk, version-skewed
or unmigrated inputs). Refine it around three distinct modes.

### Modes

1. **Boundary decorator (exceptions).** Reject bad function inputs at
   explicitly chosen boundaries — not all the time. A decorator wraps a
   function so its parameters validate on entry. Raises (fail fast, call
   does not proceed). This is the existing `@schema.validate` shape; keep it.
   Decorators are opt-in per function by design: only edges the author trusts
   to receive hostile data pay the cost.

2. **Standalone validator (error list, never throws).** The same types also
   expose a plain callable: `errors(value, spec) -> list[ValidationError]`
   (empty = pass). Convenient for validating data that arrived separately
   from a function boundary (loaded doc, network payload).

3. **Read-then-validate (decoupled).** Reading data from disk/network never
   involves type errors — load into plain structures (json.load, csv, ...),
   validate as a separate explicit step afterwards. The library provides the
   validate step; it does not wrap readers.

### Error collection semantics

One error unit: `ValidationError(path, message)` (already exists; path already
formats to `person.age`, `[1][1]`). Single mandatory rule:

> An error on a field stops further examination **of that field only**.
> Neighbouring fields are still checked independently.

So a missing field, a wrong-type field, and an out-of-range field in the same
document each produce their own error with their own path; they do not mask
each other. "Stops deeper examination" means we do not recurse into an
already-failed node (no cascade of inner errors from a structurally broken
container). Siblings continue.

Both a single `check` (raise-first, used by mode 1) and the collecting journey
(mode 2) share one traversal; raise-first simply emits the first collected
error. Do not add a second validation code path.

### Type name resolution (global registry)

Decorator/spec arguments should resolve type names through the existing
`REGISTRY` so a type is usable by name without an import — the standard
solution to the "Type declaration friction" above, without polluting
`builtins`. This keeps the registry as the one name source for both
validation modes and for command-runner argument metadata.

### Sequencing

- Phase 1: error collection (`errors()`), shared traversal, tests for the
  sibling/stop-point rule.
- Phase 2: decorator (existing `@schema.validate`) kept as mode 1; registry
  name resolution for spec strings.
- Phase 3: read-then-validate example (json/csv), ensuring no type checks
  leak into the load step.