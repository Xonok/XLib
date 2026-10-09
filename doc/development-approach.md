# Development Approach

- Each library has its own dev folder with one entry point; dev folders are **not packages** (no `__init__.py`).
- **Libraries never use versionless imports**, even in development — always an explicit released version (`from xlib import libraryname_5_9_27 as ...`). Tests are the exception: a test in a dev folder imports the library under development unversioned, because testing the code being developed is the point.
- A library pins its requirements as versioned imports, and is never released unless all of them are already released.
- Every versioned library keeps a `VERSIONS.md` in its dev folder: newest first, one entry per release, noting what changed. Tools and scripts that aren't versioned don't need one.
