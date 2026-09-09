# xconf Spec

## Overview

**xconf** is a JSON configuration loader with layered defaults, overrides, and omission handling. It reads configuration from a directory structure (`config/default/` for defaults, `config/` for user overrides), merges them deeply, handles missing keys with configurable policies ("fill" or "strict"), and saves diffs back to the user config file.

## Data Flow

```
Directory structure:
  <base>/default/name.json   ← default values (required)
  <base>/name.json           ← user overrides (optional, auto-created)

read("name"):
    │
    ▼
_load default (required) ──────► default dict
    │
    ▼
_load user (optional) ─────────► override dict (or create from default)
    │
    ▼
merge(default, override) ──────► merged dict (deep merge)
    │
    ├── if policy == "fill": ───► fill missing from default, write back
    ├── if policy == "strict": ─► raise ValueError on missing keys
    └── if policy == None: ─────► return override as-is (no default merge)
    │
    ▼
_data[name] = result ──────────► cached, returned

save("name", data, diff_only=True):
    │
    ▼
_load default ─────────────────► default dict
    │
    ▼
difference(default, data) ─────► diff dict (only changed keys)
    │
    ▼
write_json(name, diff) ────────► <base>/name.json (only differences)
```

## Key Invariants / Design Decisions

- **Deep merge**: `merge()` recursively merges dicts; non-dict values are replaced entirely. Lists are replaced, not merged.
- **Defaults are mandatory**: A `default/name.json` must exist; user config is optional (auto-created on first read).
- **Omission policies** (set via `no_omissions(name, strict=False)`):
  - `fill` (default): missing keys from default are filled in, merged result written back to user config
  - `strict`: missing keys raise `ValueError`; user must provide all keys
  - `None`: no default merge; raw user config returned (or empty if none)
- **Diff-only save**: `save(name, data, diff_only=True)` computes `difference(default, data)` and writes only changed keys. If no changes, writes `{}`.
- **Path format**: Base directory defaults to `"config"`. Changed via `configure(base)`.
- **In-memory cache**: `read()` stores result in `_data[name]`; `get(name)` retrieves cached value.
- **`_UNSET` sentinel**: `difference()` returns `_UNSET` (private sentinel) when no differences exist; `save()` converts to `{}`.

## API Surface

| Symbol | Role |
|--------|------|
| `configure(base)` | Set config base directory (default: `"config"`) |
| `merge(defs, over)` | Deep merge two dicts; returns new dict |
| `difference(defs, over)` | Keys in `over` that differ from `defs`; returns `_UNSET` if identical |
| `missing(defs, over)` | List of dotted paths in `defs` missing from `over` |
| `read(name, policy=None)` | Load config `name`; applies policy; caches and returns merged dict |
| `read_all()` | Read all configs from `default/` directory; returns count |
| `get(name)` | Return cached config from last `read()` or `None` |
| `no_omissions(name, strict=False)` | Set policy for `name`: `strict=True` → "strict", else "fill" |
| `save(name, data, diff_only=False)` | Write `data` (or diff vs default) to user config file |

*Internal (not public): `_UNSET`, `_DEFAULT_BASE`, `_data`, `_policies`, `_base`, `_paths`, `read_json`, `write_json`, `_handle_omissions`, `_read_one`.*

## Data Structures

- **`_data: dict[str, dict]`** — In-memory cache of loaded configs: `{name: merged_dict}`.
- **`_policies: dict[str, str]`** — Omission policy per config: `{name: "fill" | "strict"}`.
- **`_base: str`** — Base directory path (default `"config"`).
- **`_UNSET: object`** — Private sentinel returned by `difference()` when no diffs exist.
- **Config file** — JSON file with arbitrary nested structure (dicts, lists, primitives).

## Helper Functions

| Function | Behavior |
|----------|----------|
| `merge(defs, over)` | If both dicts: recurse on keys; else return `over`. Preserves keys in `defs` not in `over`. |
| `difference(defs, over)` | Recursively collect keys where `over` differs from `defs`. Returns `_UNSET` if equal. Non-dict values: `defs != over` → return `over`. |
| `missing(defs, over)` | Recursively collect dotted paths in `defs` absent from `over`. Returns `list[str]` (e.g., `["top.b", "nested.x"]`). |
| `_paths(name, default)` | Returns `<base>/default/name.json` if `default`, else `<base>/name.json`. |

## Planned Changes

None currently. Potential future work:
- Environment variable interpolation in config values
- Config validation via xschema
- Multiple base directories (layered configs)
- Watch/reload on file change