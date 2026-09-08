# Log database

Log-based (append-only) database. Project-specific details are configuration via schemas, not code.

## Goal

Data is appended as records; the schema describes each record type; queries read the log. Logs are cheap to write and reviewable by hand.

## Design direction

- Append-only CSV log(s) as storage; schema (from typechecking) describes valid records and their columns.
- Project configures: which record types exist, their columns/types, and how to split or name log files — without editing library code.
- Reads: sequential scan at first (log DBs are naturally sequential); indices are a later concern.
- Built on xcsv + file-handling; schema via typechecking.

## Requirements

- Write a validated record (reject records that don't match their schema).
- Read records back with typing applied (not stringly-typed forever).
- **Fold / last-write-wins by key** — read the full log, return folded state where the last record for a given key (e.g., `task_id`) wins. This is a logdb concern, NOT an xcsv concern.
- **Key-value / sparse columns** — support records where different rows have different columns. Requires xcsv to allow "unfinished lines" (fewer fields than current schema) without error. xcsv needs an override to suppress the unfinished-line error; logdb uses this for KV rows.
- Multiple record types in one log or one log per type — decided by config.
- Truncate/rotate support (legacy CSV had a `truncate`; rotation by size/date as config).

## Depends on

- xcsv (tokenizer/serializer with comment support)
- file-handling (safe append, rotation helpers)
- typechecking (schema definitions, validation)

## Order

Phase 2 item 9 (as soon as xcsv + file-handling + typechecking land).

## Out of scope for v1

- Indices, transactions, crash recovery beyond append semantics.
- Delete/update (log DBs append; compaction via rewrite+rotate if asked later).

## Open questions

- In-memory cache of the tail for fast recent-reads?
- One file with headers per record type vs header-less config.