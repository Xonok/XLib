# newsroom — find and aggregate the stories worth evaluating

`data/items.json` is a week of world-news items from three outlets. Each item has an
`id`, a `source`, a `title`, a `summary` and a `published` time. The same event often
appears in more than one outlet under a different id.

## What to produce

Write `digest.json` in the project root:

```json
{
	"items": [
		{
			"ids": ["bbc-01", "guard-01"],
			"title": "One line that names the event",
			"why": "One sentence on why it is worth evaluating."
		}
	]
}
```

Rules:

1. **One item per event.** When several corpus items report the same event, put all of
	their ids in one digest item. Do not split the event across items and do not list the
	same id twice.
2. **Use corpus ids only.** Every id in `ids` must exist in `data/items.json`, and every
	id must be used at most once across the whole digest. Do not invent an id or a fact.
3. **Select what is worth evaluating.** Prefer structural change — war, election,
	disaster, economy, law, science, public health. Leave out sport, celebrity, routine
	market moves, routine weather, product and lifestyle pieces, and opinion.
4. **Do not judge validity.** The task is to find and group the stories, not to verify
	them. Do not reject a story because a claim is unconfirmed, and do not add outside
	facts to check it.
5. **At most eight items.** One item per event; fewer is fine when fewer qualify.
6. **title and why are short.** The title is one line; `why` is one sentence.

`check.py` is the acceptance check. Run `python3 check.py` after writing `digest.json`,
and `python3 check.py --json` for the per-case detail. Do not edit `check.py`,
`data/items.json`, `SPEC.md` or `REQUEST.md`.
