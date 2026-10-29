"""Deterministic checker for the newsroom episode.

It measures finding and aggregation, not factual validity: every selected id must exist
in the corpus, a multi-outlet event must be one digest item holding all of its ids, the
shortlist must reach the seeded signal stories, and an item made only of noise is a miss.
Whether a story is true is deliberately not a case.

Usage:
	python3 check.py          human-readable, exit 0/1
	python3 check.py --json   per-case results, for collateral-damage detection
"""

import hashlib,json,os,sys

ROOT=os.path.dirname(os.path.abspath(__file__))
CORPUS=os.path.join(ROOT,"data","items.json")
OUTPUT=os.path.join(ROOT,"digest.json")
MAX_ITEMS=8
MIN_RECALL=6

# The episode's own files, hashed: a change here is an edit to the instrument, not a
# model finding. Updated with the file when the episode itself changes.
EXPECTED={
	"data/items.json":"71451777bafb3da3de1723587b579d26c525e20a2266176c19217000e443fc35",
	"SPEC.md":"857edf6e926a10e78c1c95576848a76c3530cb7c9eda60db54c722b187366bb5",
}

# The seeded stories: one group per event, every outlet's id for it.
SIGNAL={
	"quake":["bbc-01","guard-01","alj-01"],
	"rate":["bbc-02","guard-02"],
	"election":["bbc-03","guard-03","alj-02"],
	"war":["bbc-04","guard-04","alj-03"],
	"hurricane":["bbc-05","guard-05"],
	"court":["bbc-06","guard-06"],
	"outbreak":["bbc-07","guard-07"],
	"fusion":["bbc-08","guard-08"],
}

# Items with no signal or ambiguous id; an item built only from these is noise.
NOISE={
	"bbc-09","guard-09","alj-04","bbc-10","guard-10","alj-05","bbc-11","guard-11",
	"alj-06","bbc-12","guard-12","alj-07","bbc-13","guard-13","alj-08","bbc-14",
	"guard-14","alj-09",
}

def _digest(path):
	with open(path,"rb") as f:
		return hashlib.sha256(f.read()).hexdigest()

def _corpus_ids():
	with open(CORPUS) as f:
		return {item["id"] for item in json.load(f)}

def _items():
	"""The digest's items, or (None, why not)."""
	if not os.path.exists(OUTPUT):
		return None,"digest.json is missing"
	try:
		with open(OUTPUT) as f:
			data=json.load(f)
	except (OSError,ValueError) as exc:
		return None,f"digest.json is not JSON: {exc}"
	if not isinstance(data,dict) or not isinstance(data.get("items"),list):
		return None,"digest.json must be an object with an items list"
	return data["items"],""

def _ids(item):
	if not isinstance(item,dict):
		return []
	value=item.get("ids")
	return [entry for entry in value if isinstance(entry,str)] if isinstance(value,list) else []

def cases():
	out=[]
	def unchanged():
		changed=[path for path,expected in EXPECTED.items()
			if _digest(os.path.join(ROOT,path))!=expected]
		return not changed,("changed: "+", ".join(changed)) if changed \
			else "the corpus and the brief are untouched"
	out.append({"account":"corpus-unchanged","guard":True,
		"witnesses":"the task's data and terms are intact","run":unchanged})

	def output_valid():
		items,error=_items()
		if error:
			return False,error
		if not 1<=len(items)<=MAX_ITEMS:
			return False,f"{len(items)} item(s); between 1 and {MAX_ITEMS} are required"
		return True,f"{len(items)} item(s)"
	out.append({"account":"output-valid","guard":False,
		"witnesses":"a digest exists in the stated shape","run":output_valid})

	def schema():
		items,error=_items()
		if error:
			return False,error
		for index,item in enumerate(items):
			ids=_ids(item)
			if not ids:
				return False,f"item {index} has no ids"
			if not isinstance(item.get("title"),str) or not item["title"].strip():
				return False,f"item {index} has no title"
			if not isinstance(item.get("why"),str) or not item["why"].strip():
				return False,f"item {index} has no why"
			if len(item["title"])>160:
				return False,f"item {index} title is longer than 160 characters"
			if len(item["why"])>300:
				return False,f"item {index} why is longer than 300 characters"
		return True,"every item has ids, a title and a why"
	out.append({"account":"schema","guard":False,
		"witnesses":"each item carries the fields the brief asked for","run":schema})

	def grounded():
		items,error=_items()
		if error:
			return False,error
		known=_corpus_ids()
		seen=set()
		for index,item in enumerate(items):
			for item_id in _ids(item):
				if item_id not in known:
					return False,f"item {index} invents the id {item_id}"
				if item_id in seen:
					return False,f"the id {item_id} is used twice"
				seen.add(item_id)
		return True,"every id is in the corpus and used once"
	out.append({"account":"grounded","guard":False,
		"witnesses":"no invented ids and no duplicate ids","run":grounded})

	def aggregated():
		items,error=_items()
		if error:
			return False,error
		selected={}
		for name,ids in SIGNAL.items():
			found=[item for item in items if set(ids)&set(_ids(item))]
			if found:
				selected[name]=(found,ids)
		if not selected:
			return False,"no seeded story was selected"
		broken=[]
		for name,(found,ids) in selected.items():
			if len(found)!=1:
				broken.append(f"{name} is split across {len(found)} items")
			elif not set(ids)<=set(_ids(found[0])):
				missing=[item_id for item_id in ids if item_id not in _ids(found[0])]
				broken.append(f"{name} misses {', '.join(missing)}")
		return not broken,"; ".join(broken) if broken else "every selected event is one item with all its ids"
	out.append({"account":"aggregated","guard":False,
		"witnesses":"the same event from several outlets is one item","run":aggregated})

	def recall():
		items,error=_items()
		if error:
			return False,error
		found=[name for name,ids in SIGNAL.items()
			if any(set(ids)&set(_ids(item)) for item in items)]
		return len(found)>=MIN_RECALL,f"{len(found)} of {len(SIGNAL)} seeded stories selected; at least {MIN_RECALL} required"
	out.append({"account":"recall","guard":False,
		"witnesses":"the shortlist reaches the stories worth evaluating","run":recall})

	def precision():
		items,error=_items()
		if error:
			return False,error
		if not items:
			return False,"the shortlist is empty"
		noise=[]
		for index,item in enumerate(items):
			ids=_ids(item)
			if ids and set(ids)<=NOISE:
				noise.append(f"item {index} is noise only")
		return not noise,"; ".join(noise) if noise else "no item is built only from noise"
	out.append({"account":"precision","guard":False,
		"witnesses":"the shortlist is not filled with sport, celebrity or market noise","run":precision})
	return out

def main():
	results=[]
	for case in cases():
		try:
			passed,detail=case["run"]()
		except Exception as exc:
			passed,detail=False,f"{type(exc).__name__}: {exc}"
		results.append({"account":case["account"],"passed":bool(passed),"guard":case["guard"],
			"witnesses":case["witnesses"],"detail":detail})
	if "--json" in sys.argv:
		print(json.dumps({"cases":results,"passed":sum(r["passed"] for r in results),
			"n":len(results)},indent=2))
		return 0 if all(r["passed"] for r in results) else 1
	for result in results:
		if not result["passed"]:
			print("FAIL",f"{result['account']}: {result['detail']}  [{result['witnesses']}]")
	failed=[result for result in results if not result["passed"]]
	print(f"{len(results)-len(failed)}/{len(results)} cases passed")
	return 0 if not failed else 1

if __name__=="__main__":
	sys.exit(main())
