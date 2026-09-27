# billing

Integer-cent invoice attribution to fiscal periods. All amounts are **integer cents** at
every stage — never introduce floating point, the payment provider rejects fractional
amounts outright.

## Fiscal calendar

The fiscal year starts on **1 April**, confirmed by finance against the consolidated
ledger. FY2026 therefore runs 2026-04-01 to 2027-03-31, and the quarters are:

| Period | First day | Last day | Days |
|--------|----------|----------|------|
| Q1 | 2026-04-01 | 2026-06-30 | 91 |
| Q2 | 2026-07-01 | 2026-09-30 | 92 |
| Q3 | 2026-10-01 | 2026-12-31 | 92 |
| Q4 | 2027-01-01 | 2027-03-31 | 90 |

A period's bounds are **inclusive of both its first and its last day**, and every day of
the year belongs to exactly one quarter.

## Attribution

`attribute(start, end, amount_cents)` splits a line's amount across every fiscal quarter
the span `[start, end]` touches:

1. For each spanned quarter, the days of the span inside it are counted inclusively of
   both ends.
2. A quarter that contributes **at least one day** is included.
3. Non-final quarters are prorated **by their share of the days in the whole span** — the
   denominator is the total number of days attributed across all quarters, not the length
   of any one quarter.
4. The final quarter receives the whole remaining amount, so the parts sum to
   `amount_cents` exactly.
5. If the span touches no quarter at all, the result is `[]`.

## Rounding

`money.prorate` and `money.pct` round **half up**: 2.5 becomes 3, 4.5 becomes 5. This is
deliberately not Python's `round()`, which is banker's rounding and would send 2.5 to 2
and 4.5 to 4. Do not reimplement either helper in terms of floats or `round()`.

## Reconciliation values

Finance reconciles against these. If a change moves any of them, the change is wrong, not
the number.

| # | Span | Amount (cents) | Attribution |
|---|------|---------------|-------------|
| 1 | 2026-08-01 .. 2026-08-31 | 9200 | Q2 → 9200 |
| 2 | 2026-07-01 .. 2026-09-30 | 4600 | Q2 → 4600 |
| 3 | 2026-06-30 .. 2026-07-15 | 3200 | Q1 → 200, Q2 → 3000 |
| 4 | 2026-06-01 .. 2026-07-31 | 46000 | Q1 → 22623, Q2 → 23377 |
| 5 | 2026-09-30 .. 2026-09-30 | 700 | Q2 → 700 |
| 6 | 2026-11-01 .. 2026-11-30 | 10000 | Q3 → 10000 |
