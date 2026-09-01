# File server logic

Static and file-serving behaviour, written as a plugin for the server framework.

## Goal

A server can serve files — but only the files it has explicitly allowed. Content types are correct, paths stay inside the served roots, and it composes cleanly with other plugins.

## Security: default is to serve nothing

- The default behaviour is to not serve any file that isn't explicitly allowed.
- Allowed files are determined by configuration (see Config), generally "by type" today — the config says which extensions may be served, and only those roots are reachable.
- Bypassing the default (e.g. "serve whatever is in this folder") must be an explicit, visible statement in the main function of the server that uses the library — not buried in config, not a flag the library defaults to true.

## Requirements

- Path normalization and traversal protection (sane checks on untrusted input, per AGENTS.md).
- MIME types from an extension mapping (stdlib `mimetypes` first; override map as needed) — this doubles as the "what can be served" gate.
- Compression of text-ish responses (gzip).
- Index file handling (serve `index.html` for a directory path) — decide whether this is core or opt-in.
- Missing files: proper 404 vs the plugin's own error page; must not collide with other routes (only claim paths it owns).

## Config

- Servable locations come from the config library: which served files exist and where. Currently this is typed (by extension/type); a way to serve whatever happens to be in a given folder is a useful addition on top of that.
- Config drives allow/deny so the security story is declarative and inspectable, consistent with the "explicit statement in main" rule for the opt-out.

## Depends on

- server-framework (plugin API, request/response helpers).
- config (which locations and types are allowed).
- file-handling (path/root helpers, safe join, content detection if taken on).

## Order

Phase 3 item 11.

## Open questions

- Streaming large files vs reading into memory (v1 can be simple; note as a later concern).
- Range requests / partial content — out of scope for v1 unless asked.
- Does "by type" mean MIME type, extension, or both in the config data?