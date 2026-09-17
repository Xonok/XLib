# File handling

General file-handling helpers shared by several libraries.

## Goal

Safe, small utilities for filesystem work where libraries keep doing the same things (safe path joins, reading/writing, listing, root-constrained access).

## Design direction

- Safe path joining within a root (traversal protection) — directly reused by file-server.
- Read/write helpers (text/binary, create dirs, atomic-ish write).
- Listing/filtering files by extension, useful for webapp lazy views and testing discovery.
- Handling of the Write-tool/editor newline gotcha seen in this repo (files shouldn't silently lose trailing newlines) if it generalizes to a library concern.

## Consumers

- file-server (root-constrained access)
- logdb (append/rotate)
- webapp / testing (discovery, loading files lazily)
- release tooling possibly

## Order

Phase 1 item 5.

## Out of scope for v1

- Watch/file-change events (tmux-xlib's --watch is tooling, not a library feature yet).
- Compression (that's library-specific; server handles gzip).