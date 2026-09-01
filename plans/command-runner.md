# Command runner

Command dispatch that plugs into the server framework (POST requests) and the websocket library. Integrates typechecking for arguments, and owns sessions.

## Goal

Write a command once as (name, description of arguments via types, handler); the library turns it into an endpoint on HTTP and a message type on websocket with validation for free.

## Design direction

- Command = name + declared parameters (types) + handler. Same declaration powers POST dispatch and websocket dispatch.
- Typechecking does input validation and can generate human/help descriptions.
- Sessions live here (decision recorded): a session = stateful context attached to a client connection with (auto) cleanup. Needed because websocket is long-lived and POST needs auth-ish continuity.
- Result serialization is pluggable (JSON default; CSV if/when relevant).

## Transports

- Server plugin: map `POST /<command>` → validate → run → return result.
- Websocket plugin: incoming message with command name → same pipeline.
- A connection can host commands over either transport without duplicates.

## Depends on

- server-framework (plugin mounting)
- websocket (message transport)
- typechecking (arg validation, help)
- optionally csv (dense responses), testing (of the runner itself), logdb (session persistence later)

## Sessions

- Created per connection/login as configured; held in memory at first (persist via logdb only if asked).
- Cleanup on disconnect/timeout must be explicit, not leaked threads.

## Order

Phase 3 item 12 (needs server-framework, websocket, typechecking).

## Out of scope for v1

- Async scheduling / long-running command interleaving.
- Permissions matrix beyond per-session identity.