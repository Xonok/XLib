# XLib Reviewer Agent

## Goal
Implement a reviewer agent that acts as a release gate — user-invoked, independent code review, produces review documents keyed to commit hashes, executes releases only on explicit user permission.

## Requirements
- **User-invoked only**: Programmer never calls reviewer
- **Per-library reviews**: Each library reviewed independently
- **Review documents**: Stored in `reviews/<library>-<commit-hash>.md`, keyed to commit so staleness detectable via `git diff`
- **Release execution**: Reviewer runs `release/release.py` on explicit user permission
- **Independent gate**: Separate agent from programmer
- **Bump recommendation**: Reviewer analyzes and recommends bump type (revision/minor/major)
- **Full rule coverage**: Reviewer checks all applicable rules — style/common.md, style/python.md, style/architecture.md, SPEC.md compliance
- **Test execution**: Reviewer runs tests (xtest) as part of review; tests should produce no output on success, only on failure

## Review Document Format
```
reviews/<library>-<commit-hash>.md
# Review: <library> @ <commit-hash>
**Date**: <ISO date>
**Reviewer**: <agent-id>
**Scope**: <files or "full library">
**Status**: `pending` | `approved` | `changes-requested` | `blocked`
**Bump**: `revision` | `minor` | `major`

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
3. Reviewer runs tests (xtest) — silent on pass, reports failures
4. Reviewer checks all rules: SPEC compliance, style/common.md, style/python.md, style/architecture.md
5. Reviewer writes review document to `reviews/` with bump recommendation
6. Reviewer presents findings, recommends bump type (rev/minor/major)
7. User discusses, decides
8. If user says "Release <library> [--minor|--major]", reviewer runs `python3 release/release.py <library> [--minor|--major]`
9. Reviewer updates review doc status to `approved` with release version

## Integration Points
- **Reads**: Library source in `<library>/<library>.py`, release script, SPEC.md, xtest
- **Writes**: Review documents in `reviews/`
- **Executes**: `release/release.py` on permission; `xtest` during review
- **Uses**: `git` for commit hashes and staleness checks (read-only)

## Open Questions
1. How to handle multi-library reviews (dependencies)?
2. Review document retention — keep all or only latest per library?

## Status
- [ ] Plan approved
- [ ] Technical spec written
- [ ] Implementation started
- [ ] Testing
- [ ] Release