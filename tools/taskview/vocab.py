#!/usr/bin/env python3
"""
vocab — the categories and tags this machine's task store may use.

The list is machine-specific, so it lives beside the store rather than in the
repository: `<data-dir>/vocab.yaml` (default `~/.local/share/taskview/vocab.yaml`).
A missing file means no vocabulary is configured and `taskupdate` accepts any
value; when the file exists, a value it does not list is refused before the row
is written, and a value that differs only in case, `-` or space is stored in the
house spelling instead (lowercase, `_` for them).
"""

import os,yaml
from pathlib import Path

try:
	from tools.taskview.taskview import resolve_data_dir
except ImportError:
	from taskview import resolve_data_dir

VOCAB_FILENAME = "vocab.yaml"

class VocabError(Exception):
	"""The vocabulary file exists but cannot be read as a category/tag list."""

def resolve_vocab_path(data_dir: Path | None = None) -> Path:
	"""The vocabulary beside the task store: `<data-dir>/vocab.yaml`."""
	if data_dir is None:
		data_dir = resolve_data_dir(None, os.environ)
	return Path(data_dir) / VOCAB_FILENAME

def load_vocab(path: Path | None = None) -> dict | None:
	"""The allowed categories and tags, or None when no file is configured.

	Returns `{"path", "categories", "tags"}` with both sets in house spelling.
	Raises VocabError for a file that exists but is not a category/tag mapping.
	"""
	path = resolve_vocab_path() if path is None else Path(path)
	if not path.is_file():
		return None
	try:
		with path.open("r", encoding="utf-8") as f:
			data = yaml.safe_load(f) or {}
	except (OSError, yaml.YAMLError) as e:
		raise VocabError(f"cannot read {path}: {e}") from e
	if not isinstance(data, dict):
		raise VocabError(f"malformed vocabulary in {path}: expected a mapping")
	categories = data.get("categories") or []
	tags = data.get("tags") or []
	if not isinstance(categories, list) or not isinstance(tags, list):
		raise VocabError(f"malformed vocabulary in {path}: categories and tags must be lists")
	return {
		"path": path,
		"categories": {normalise_value(value) for value in categories if str(value).strip()},
		"tags": {normalise_value(value) for value in tags if str(value).strip()},
	}

def normalise_value(text: str) -> str:
	"""House spelling: lowercase, with `_` standing in for a `-` or a space."""
	return str(text).strip().lower().replace("-", "_").replace(" ", "_")

def normalise_tags(tags: str) -> str:
	"""Comma-separated tags in house spelling, de-duplicated, order preserved."""
	seen = []
	for tag in str(tags).split(","):
		value = normalise_value(tag)
		if value and value not in seen:
			seen.append(value)
	return ",".join(seen)

def check_category(category: str, vocab: dict | None) -> str | None:
	"""The refusal message for a category outside the vocabulary, or None."""
	if vocab is None or category == "":
		return None
	if normalise_value(category) not in vocab["categories"]:
		return (f"category '{category}' is not in {vocab['path']}: "
			f"use one of {_listing(vocab['categories'])}, or add it to the file")
	return None

def check_tags(tags: str, vocab: dict | None) -> str | None:
	"""The refusal message for a tag outside the vocabulary, or None."""
	if vocab is None or tags == "":
		return None
	for tag in normalise_tags(tags).split(","):
		if tag and tag not in vocab["tags"]:
			return (f"tag '{tag}' is not in {vocab['path']}: "
				f"use one of {_listing(vocab['tags'])}, or add it to the file")
	return None

def _listing(values: set) -> str:
	"""The sorted vocabulary for a message, short enough to read in a terminal."""
	names = sorted(values)
	if len(names) > 12:
		return ", ".join(names[:12]) + f", ... ({len(names)} total)"
	return ", ".join(names)
