# Loot tables

Loot table generation with recursion support and heavy configuration.

## Goal

Define a loot table declaratively (entries, weights, amounts) and roll it; entries may reference other tables (recursion), with depth/cycle guards.

## Design direction

- Table = declarative data: entries with weights, each entry being an item, another table reference, or a sub-roll.
- Recursion: an entry can point at another table (including itself via cycles at runtime) — depth limit and cycle detection needed.
- Configuration via plain data (dicts) so tables can come from files/config, not code.
- Uses dnd-math for rolls (weighted picks).
- Nested rolls for quantities: entry has a count (`1d4` gold, "2 × entry").

## Depends on

- dnd-math (rolls, weighted selection)

## Order

Phase 3 (after dnd-math; otherwise independent of the server stack).

## Open questions

- Result shape: flat item list vs tree (keep provenance of which table produced what)?
- Deterministic mode with a fixed seed for testing/reproducible generation?