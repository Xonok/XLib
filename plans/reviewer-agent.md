# XLib Reviewer Agent

## Goal
Implement a reviewer agent that acts as a release gate — user-invoked, independent code review, produces review documents keyed to commit hashes, executes releases only on explicit user permission.

## Requirements
- **User-invoked only**: Programmer never calls reviewer
- **Per-library reviews**: Each library reviewed independently
- **Review documents**: Stored in `reviews/<library>-<commit-hash>.md`, keyed to commit so staleness detectable via `git diff`
- **Release execution**: Reviewer runs `release/release.py` but only after explicit user permission
- **Independent gate**: Separate agent from programmer

## Review Document Format
```
reviews/<library>-<commit-hash>.md
# Review: <library> @ <commit-hash>
**Date**: <ISO date>
**Reviewer**: <agent-id>
**Scope**: <files or "full library">
**Status**: `pending` | `approved` | `changes-requested` | `blocked`

## Summary
<2-3 sentence overview>

## Findings
### Issues (must fix)
- <file:line> - <description>

### Suggestions (optional)
- <file:line> - <description>

### Approved
- <what was reviewed and passed>

## Decision
- `approve` — ready for release
- `request-changes` — fix issues first
- `block` — fundamental problems

## Outdated Check
`git diff <commit-hash>..HEAD -- <library>/` — if non-empty, review is stale
```

## Workflow
1. User invokes: "Review <library>" (or "Review all")
2. Reviewer finds latest commit touching that library, analyzes current state
3. Reviewer writes review document to `reviews/`
4. Reviewer presents findings, recommends bump type (rev/minor/major)
5. User discusses, decides
6. If user says "Release <library> [--minor|--major]", reviewer runs `python3 release/release.py <library> [--minor|--major]`
7. Reviewer updates review doc status to `approved` with release version

## Integration Points
- **Reads**: Library source in `<library>/<library>.py`, release script
- **Writes**: Review documents in `reviews/`
- **Executes**: `release/release.py` on permission
- **Uses**: `git` for commit hashes and staleness checks

## Open Questions
1. Should reviewer also check architecture rules (style/architecture.md)?
2. Should reviewer run tests (xtest) as part of review?
3. How to handle multi-library reviews (dependencies)?
4. Review document retention — keep all or only latest per library?

## Status
- [ ] Plan approved
- [ ] Technical spec written
- [ ] Implementation started
- [ ] Testing
- [ ] Release