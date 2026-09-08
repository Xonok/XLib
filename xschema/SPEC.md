# xschema Spec

## Overview

**xschema** is a runtime type/schema system that validates Python values against type specifications. It provides a unified `parse()` funnel accepting two equivalent expression forms — a compact string notation (`"int"`, `"int_nat"`, `"list:int(0,5)"`, `"dict:str:int"`) and a Python/dict form (builtins, `Type` instances, composite dicts like `{"name": "str", "?email": "str"}`) — both producing `Type` instances with a shared `check(value, path)` contract. A global `Registry` maps type-id strings to `Type` classes, enabling user-defined types usable in the string notation. A `Schema` built from a function signature wraps the function (`@schema.validate`) so every call validates its arguments, binding positional/keyword args and raising `ValidationError` with a dotted-path locator on mismatch.

## Data Flow

```
spec (str | type | Type | dict)
       │
       ▼
  parse() ──────────────────► Type instance
       │                           │
       │                    +------------------+
       │                    |                  |
       ▼                    ▼                  ▼
Registry              Scalar types         Container types
(type-id → class)     (Int/Float/Num/      (List, Dict,
                       Bool/Str)             Composite)
                                                       │
                               ┌─────────────────────┘
                               ▼
                        validate(value, spec)
                               │
                               ▼
                        Type.check(value, path[])
                               │
                               ├── raises ValidationError(path, msg)
                               │     path → "user.addresses[0].zip"
                               │
                               └── returns None (success)
```

**Schema-from-function path:**
```
@schema.validate
def fn(a: int, b: str = "x"): ...
       │
       ▼
Schema.from_function(fn)  ──► inspect.signature
       │                          │
       ▼                          ▼
  fields dict              annotations + defaults
  {name: (Type, opt)}           │
       │                        ▼
       ▼              internal: _simple_from_annotation / _type_from_default
  Schema(fn, fields)          │
       │                        ▼
       ▼              Type instances + optional flag
  SchemaDecorator           │
       │                        │
       ▼                        ▼
wrapped(*args, **kwargs)  bind() → argdict → check() → ValidationError or call
```

*Internal helpers `_simple_from_annotation`, `_type_from_default`, `_fields_from_signature` are not public API.*

## Key Invariants / Design Decisions

- **Two expression forms, one funnel**: String notation (config/user input) and Python/dict form (code-level) both route through `parse()` → `Type`. No semantic difference.
- **Raise-on-failure**: `check()` raises `ValidationError` (contrast with xcsv's `(result, error)` tuples). Validator wrappers (`@schema.validate`) are opt-in boundaries, not pervasive checks.
- **Path-tracking errors**: Every `check(value, path)` receives and extends a `path` list (field names + int indices). `ValidationError` formats it as a locator (`user.addresses[0].zip`). Recursion stops at the failed node; siblings continue.
- **Registry as extension point**: `REGISTRY` maps `"int"`, `"list"`, etc. to `Type` classes. User libraries register custom types by name → usable in string specs without imports.
- **Required vs optional**: Composite fields prefixed with `?` (`"?email"`) are optional; missing optional fields are skipped, missing required fields raise. Function parameters: default → optional; annotation-only → required.
- **No error collection mode yet**: Current `check()` is raise-first. The plan specifies a future `errors(value, spec) -> list[ValidationError]` collecting all sibling errors (Phase 1).

## API Surface

| Symbol | Role |
|--------|------|
| `parse(spec)` | Funnel: str/type/Type/dict → `Type` instance |
| `validate(value, spec)` | One-shot validation; raises `ValidationError` |
| `format_path(path)` | Format path list as dotted locator (`"user.addresses[0].zip"`) |
| `Type` / subclasses | Base + concrete types (`IntType`, `FloatType`, `NumType`, `BoolType`, `StrType`, `ListType`, `DictType`, `CompositeType`, `IntNat`, `IntGt0`) |
| `Registry` / `REGISTRY` | Global name → class map; `register(cls)`, `get(name)`, `names` |
| `ValidationError(path, msg)` | Exception with `path` (list) and `path_str` property |
| `Schema.from_function(fn)` | Build schema from signature (annotations + defaults) |
| `Schema.check(argdict)` | Validate bound arguments |
| `Schema.bind(args, kwargs)` | Positional + keyword → dict per parameter order |
| `Schema.validate` / `SchemaDecorator` | Decorator: wrap function for per-call validation |

*Internal (not public): `_simple_from_annotation`, `_type_from_default`, `_fields_from_signature`, `_composite_fields`, `_parse_string`, `_construct`, `_bounds*`, `_split*`, `_coerce`, `_bound_check`.*

## Data Structures

- **`Type`** (base): `name` (registry id), `check(value, path)`, `__repr__` via `_params()` (internal).
- **Scalar types** (`IntType`, `FloatType`, `NumType`, `BoolType`, `StrType`): optional `lo`/`hi` bounds (numeric or length). `IntNat` (`lo=0`), `IntGt0` (`lo=1`) are preset subclasses.
- **`ListType`**: `elem` (element `Type` or `None`), `lo`/`hi` length bounds. Recurses `elem.check(item, path + [i])`.
- **`DictType`**: `key` and `value` `Type`s (or `None`). Checks each `k,v` with `path + [k]`.
- **`CompositeType`**: `fields: {name: (Type, optional)}`. Requires all non-optional fields, rejects extra fields, recurses per field with `path + [key]`.
- **`Registry`**: `_types: {str: TypeClass}`; `register(cls)`, `get(name)`, `__getitem__`, `names`.
- **`Schema`**: `fn` (original), `fields: {name: (Type, optional)}`. `from_function()` uses internal `_fields_from_signature`.
- **`SchemaDecorator`**: Holds `Schema`; `__call__(fn)` returns `wrapped(*args, **kwargs)` that binds, checks, then calls.
- **`ValidationError`**: `path` (list), `message`, `path_str` property → formatted locator.

## Planned Changes

Per `plans/typechecking.md`:

1. **Error collection mode** (`errors(value, spec) -> list[ValidationError]`): shared traversal with raise-first `check()`; stops at failed node, continues siblings. Phase 1.
2. **Read-then-validate examples**: JSON/CSV load → explicit validate step; ensure no type checks leak into load. Phase 3.
3. **Custom type declarative form**: User-defined types registered in `REGISTRY` with a declarative checker (not yet in code; plan mentions "custom checker, likely with a declarative form").