# Watcher review

Advisory pass over the prototype on 2026-11-11. Items are ordered so each fix
unblocks the next; most are otherwise independent.

## Settled, not faults

- **`interval` is the backend timeout, not a batching window.** Inotify blocks
	in `select` up to the timeout and delivers as soon as events arrive — no
	added delay. Polling sleeps the interval between scans. It stays a parameter
	for tuning the polling backend (Windows performance); 1 second is the
	candidate default.
- **The signature order is intentional** — `watch(callback, interval, paths, excludes)`.
	`excludes` is required, not defaulted, because a non-default argument cannot
	be type-hinted cleanly after a defaulted one. Callback and interval come
	first so inline lists for `paths` and `excludes` read well.
- **One event per path per callback batch.** Duplicates within one read
	(`IN_MODIFY` + `IN_CLOSE_WRITE`) reduce to one event.
- **Recursion is in scope.** The earlier "single folder, no recursion" goal is
	abandoned; new subdirectories must be watched. Excludes are required
	regardless.
- **`paths` may be files or folders.** A file path is watched through its
	parent directory internally; the caller does not need to know that.
- **Excludes are matched relative to cwd.**

## Faults

1. **Entry import.** `watcher.py:4` — `from _ import watcher` resolves only when
	`dev/watcher/` is on `sys.path` as a script's directory. Imported the repo
	way (`from watcher.watcher import ...`), `_` is not top-level and the import
	fails. Use `from ._ import watcher`, as `dev/xhttp/xhttp.py` does.

2. **Public constants are undefined.** `watcher.py:18-20` — the docstring
	promises `NEW`, `CHANGE` and `REMOVE`, but no module defines them. Expose them
	from the entry file, which is where the public API lives, and have both
	backends emit the same values (bind the entry names to one internal
	definition, rather than defining them twice).

3. **Docstring example is not valid Python.** `watcher.py:12-14` —
	`watch_callback(events):` is missing `def`, and the loop unpacks `evt,path`
	while the text describes the tuple as `(event type, file path)`. Show the
	real shape.

4. **Watch registration calls the wrong thing.** `_/watcher.py:32-34` —
	`notifier.add_watch(path)` is not a module function; the instance is
	`notify.add_watch`. It also returns `None`, so `wd_to_path` stays empty. Let
	the notifier own wd→path, or make `add_watch` return the wd and drop the
	duplicate map.

5. **The event unpacking cannot work.** `_/watcher.py:41`, `_/inotify.py:78`,
	`_/notifier.py:37` — both notifiers return `(base, (wd, mask, path))`, so
	`for wd,mask,path in evt` unpacks two values into three and raises
	`ValueError`. Return one flat `(base, mask, path)` per event.

6. **`events_out` is a list indexed by a path.** `_/watcher.py:39,44` — assigning
	`events_out[fullpath]` raises `TypeError` on the first event. Make it a dict
	keyed by full path, reduce duplicates, then convert to the three-event list.

7. **The callback gets the raw inotify events.** `_/watcher.py:45` —
	`callback(events)` passes the unconverted read result, not the reduced
	three-event list built above.

8. **An empty event name breaks the join.** `_/watcher.py:43` —
	`os.path.join(base, path)` with `path == ""` (the self events
	`IN_DELETE_SELF`/`IN_MOVE_SELF`/`IN_IGNORED`) yields `base/`. Use `base`
	when the name is empty, and skip when `base` is `None`.

9. **Cleanup runs only on the happy path.** `_/watcher.py:46-48` —
	`notifier.destroy()` does not exist (it is `notify.destroy()`), and it is not
	in a `finally`, so a callback exception leaks the descriptor. Close in
	`finally`. Whether the library should swallow `KeyboardInterrupt` at all is
	still a decision.

10. **The inotify parser reads the name from the wrong offset.** `_/inotify.py:47-53`
	— `offset` is advanced past the name before the name is sliced, so every
	reported path is bytes from the next record. Slice
	`raw[offset:offset + namelen]` first, then advance by `(namelen + 3) & ~3`.
	The deleted `dev/xwatch/_/ctypes.py` had this order right.

11. **The inotify availability guard is wrong.** `_/inotify.py:18-31` — the
	import catches only `AttributeError`; `ctypes.CDLL(None)` can raise `OSError`
	on platforms without an inotify-capable C runtime. Catch both and set
	`_libc = None`. `create()` tests `HAS_INOTIFY is None`, which is never true
	because the flag is `True`/`False`; guard on `_libc is None` instead.

12. **There are two notifier classes.** `_/inotify.py:58-79` duplicates the one
	in `_/notifier.py` (path map, read, destroy) with a different return shape.
	Keep the binding syscall-only and delete the class, so wd→path lives in one
	place.

13. **An unknown wd raises `KeyError`.** `_/notifier.py:37` — `self.paths[wd]`
	fails once the kernel drops a watch (`IN_IGNORED`, deleted directory). Use
	`.get(wd)` and drop the stale entry instead of raising out of the loop.

14. **The poll fallback calls a function that does not exist.** `_/notifier.py:62`
	— `os.isdir` is not in the `os` module; the first poll raises
	`AttributeError`. Use `os.path.isdir` or `os.scandir`.

15. **The poll fallback loses the directory when recursing.** `_/notifier.py:63`
	— `os.listdir` returns names, not paths, so recursing on them resolves
	against cwd instead of the watched directory. Join with the directory first.

16. **The poll stamp is a placeholder.** `_/notifier.py:54-58` — `mtime_new = 0`
	means no change is ever detected. Use a real stamp (`st_mtime_ns` and
	`st_size`, or the `stamp` helper in `tools/xlint/_io.py`).

17. **A missing file is reported as a change.** `_/notifier.py:51-58,68` — a
	missing file returns `None`, and `None != False` is true, so every missing
	path is appended. Branch on existence explicitly.

18. **The poll fallback has no baseline.** `_/notifier.py:44-48` — `add_watch`
	records no initial stamp, so the first read must seed the tree without
	reporting every existing file as new. Choose the rule (silent seed is the
	usual one) and implement it.

19. **`path_in_scope` is a stub.** `_/notifier.py:4-16` — exact match only, and
	the `*`/`**` branches do nothing. It is not called yet; keep it unwired
	until the cwd-relative exclude matcher exists.

20. **The harness is stale.** `test.py:1,8` — imports `xwatch` and uses the old
	`(paths, callback)` order, so it cannot run. Update it to
	`from watcher.watcher import watch` and `watch(on_change, 1.0, [...], [])`,
	or move it under `test/` when the xtest suite starts.

21. **Layout leftovers.** `_/` has no `__init__.py` (it works today through the
	namespace-package fallback, but the repo layout includes it), and
	`__pycache__/xwatch.cpython-314.pyc` is left from the rename — delete it.

## Gaps against the current goal (not faults yet)

- **Recursive watching.** Inotify has no recursive flag: each new directory
	needs its own `inotify_add_watch` when it appears, and its wd dropped when it
	goes. Excludes apply when a directory enters scope.
- **File paths.** Watch the parent directory and filter to the requested files;
	a direct file watch is lost to `IN_IGNORED` when an editor replaces the
	inode.
- **`IN_IGNORED` and `IN_Q_OVERFLOW`.** Already noted as yours to handle: an
	overflow arrives with `wd == -1`, and neither should reach a `KeyError`.
