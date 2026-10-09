# Working Tree

Don't change files that carry uncommitted changes you did not make. Before your first edit, run `python3 tools/agent-coord.py check-clean <path>` — `clean` means proceed, `dirty` means stop and name the blocked file. A file you created yourself earlier in the session is yours to keep editing. The human can override by explicit instruction.
