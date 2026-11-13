# Watcher

File watcher library.
Uses inotify when available, polling when not.

## Vision

Must be simple to use and require very few lines for common use cases.

## AI limits

The implementation is human-written, tests AI-written.

## Initial goal

Watch a single folder, say when anything in it changed.
Support exclusions immediately - it's not harder in practice.
