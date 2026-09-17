# Dnd math

Math for dice and similar roleplaying mechanics.

## Goal

A small library for dice rolls and related random math: `roll("2d6")` → result, plus nicer pieces for the game logic layer.

## Design direction

- Parse dice notation: `NdS` (count, sides), modifiers (`2d6+3`, `1d10-2`), maybe rerolls/exploding dice as explicit features.
- `random.SystemRandom` (crypto-strong) unless there's a reason for seeded/reproducible rolls — decide.
- Return roll breakdowns (per-die results + sum) so callers can show or manipulate them, not just totals.
- Related helpers: average/expected value, min/max, drop highest/lowest (common DnD patterns).

## Consumers

- loot-tables (rolls during generation)

## Order

Phase 1 item 6. Leaf library; nothing depends on it before loot-tables.

## Out of scope for v1

- Probability distribution analysis (beyond EV).
- Any simulation/encounter logic — that's project code.