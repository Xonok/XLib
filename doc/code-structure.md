# Code Structure

- The entry file holds **only the public interface**, and the public API is *defined* there — never imported from an internal module and re-exported, because the bundler would prefix the name out from under its callers. Internals go in separate files (`<libraryname>_tok.py`).
- No `__init__.py` at a library root. Internal subfolders (e.g. `xcsv/_/`) may have one if they're packages.
