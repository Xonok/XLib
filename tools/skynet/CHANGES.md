# Skynet OpenCode 2 Migration Fix

## Problem

After migrating to OpenCode 2, Skynet's statistics were not including data from sessions. The tool was querying the wrong table (`message` instead of `session_message`), and the total token count column was showing zero for all models.

## Root Cause

OpenCode 2 stores assistant messages in the `session_message` table with the following structure:

- `session_message` table (not `message` table)
- `type` field to distinguish between 'user' and 'assistant' messages
- `session_id` column (separate from the data JSON)
- Message data in JSON format with fields like:
- `model.id` (e.g., "glm-4.7-flash")
- `model.providerID` (e.g., "zai")
- `tokens.input`, `tokens.output`, `tokens.reasoning`, `tokens.cache.read`, `tokens.cache.write`
- `finish` field
- `time.created` timestamp

## Solution

Modified `tools/skynet.py` in the `load_stats()` function:

1. Changed table from `message` to `session_message`
2. Added `WHERE type = 'assistant'` filter
3. Changed field extraction from:
- `$.modelID` → `$.model.id`
- Kept the same token and finish field paths
- Kept `time.created` path
4. Added COALESCE to calculate total tokens from input + output + reasoning + cache_read + cache_write (since `tokens.total` field is no longer present)

## Changes Made

```python
# Before:
SELECT json_extract(data, '$.modelID'),
    ...
FROM message
WHERE json_extract(data, '$.role') = 'assistant'
...

# After:
SELECT json_extract(data, '$.model.id'),
    ...
FROM session_message
WHERE type = 'assistant'
...
COALESCE(
    json_extract(data, '$.tokens.total'),
    (COALESCE(json_extract(data, '$.tokens.input'), 0) +
     COALESCE(json_extract(data, '$.tokens.output'), 0) +
     COALESCE(json_extract(data, '$.tokens.reasoning'), 0) +
     COALESCE(json_extract(data, '$.tokens.cache.read'), 0) +
     COALESCE(json_extract(data, '$.tokens.cache.write'), 0))
)
...
```

## Testing

The fix was verified by:
1. Running `skynet --window-hours 1` which now shows data from OpenCode 2 sessions
2. Checking that multiple models are tracked (glm-4.7-flash, dots-studio/dots-3-note-preview:free, thinkingmachines/inkling:free, etc.)
3. Verifying token counts are correctly extracted (input, output, reasoning, cache)
4. Verifying total tokens are calculated correctly (input + output + reasoning + cache)
5. Running xlint to ensure code formatting compliance

## Impact

- Skynet now correctly tracks usage statistics for OpenCode 2 sessions
- All assistant messages from recent sessions are included in statistics
- No breaking changes to the command-line interface
