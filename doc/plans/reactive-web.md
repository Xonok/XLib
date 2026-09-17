# Reactive web framework (JS)

JS toolkit for data dependencies: declare data and the code that depends on it; when data changes, the dependent code runs.

## Goal

A small reactive system in JS used by webapp views: track state, subscribers auto-update on change, minimal API (no full framework).

## Design direction

- Reactive primitives: reactive value/cell (read gives current value + subscribes the caller), computed values (depend on cells, recompute on invalidation), effects (run code and re-run when its dependencies change).
- Dependency tracking done by reading inside computations/effects — classic reactive model (no manual subscribe calls).
- Minimal and library-shaped (matches the XLib style: small, composable, no framework bloat).
- Web delivery: consumes webapp's lazy JS loading; also usable standalone as a JS file.

## Consumers

- webapp views (UI state, updates)

## Order

Phase 4 item 14. Independent of the Python pipeline; can start before webapp (build-order.md notes this).

## Out of scope for v1

- Rendering/DOM framework, routing, SSR. It's a dependency-tracking toolkit, not a UI framework.
- Persistence of state (that's the project's job, or a server via websocket).