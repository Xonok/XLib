# XLib plans

Planning documents for libraries and tooling in this repo. Each library gets its own plan file plus one file describing the build order. Files are about *what* and *why*; the live rules for *how* code is written live in AGENTS.md.

Plans are living documents. When a plan becomes reality, the plan file is deleted and the library's own docs (if any) take over. TODO items below are placeholders, not commitments — each plan gets its decisions confirmed before building starts.

**Where a plan's residue goes.** A plan is deleted when the work lands, but only after anything in it that is *not* built has been carried into the doc that outlives the plan — a `## Planned Changes` / `## Open questions` section in the library's SPEC.md, or a `## Future work` section in the tool's README. Eight files were deleted on 2026-09-30 that way; `tools/release/README.md`, `dev/xcsv/SPEC.md` and `dev/xtest/SPEC.md` carry what was left.

## Contents

- [build-order.md](build-order.md) — recommended order, rationale, what unlocks what.
- [bundler.md](bundler.md) — review + redesign notes for the bundler. The redesign is abandoned and superseded by a new spec (epi `6MFX0Z1`); the file is kept as the record of the attempt.
- [ai-code-viability.md](ai-code-viability.md) — can AI-heavy development stay viable long-term? Five mechanisms (per-library architectural docs, structural-consistency rules, scenario-oriented tests, a design-review step, subtle-behavior annotations), each to be costed and ranked before any is adopted. Recovered from the git-ignored `.agents/` folder on 2026-09-29, where it had sat untracked since 2026-09-10; human task: taskview #75, epiq `E98CRYM`.
- [code-analysis.md](code-analysis.md) — deploy full code analysis tooling beyond xlint's style rules (SonarQube and candidates); needs discussion.
- [comment-types.md](comment-types.md) — standardise comment types by visual pattern, so a comment's purpose reads at a glance.
- [agent-coord-role-notes.md](agent-coord-role-notes.md) — role-based notes shared between agents of the same role, alongside instance notes; promote instance → role by hand.
- [taskview-time-refresh.md](taskview-time-refresh.md) — periodic time-based refresh of the tmux task view so relative timestamps update.
- [tmux-panel-priorities.md](tmux-panel-priorities.md) — repurpose the unused tmux panel to show priorities in condensed form.
- [typechecking.md](typechecking.md) — type system with custom type support, usable standalone. `dev/xschema/SPEC.md` draws on it.
- [xlint-frontmatter-fence-skip.md](xlint-frontmatter-fence-skip.md) — exempt YAML frontmatter and fenced code blocks from the `.md` space-indent check. Implemented; indented fences exempted per ruling `QN1N82Y`.
- [xaudit.md](xaudit.md) — project-specific structural checks, owning the watch loop and calling xlint one-shot. Decided, not started.
- [per-person-files.md](per-person-files.md) — make the per-person master files (`STATUS.md`, `TASKS.md`, `PLAN.md`) tracked but personal, with the root file a gitignored per-person symlink.
- [server.md](server.md) — declarative server framework that other libraries plug into.
- [fileserver.md](fileserver.md) — static/file serving as a server plugin.
- [websocket.md](websocket.md) — websocket protocol handling, server-pluggable.
- [command-runner.md](command-runner.md) — command dispatch for server + websocket, sessions, typechecking integration.
- [logdb.md](logdb.md) — log-based database, project details via schema configuration.
- [dnd-math.md](dnd-math.md) — dice and similar math.
- [loot-tables.md](loot-tables.md) — loot tables with recursion and configuration.
- [file-handling.md](file-handling.md) — file handling helpers.
- [js-libraries.md](js-libraries.md) — an "xlib for JS": versioned JS bundles, opt-in serving.
- [webapp.md](webapp.md) — minimal Py/JS webapp framework with lazy views.
- [reactive-web.md](reactive-web.md) — JS reactive toolkit for data dependencies.

## Cross-cutting decisions (recorded so far)

- **Planning pattern**: Standard workflow for projects: requirements → plan → spec → implement → review → release. The planner writes the plan, **the human writes the spec**, the programmer implements the spec as code, the reviewer builds the tests from the spec (pass 1) and checks the work (pass 2). See `doc/development.md` for the stages and who owns each.
- **Schema and typechecking**: possibly the same library; decision deferred. Treat as one design until a reason to split appears.
- **Server framework**: fresh design, not an evolution of `xlib_legacy/dumb_http.py`. Legacy code stays as reference material only.
- **Command runner sessions**: part of the command runner library, not a separate one.
- **Build order**: [build-order.md](build-order.md) documents the dependency-informed order. The release script comes early because everything else needs a way to be released.
- **Release script decisions**: recorded in `tools/release/README.md` now that the plan has been deleted — version semantics, the `--major` age gate, dependency pinning, and the future work (export, publish-dependencies, bundler reuse). The release folder is `tools/release/`; it is developed like a library but never released.
- **Future tooling**: a *publish-dependencies* script and the release script's *export* function are planned but not in scope yet; both are listed in `tools/release/README.md`.
- **Language split**: most libraries are Python. `reactive-web` and the webapp view layer are JS. The webapp framework is Py + JS.
- **File server security**: default is to serve nothing that isn't explicitly allowed; allowed types/locations come from config, and "serve whatever is in a folder" requires an explicit statement in the server's main function.
- **JS provisioning**: JS libraries are versioned bundles (an "xlib for JS") and servers opt in per-server to hand them to clients — never by default.
- **xlint release decision**: Currently a dev tool (not released). Traveller could use it; decision pending discussion. If released: would need versioning, SPEC.md, and entry in build order. Add to backlog.
