# Config

Configuration library, used by file-server and potentially logdb/webapp later. Evolved from `xlib_legacy/Config.py`, which reads JSON configs from `config/<name>.json` with defaults in `config/default/<name>.json`, reports or fills omissions, and caches loaded configs.

## Goal

Projects declare configuration as JSON with a defaults layer; libraries ask for config by name and get a dict. Omission handling (report vs auto-fill with defaults) is explicit per config.

## Requirements

- Read a named config from `config/`, falling back to `config/default/` when missing (creating the user-facing file from defaults).
- Merging and omission detection: for configs marked no_omissions, missing keys are reported and optionally filled from defaults.
- Cached reads (`read_all` + `get`).
- Keep the current semantics (`read`, `read_all`, `get`, `no_omissions`); the FIX_OMISSIONS / REPORT_OMISSIONS distinction is already sensible.

## Relationship to typechecking

Config values come back as JSON-typed dicts; validating them with typechecking schemas is natural but not required for v1. Decide whether config's "defaults" layer doubles as the schema.

## Consumers

- file-server (which locations/types to serve, and whether folder-serving is allowed).
- logdb (schema-configured per-project records).
- webapp (deferred).

## Order

Phase 1 item — cheap to do early since file-server depends on it.

## Open questions

- Keep the filesystem layout (`config/` + `config/default/`) exactly, or make the base directory configurable?
- Should config be validated against typechecking on load, or is that overkill?