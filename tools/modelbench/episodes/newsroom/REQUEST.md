# newsroom — the shortlist

I have a week of world-news items from three outlets in `data/items.json`, and I do not
want to read all of it. Give me the shortlist of stories worth evaluating.

Do not check whether the stories are true — that is a different job. **Find the ones
that matter and group the same event across outlets.** If three outlets covered one
earthquake, I want one item naming all three ids, not three items.

Write `digest.json` as `SPEC.md` describes, with at most eight items. Prefer the stories
that will still matter next week; leave out the sport, celebrity, routine market and
weather noise. Run `python3 check.py` to confirm the shape and the grouping. Do not edit
`check.py`, `data/items.json`, `SPEC.md` or `REQUEST.md`.
