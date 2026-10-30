"""The built-in source kinds and the configured instances built from them."""

from . import apt,digest,freemodels,models,site

KINDS={"apt":apt.Apt,"digest":digest.Digest,"freemodels":freemodels.FreeModels,"models":models.Models,"site":site.Site}

def build(entries:list[dict])->tuple[list,list[str]]:
	"""Build one source per configured entry, in config order.

	Returns the sources and one notice per unknown kind or malformed entry;
	one bad entry does not stop the others.
	"""
	sources=[]
	notices=[]
	for entry in entries:
		kind=KINDS.get(entry["kind"])
		if kind is None:
			notices.append(f"unknown source: {entry['kind']}")
			continue
		try:
			sources.append(kind(entry["id"],entry))
		except (TypeError,ValueError) as exc:
			notices.append(f"{entry['id']}: {exc}")
	return sources,notices
