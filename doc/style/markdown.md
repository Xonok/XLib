# Markdown style

Rules for Markdown files in this repo.

## Indentation

- Markdown files use tabs for indentation.
- Exempt: YAML frontmatter, which YAML requires be space-indented, and the contents
	of fenced code blocks, whatever their indentation. A fence is recognised after
	leading whitespace, so a block nested in a list item is a fence (`QN1N82Y`).
- A 4-space indented code block is still a violation: the convention is fenced
	blocks, and Markdown's indented-code syntax requires spaces by definition.
- A mid-line double space is a typo. Use one space between words and after
	punctuation; hard line breaks use an explicit backslash.
