# rota

The office rota: a shift, the pay rules, and a day's schedule. Python 3, standard library
only. All money is **integer cents**; all times are **minutes since midnight**.

## Shifts

A shift is `Shift(worker, start, end)`. A shift ends later the same day, so `end > start`;
anything else raises `ValueError`. `minutes()` is `end - start`. `hours_text()` renders
whole hours and the remaining minutes as `"8h00"`, `"7h30"`.

## Pay

`pay_cents(minutes, rate_cents_per_hour)`:

1. A **thirty-minute unpaid break** is deducted when a shift is **longer than six hours**.
	Exactly six hours is paid in full — the comparison is strict.
2. The break is taken out **before** the overtime threshold is applied.
3. The first **forty paid minutes-hours** are paid at `rate_cents_per_hour`.
4. The rest is paid at **one and a half times** the rate.
5. Each part is computed separately and **truncated to the cent**, and the two parts are
	added. The total is not one division of the whole amount.

Worked examples, at a rate of 1000 cents an hour:

| Shift | Paid minutes | Total (cents) |
|-------|--------------|---------------|
| 4h (240 min) | 240 | 4000 |
| exactly 6h (360 min) | 360 | 6000 |
| 7h (420 min) | 390 | 6500 |
| 30h (1800 min) | 1770 | 29500 |
| 45h (2700 min) | 2670 | 46750 |

The 45-hour row is the one that matters: 40h at 1000 is 40000, and the remaining 4.5 paid
hours at 1500 is 6750.

## Schedule

`Schedule` holds a day's shifts.

- `add(shift)` refuses a shift that **overlaps** another shift for the same worker, raising
	`ValueError`; shifts for different workers never conflict.
- Two shifts that merely **touch** do not overlap: one ending at 12:00 and one starting at
	12:00 are fine. The conflict only fires when they share a minute.
- `total_minutes()` sums every shift on the rota, across workers.
- `by_worker(worker)` returns that worker's shifts in the order they were added.
- `conflicts(shift)` returns the existing shifts it would overlap.

## Deliverable

The implementation is correct as written. What is missing is a test suite, and the shape
of that suite is in `REQUEST.md`. `check.py` is the acceptance check.
