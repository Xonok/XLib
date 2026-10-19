# HTML style

Rules specific to HTML. Read `style/common.md` for the language-independent
rules; this file only adds HTML-specific ones.

`xlint` checks these (`tools/xlint/_html.py`), on top of the generic checks
every language gets: no double blank line, no trailing whitespace, one final
newline, and no trailing blank line.

## Structure

- Every non-void tag is closed explicitly. There is no optional end tag and no
	implicit closing: `<p>` is closed by `</p>`, not by the block element that
	follows it.
- The void elements — `area`, `base`, `br`, `col`, `embed`, `hr`, `img`,
	`input`, `link`, `meta`, `param`, `source`, `track`, `wbr` — have no end,
	so they are never closed. A `</br>` is a finding.
- A closing tag closes the innermost open element. A tag that names an element
	below it closes that one and the elements above it on the way, which is a
	mis-nesting and not a shorthand: `<div><span></div>` is a finding.
- The content of a raw-text element — `script`, `style`, `textarea`, `title` —
	is text, not markup. A `<` in a script does not open a tag.

## Indentation

- HTML is indented with tabs, like everything else in this repo.
- A line that starts with a tag sits at the level of the element that tag opens
	or closes. A line of text is not placed by the nesting: the prose in an
	element is written at the element's own level or one deeper, and both are in
	use, so the rule leaves prose where the author put it.
- The depth is measured in the file's own unit — a tab, or the greatest common
	divisor of the file's space runs. A space-indented file is measured in its
	own spaces, so the finding names the depth rather than the unit.

## Comments

- A comment's content is markup the author commented out. It opens and closes
	nothing, and its indentation is the author's rather than the nesting's —
	which is the point of keeping it.
