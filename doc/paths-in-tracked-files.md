# Paths in Tracked Files

A tracked file is versioned *and* synced between machines, so it must not carry one machine's layout. Name a path relative to its repo, or point at the Agents workspace's `.agents/machine-info.md`, which is gitignored precisely so it can hold machine-specific locations. The exceptions are files whose subject *is* a location — a setup walkthrough's `scp` example, a plan about another host — a path quoted as evidence, and `personal/<person>/HISTORY.md`, which is per-person and exempt. xlint ticket `7HP67R2` will flag the rest.
