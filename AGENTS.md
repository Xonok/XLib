# Project rules

These rules apply to all code written in this repository. AI assistants must follow them.

## Code style

- Code is always indented with tabs.
- Function definitions and calls must remain on one line.
- Use intermediate variables to break up complex logic.
- Prefer concise code, but do not make it complicated just to be concise.
- Don't pad things with extra spaces as a blanket rule.
- Do use spaces to break math into simpler parts.
- Use guard clauses instead of nested `if`s, unless the `if` has branches.
- Code that deals with untrusted input starts with sanity checks. It returns or raises an error when those checks fail.
