# Tmux Panel Priorities Display

## Goal
Repurpose an unused tmux panel in the XLib tmux session (tmux-xlib.sh) to show priorities in condensed form.

## Requirements
- Display current task prominently (most of the space)
- Show upcoming tasks (some space)
- Summarize remaining tasks with total count and maybe expected hours
- Update automatically as tasks change
- Condensed format to fit in a tmux panel

## Current State
- XLib tmux session exists with multiple panels
- One panel is unused and can be repurosed
- Task data lives in TASKS.md (workspace-specific) and shared-notes.md

## Design Considerations
1. **Data Source**: Read from TASKS.md and/or shared-notes.md
2. **Update Frequency**: How often to refresh? On file change?定时?
3. **Format**: Text-based, fits in narrow tmux panel
4. **Location**: Which panel to use? How to identify it?
5. **Integration**: Should this be a script, a plugin, or part of tmux-xlib.sh?

## Open Questions
1. Which panel is "unused" and how to identify it reliably?
2. Should this read from local TASKS.md or from XLib's own task tracking?
3. How to handle task prioritization? (user's priorities vs. deadlines)
4. Should this be interactive (clickable) or display-only?
5. What's the refresh mechanism? (inotify,定时, manual?)

## Next Steps
1. Identify the unused panel in tmux-xlib.sh
2. Design the display format
3. Create a script to parse tasks and format for display
4. Integrate with tmux session
5. Test and refine

## Status
- [ ] Plan approved
- [ ] Technical spec written
- [ ] Implementation started
- [ ] Testing
- [ ] Release