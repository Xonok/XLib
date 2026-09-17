# JS library provisioning

A place for JS libraries (an "xlib-like place for JS"), plus a way for servers to send those libraries to clients when asked — opt-in per server, never on by default.

## Goal

One home for this repo's JS code (reactive-web, webapp's JS layer, future JS libs), versioned and bundled like the Python xlib, so multiple servers can hand libraries to browsers without each project duplicating them.

## Why this is a thing of its own

The Python side is simple: libraries sit in `xlib/`, a server imports them directly. JS adds a hop — a server holds the files and a browser fetches them over HTTP. So there are two pieces: the *catalog* (versioned JS bundles, like `xlib/` for Python) and the *serving* (a server offering the catalog to clients).

## Design direction

- **Catalog**: versioned JS files/folders following the same naming idea as Python (`libraryname_major_minor_revision.js`), released by something like the release script — JS bundling is concatenation, not Python import inlining, so the bundler story differs (decide how).
- **Serving**: a library that a server mounts explicitly. Once mounted, a route answers "give me <library> <version>" and streams the bundle. The server can also pin which libraries it will expose at all.
- **Not allowed by default**: a server does not expose the catalog unless its main function explicitly enables it — same philosophy as file-server's "serve nothing unless allowed." The enablement must be an explicit statement in the server's main function.

## What "explicit" looks like

A server's main function says it wants JS library serving (e.g. a call adding the js-library plugin/route), and possibly which library names it allows. There is no config/per-server default flipping this on.

## Depends on

- server-framework (route/plugin mounting).
- file-server or file-handling (reading bundles from disk) — extent to decide.
- release tooling (to produce the versioned bundles).

## Order

Phase 4 item — pairs with webapp and reactive-web (they are its first consumers). Its serving side needs server-framework first.

## Open questions

- Does a server expose *all* known libraries, or must each library name be allowed individually?
- Version negotiation: pinned like xlib_pins, or "latest on disk" like xlib's default?
- Where does the catalog live: a `js/` folder in this repo, or inside xlib-style dev folders?