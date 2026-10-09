# Versioning

Libraries are versioned `<library>_<major>_<minor>_<revision>.py`. Bump **revision** by default — bugfixes only, no features, no API change. **Minor** for additions that don't break previous users. **Major** only to drop deprecated code, and only with both breaking changes and time since the last major. Cosmetic fixes need no bump. Deprecations are marked in version terms and dropped after exactly 2 major versions.
