# patchlib

Small text utilities used by the publishing pipeline. Python 3, standard library only.

## `tokenizer`

- `words(text)` returns the words in `text`. A word is a run of **ASCII letters and the
	apostrophe** — `don't` is one word, `it's` is one word. **Digits, underscores and
	punctuation are not part of a word**: `x1` is the word `x`, and `snake_case` is the two
	words `snake` and `case`.
- `word_count(text)` is the number of words.

## `slugs`

- `slug(text)` makes a URL slug: **strip leading and trailing whitespace**, lowercase, and
	replace each space with a hyphen. The result has **no leading or trailing hyphen**.
- `slug("Hello World")` is `hello-world`; `slug(" Hello ")` is `hello`.

## `truncate`

- `truncate(text,limit)` returns `text` unchanged when `len(text) <= limit`.
- When it is **longer than** `limit`, it returns the first `limit - 3` characters followed
	by `...`, so the result is exactly `limit` characters. A string of exactly `limit`
	characters is **not** truncated.
- `truncate("hello world",8)` is `hello...`.

## `stats`

- `average_word_length(text)` is the mean character length of the words, and **`0.0` when
	there are no words** — it never raises.
- `longest_word(text)` is the word with the **most characters**; if two words tie, the
	first one wins. It is `""` when there are no words.

## Change set

`CHANGES.diff` changes the four modules above. The change adds `word_count` and is meant
to leave every rule in this document true.
