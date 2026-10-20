# Paths in Tracked Files

A tracked file is versioned *and* synced between machines, so it must not carry one machine's layout. Name a path relative to its repo, or point at the Agents workspace's `.agents/machine-info.md`, which is gitignored precisely so it can hold machine-specific locations. The exceptions are files whose subject *is* a location — a setup walkthrough's `scp` example, a plan about another host — a path quoted as evidence, and `personal/<person>/HISTORY.md`, which is per-person and exempt. xlint ticket `7HP67R2` will flag the rest.

**`~/` is not a machine's layout and is not flagged** (2026-10-20). The rule is about *one machine's* layout, and `~/` is the portable form: `os.path.expanduser("~/.local/share/taskview")` is correct on every machine, where `/home/someone/...` is correct on one. Flagging `~/` would have meant rewriting correct code to point at a machine-info file, which is a rule that makes the code worse.

**The check runs on Python files too** (2026-10-20), and it distinguishes a docstring from a string literal. A docstring is prose about the code, and one that says where the tool lives names a location; a string literal is a value, and one that looks like a path is usually a test fixture. So the check flags the first and leaves the second alone — which is what lets `tools/tool_schema_cache.py` be corrected rather than the check weakened.
