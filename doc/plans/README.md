# XLib plans

Planning documents for libraries and tooling in this repo. Each library gets its own plan file plus one file describing the build order. Files are about *what* and *why*; the live rules for *how* code is written live in AGENTS.md.

Plans are living documents. When a plan becomes reality, the plan file is deleted and the library's own docs (if any) take over. TODO items below are placeholders, not commitments — each plan gets its decisions confirmed before building starts.

## Contents

- [build-order.md](build-order.md) — recommended order, rationale, what unlocks what.
- [release-script.md](release-script.md) — versioned bundle creation + what pybundle must support first.
- [server.md](server.md) — declarative server framework that other libraries plug into.
- [fileserver.md](fileserver.md) — static/file serving as a server plugin.
- [websocket.md](websocket.md) — websocket protocol handling, server-pluggable.
- [typechecking.md](typechecking.md) — type system with custom type support, usable standalone.
- [command-runner.md](command-runner.md) — command dispatch for server + websocket, sessions, typechecking integration.
- [testing.md](testing.md) — easier test authoring for projects (`xtest`).
- [logdb.md](logdb.md) — log-based database, project details via schema configuration.
- [xcsv.md](xcsv.md) — XCSV with comment support, usable standalone and over HTTP.
- [dnd-math.md](dnd-math.md) — dice and similar math.
- [loot-tables.md](loot-tables.md) — loot tables with recursion and configuration.
- [file-handling.md](file-handling.md) — file handling helpers.
- [xconf.md](xconf.md) — JSON config with defaults; drives what file-server may serve.
- [js-libraries.md](js-libraries.md) — an "xlib for JS": versioned JS bundles, opt-in serving.
- [webapp.md](webapp.md) — minimal Py/JS webapp framework with lazy views.
- [reactive-web.md](reactive-web.md) — JS reactive toolkit for data dependencies.
- [reviewer-agent.md](reviewer-agent.md) — release gate agent: user-invoked code review, produces review docs keyed to dev folder content hash (`<lib>-<hash>.md`), executes releases on explicit permission.
- [skynet-second-tracker.md](skynet-second-tracker.md) — second agent tracker pane: live sessions with workspace-scoped names and statuses; trim first tracker (drop Active, hide Len/Tool/Stop/Unk).
- [taskview-time-refresh.md](taskview-time-refresh.md) — periodic time-based refresh for `taskview/taskview.py` tmux task view so relative timestamps update.
- [tmux-panel-priorities.md](tmux-panel-priorities.md) — repurpose unused tmux panel to show priorities in condensed form.

## Cross-cutting decisions (recorded so far)

- **Planning pattern**: Standard workflow for projects: requirements → plan → spec → implement → review → release. Secretary writes plan, planner in XLib fleshes out technical details with user to write spec, programmer implements spec as code, reviewer checks the work and (after asking for permission) makes a release if appropriate.
- **Schema and typechecking**: possibly the same library; decision deferred. Treat as one design until a reason to split appears.
- **Server framework**: fresh design, not an evolution of `xlib_legacy/dumb_http.py`. Legacy code stays as reference material only.
- **Command runner sessions**: part of the command runner library, not a separate one.
- **Build order**: `plans/build-order.md` documents the dependency-informed order. The release script comes early because everything else needs a way to be released.
- **Release script decisions**: recorded in `plans/release-script.md`. Notably: release folder is `release/release.py` (script developed like a library but never released); the script does not test bundled output; a library can't be released before all its requirements are; `--major` is gated behind an age threshold (override with `--force`); the release script was implemented as `release/release.py` and the bundler was refactored to support explicit versioned imports.
- **Future tooling**: a *publish-dependencies* script (so projects can publish their deps for xlib and know when an old release can be dropped/moved) and the release script's *export* function (fold in xlib deps for outside-garden use) are planned but not in scope yet.
- **Language split**: most libraries are Python. `reactive-web` and the webapp view layer are JS. The webapp framework is Py + JS.
- **File server security**: default is to serve nothing that isn't explicitly allowed; allowed types/locations come from config, and "serve whatever is in a folder" requires an explicit statement in the server's main function.
- **JS provisioning**: JS libraries are versioned bundles (an "xlib for JS") and servers opt in per-server to hand them to clients — never on by default.
- **xlint release decision**: Currently a dev tool (not released). Traveller could use it; decision pending discussion. If released: would need versioning, SPEC.md, and entry in build order. Add to backlog.