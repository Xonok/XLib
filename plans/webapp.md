# Webapp framework

Minimal webapp framework, Python + JS. Enables views and loads them lazily.

## Goal

The smallest layer on the server-framework that turns routes into views: a view maps a path to a handler producing content; content is loaded lazily (not all at startup).

## Design direction

- Py side: a thin view layer over server-framework — register view = path + handler; framework routes to it. Keep it minimal (this is not a full MVC framework).
- JS side: what the browser loads — pages/views fetched on demand (lazy load), no single giant bundle.
- Lazy = views/JS modules loaded when first requested; decision on what "view" is (file on disk? handler in a dev folder? both).
- Discovery could lean on file-handling (scan a views folder) and/or explicit registration.
- Minimalism is the point: no ORM, no asset pipeline beyond what's needed. The reactive-web lib (JS) is the toolkit that views use.

## Depends on

- server-framework (Py hosting)
- reactive-web (JS side)
- maybe file-handling (view discovery)

## Order

Phase 4 item 13.

## Open questions

- Where do JS assets live and how are they served (static via file-server)?
- Templating: string/none at first, or an escape-hatch for arbitrary Python to produce HTML?