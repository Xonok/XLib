# xhttp Test Rules

## Expected Failures

**`@unittest.expectedFailure` is ONLY for features that are deliberately NOT implemented.**

It is NOT for:
- Bugs in implemented features
- Edge cases that "should work but don't"
- Known defects in working code

If the code attempts to support a feature, a test of that feature failing is a **real failure**, not an expected one.

### Examples

| Situation | Marker |
|-----------|--------|
| WebSocket sender doesn't catch `BrokenPipeError` | ❌ No `expectedFailure` — sender is implemented, this is a bug |
| `send_file` path traversal not implemented | ✅ `expectedFailure` — feature deliberately omitted |
| Unmasked client frames rejected | ❌ No `expectedFailure` — correct behavior per RFC 6455 |
| Leftover bytes lost during WS upgrade | ❌ No `expectedFailure` — upgrade is implemented, this is a bug |

### Why This Matters

- `expectedFailure` hides real problems from the test report
- CI should fail on implementation bugs so they get fixed
- The test suite should show the true state of the implementation
- "Expected failure" means "we chose not to do this", not "this is broken"

---

## Related Documents

- `SPEC.md` — lists known defects (these are bugs, not expected failures)
- `test_xhttp.py` — standalone test for basic parse/runtime behavior
- `test/README.md` — test group descriptions
