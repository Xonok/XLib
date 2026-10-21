# invoicer — the totals are wrong

Finance says account 7 should total **2160 cents** and it is coming out as 2200. I have
checked the number against the provider dashboard, so treat 2160 as correct — if your fix
produces something other than 2160 for account 7, the fix is wrong, not the number.

Two things I care about, because they have bitten us before:

- **Everything stays in integer cents.** The provider rejects fractional amounts outright.
	No floating point anywhere in the path, and no `round()` — that is banker's rounding and
	it will not give you the half-up behaviour the spec calls for.
- **Don't break the paths that are already right.** If your change makes behaviour that
	was correct before become incorrect, that is the bug.

Read `SPEC.md` and `invoicer.py`, work out what's wrong, and fix it.
