# invoicer

Integer-cents invoice calculator. All amounts are **integer cents** at every stage. Never
introduce floating point: the payment provider rejects fractional amounts outright, and
rounding applied earlier in the pipeline changes the total.

## Specification

1. `subtotal` = sum over lines of `unit_cents * qty`.
2. `discount` is applied to the **subtotal**, as an integer percentage truncated toward
	 zero.
3. `tax` is applied to the **discounted amount** — not the subtotal — as an integer
	 percentage, rounded half up.
4. `total` = discounted amount + tax.

## Known-good values

These are the numbers finance reconciles against. If a change makes any of them move, the
change is wrong, not the number.

| Account | Lines (`unit_cents`, `qty`) | discount % | tax % | total (cents) |
|---------|------------------------------|-----------|-------|----------------|
| 7 | `[(1000, 2)]` | 10 | 20 | **2160** |
| 12 | `[(250, 4), (99, 3)]` | 0 | 20 | 1357 |
| 31 | `[(10000, 1)]` | 33 | 5 | 6735 |

Account 12 has no discount, which is why it does not discriminate between "tax on
subtotal" and "tax on discounted" — it is a regression guard, not a bug witness.
