# Rule-Change News

Run `python3 tools/agent-coord.py news` at session start and before first subagent dispatch. It reports changed rule files and marks them seen. Prefer to mechanize rules (tool checks, bundle-time checks) over prose; use news for changes you can't mechanize.

A run that finds no rule files at all says `nothing checked`, which is not the same answer as `no new guideline changes`: the first means the lookup found no workspace, the second means the rules did not change.
