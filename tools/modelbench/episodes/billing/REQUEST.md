# billing — the quarter totals are wrong

Two things have gone wrong in the same week and I do not think they are the same bug.

**Everything that lands on a boundary day has vanished.** A line that starts on the first
of a quarter, or a line sitting entirely on the last day of a quarter, is not appearing in
the attribution at all — `attribute()` hands back nothing for it. Lines in the middle of a
quarter are fine.

**A line that crosses a quarter boundary is being charged too much to the first quarter.**
One invoice covering the whole of June plus the first month of the next quarter came out
with more than it should in the earlier period.

Two things I care about, because they have bitten us before:

- **Our fiscal year starts on 1 April, not 1 January.** Finance checked this against the
	consolidated ledger, so treat it as settled. If your change puts the year back on
	January, the change is wrong, not the calendar.
- **Everything stays in integer cents, and rounding stays half up.** No floating point
	anywhere in the path, and do not swap `prorate` or `pct` for `round()` — that is
	banker's rounding and it moves the totals by whole cents.

Read `SPEC.md`, `fiscal.py`, `billing.py` and `money.py`, work out what is wrong, fix it,
and confirm with `check.py`. Do not break the paths that already work: `check.py` has
cases that pass today and must still pass afterwards.
