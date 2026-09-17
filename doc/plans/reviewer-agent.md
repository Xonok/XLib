# XLib Reviewer Agent

## Goal
Implement a reviewer agent that acts as a release gate — user-invoked, independent code review, produces review documents keyed to dev folder content hash, executes releases only on explicit user permission.

## Requirements
- **User-invoked only**: Programmer never calls reviewer
- **Per-library reviews**: Each library reviewed independently
- **Review documents**: Stored in `reviews/<library>-<hash>.md` where `<hash>` is a content hash of the dev folder (all files combined). The hash serves as a change detector — if the folder content changes, the review is stale.
- **Release execution**: Reviewer runs `release/release.py` on explicit user permission
- **Independent gate**: Separate agent from programmer
- **Bump recommendation**: Reviewer analyzes and recommends bump type (revision/minor/major)
- **Full rule coverage**: Reviewer checks all applicable rules — style/common.md, style/python.md, style/architecture.md, SPEC.md compliance
- **Test execution**: Reviewer runs tests (xtest) as part of review; tests should produce no output on success, only on failure

## Review Document Format
```
reviews/<library>-<hash>.md          # hash = content hash of dev folder
# Review: <library> @ <hash>
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

## Staleness Check
Compute hash of `<library>/` folder (all files). If different from `<hash>` in filename, review is stale.
```

## Workflow
1. User invokes: "Review <library>" (or "Review all")
2. Reviewer computes content hash of `<library>/` dev folder
3. If `reviews/<library>-<hash>.md` exists, it's still valid — reviewer can update or note staleness
4. Reviewer analyzes current state
5. Reviewer runs tests (xtest) — silent on pass, reports failures
6. Reviewer checks all rules: SPEC compliance, style/common.md, style/python.md, style/architecture.md
7. Reviewer writes/updates review document to `reviews/<library>-<hash>.md` with bump recommendation
8. Reviewer presents findings, recommends bump type (rev/minor/major)
9. User discusses, decides
10. If user says "Release <library> [--minor|--major]", reviewer runs `python3 release/release.py <library> [--minor|--major]`
11. Reviewer updates review doc status to `approved` with release version

## Integration Points
- **Reads**: Library source in `<library>/` (working tree), release script, SPEC.md, xtest
- **Writes**: Review documents `reviews/<library>-<hash>.md`
- **Executes**: `release/release.py` on permission; `xtest` during review
- **Uses**: Content hashing for staleness detection (no git required)

## Open Questions
1. How to handle multi-library reviews (dependencies)?
2. Review document retention — keep all or only latest per library?

## Status
- [ ] Plan approved
- [ ] Technical spec written
- [ ] Implementation started
- [ ] Testing
- [ ] Release