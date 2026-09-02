# Build order

Recommended order = dependencies first, with early work establishing the dev-folder + release workflow so later libraries have a pipeline to release through. Each phase is buildable and releasable on its own.

## The dependency picture

```
csv ─────────────┐
file-handling ───┼──> logdb
typechecking ────┴──┐
                    ├──> command-runner ──> sessions
config ──> file-server
dnd-math ──> loot-tables
server-framework ──> websocket ─┐
     └─> file-server ───────────┤
     └─> js-libraries ──────────┼──> webapp ──> reactive-web
```

Foundations first, everything fanning out from them.

## Phase 0 — release machinery

1. **pybundle** (finish the bundler). **DONE** — `pybundle/bundler.py` is the implementation; the incomplete `inliner.py`/`inliner2.py` prototypes were removed. Bundler output is xlint-clean (imports merged per repo style, single blank after the import block).
2. **release script** — consumes the bundler, produces `xlib/<library>_<major>_<minor>_<revision>.py`. Needs `-minor` / `-major` behavior described in readme.md, and to keep pins consistent (`xlib_pins.py`). **DONE** and validated end-to-end: `xtest` was the first library released through it (`xlib/xtest_1_0_0.py`), importable both unversioned (`from xlib import xtest`) and versioned (`from xlib import xtest_1_0_0`).

Why first: everything below needs a way to become a versioned release, and it validates the whole "dev in a folder → release to xlib" model with trivial inputs.

## Phase 1 — foundations (leaf libraries, no internal deps)

3. **typechecking** (with schema candidacy) — shape validation + custom types. Foundation for command-runner, logdb, and likely testing and CSV round-trips. The schema/typechecking split decision lives here.
4. **csv** — comments + tokenizer/serializer, stringly-typed by nature. Leaf library, good early test of the release pipeline.
5. **file-handling** — building blocks for file-server and logdb.
6. **dnd-math** — dice etc. Leaf, dependencies are just stdlib.
7. **config** — JSON config with a defaults layer (from `xlib_legacy/Config.py`); file-server depends on it, logdb may validate against it.
8. **xtest** (was "testing") — built early so every library after it is developed against real tests, but must not block the other phase-1 libs; they can exist before it and gain tests later. It is a normal versioned library (external projects can depend on it), which also makes it a good first end-to-end test of the release pipeline.

## Phase 2 — infrastructure

9. **server-framework** — the plug-in host. Everything web-shaped hangs off it, so its plugin/declarative design has to be settled early even if consumers arrive late.
10. **logdb** — consumable as soon as csv + file-handling + typechecking land; independent of the server stack.
11. **websocket** — protocol lib first; the server plugin layer comes when the framework is ready. Can be developed and released in parallel with 9.

## Phase 3 — built on the server framework

12. **file-server** — server plugin + file-handling + config. Default is to serve nothing; allowed types/locations come from config, folder-serving is an explicit statement in main.
13. **command-runner** — the typechecking-integrated dispatcher; gets a `POST` transport plugin and a websocket transport plugin once both hosts exist. Sessions live in this library.

## Phase 4 — the web layer

14. **webapp** (Py/JS) — minimal, lazy views, mounting on server-framework.
15. **js-libraries** — the "xlib for JS": versioned JS bundles plus an opt-in-per-server way to hand them to clients. Serves reactive-web/webapp JS.
16. **reactive-web** (JS) — data-dependency toolkit; consumed by webapp's JS side. Could start before webapp since it's JS and independent of the Python release pipeline.

## Parallelization notes

- 3–8 have no interdependencies; they can be built in any order or concurrently.
- 11 can run beside 9; only its plugin layer is constrained.
- 16 is JS and only needs an (unversioned or pinned) webapp to feed on; it can move earlier if wanted.

## Order-sensitive decisions

- Schema/typechecking merge decision must be made in phase 1 (item 4) — logdb and command-runner will assume the interface.
- The server plugin API must be decided during item 9; file-server, websocket, js-libraries, and command-runner all assume it afterward.
- File-server's "serve nothing unless allowed" default and explicit folder-allow in main are decided in item 12; js-libraries inherits the same opt-in philosophy.