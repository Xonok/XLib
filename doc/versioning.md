# Versioning

Libraries are versioned `<library>_<major>_<minor>_<revision>.py`. Bump **revision** by default — bugfixes only, no features, no API change. **Minor** for additions that don't break previous users. **Major** only to drop deprecated code, and only with both breaking changes and time since the last major. Cosmetic fixes need no bump. Deprecations are marked in version terms and dropped after exactly 2 major versions.

A released file is frozen in the sense that its behaviour and public API do not
change; it is **not** frozen byte-for-byte. Whitespace-only edits (for example,
to satisfy xlint) are permitted on a released file without a version bump, as
long as they change no behaviour. The release keeps its version number and its
place in `xlib/`.
