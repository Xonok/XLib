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

## Order

Phase 1 item 3 (skeleton first; the requirements from consumers later).