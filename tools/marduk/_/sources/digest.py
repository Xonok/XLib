"""Pull world-news feeds with a cheap model, then evaluate them for the digest."""

import json,os,subprocess,time,urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from .. import event

DEFAULT_PULL_MODEL="openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
DEFAULT_EVAL_MODELS=("opencode/big-pickle","opencode/deepseek-v4.1-flash")

class Digest:
	"""Two stages: a cheap pull for candidates, a better daily evaluation."""

	def __init__(self,id:str,options:dict):
		self.id=id
		self.feeds=_feeds(options.get("feeds"))
		self.pull_model=_model(options.get("pull_model",DEFAULT_PULL_MODEL),"pull_model")
		self.eval_models=_models(options.get("eval_models",list(DEFAULT_EVAL_MODELS)))
		self.interval_seconds=float(options.get("interval_seconds",3600.0))
		self.evaluate_seconds=float(options.get("evaluate_interval_seconds",86400.0))
		self.stale_seconds=float(options.get("stale_after_seconds",max(self.interval_seconds*3,self.evaluate_seconds*2)))
		self.timeout_seconds=float(options.get("timeout_seconds",180.0))
		self.max_items=int(options.get("max_items_per_feed",20))
		self.max_new=int(options.get("max_new_items",60))
		self.max_candidates=int(options.get("max_candidates",200))
		self.max_seen=int(options.get("max_seen",2000))
		self.max_age_days=float(options.get("max_age_days",3.0))
		self.candidate_days=float(options.get("candidate_days",3.0))
		self.run_dir=options.get("run_dir") or _default_run_dir()

	def interval(self)->float:
		return self.interval_seconds

	def stale_after(self)->float:
		return self.stale_seconds

	def keys(self)->list[tuple[str,str]]:
		"""The digest is news, not a health row."""
		return []

	def check(self,now:float,memory:dict|None=None,items=None,call=None)->list[event.Condition]:
		"""Pull new items, evaluate when due, and return this week's published items."""
		memory={} if memory is None else memory
		call=(lambda model,prompt,timeout: _run_model(model,prompt,timeout,self.run_dir)) if call is None else call
		self._roll_week(now,memory)
		items=_fetch(self.feeds,self.timeout_seconds,self.max_items) if items is None else items
		fresh=self._fresh(items,now,memory)
		if fresh:
			memory.setdefault("candidates",[]).extend(self._pull(fresh,now,memory,call))
		self._prune(now,memory)
		self._evaluate(now,memory,call)
		return self._conditions(now,memory)

	def _fresh(self,items:list[dict],now:float,memory:dict)->list[dict]:
		"""The items not seen before and not older than the age limit."""
		seen=memory.setdefault("seen",{})
		fresh=[]
		for item in items:
			url=item.get("url")
			if not url or url in seen:
				continue
			published=float(item.get("published") or now)
			if now-published>self.max_age_days*86400:
				seen[url]=now
				continue
			fresh.append(item)
		return fresh[:self.max_new]

	def _pull(self,fresh:list[dict],now:float,memory:dict,call)->list[dict]:
		"""One cheap-model call that turns feed items into candidate summaries."""
		prompt=_pull_prompt(fresh)
		text=call(self.pull_model,prompt,self.timeout_seconds)
		data=_json(text)
		candidates=data.get("candidates")
		if not isinstance(candidates,list):
			raise ValueError("the pull model returned no candidates list")
		result=[]
		for entry in candidates:
			if not isinstance(entry,dict):
				continue
			index=_index(entry.get("item"),len(fresh))
			if index is None:
				continue
			item=fresh[index]
			result.append({
				"title":_text(entry.get("title")) or item["title"],
				"summary":_text(entry.get("summary")),
				"url":item["url"],
				"source":item["source"],
				"at":now,
			})
		seen=memory.setdefault("seen",{})
		for item in fresh:
			seen[item["url"]]=now
		return result

	def _evaluate(self,now:float,memory:dict,call)->None:
		"""One better-model call a day; it may publish one item, or two exceptional ones."""
		published=memory.setdefault("published",[])
		if now-memory.get("last_eval",0)<self.evaluate_seconds:
			return
		candidates=memory.get("candidates") or []
		if not candidates:
			return
		if len(published)>=2:
			memory["last_eval"]=now
			return
		allowed=2-len(published)
		prompt=_eval_prompt(candidates,published)
		text,model=_eval_with_fallback(self.eval_models,prompt,self.timeout_seconds,call)
		data=_json(text)
		items=data.get("items")
		if not isinstance(items,list):
			raise ValueError(f"{model} returned no items list")
		chosen=[]
		for entry in items:
			if len(chosen)>=allowed:
				break
			if not isinstance(entry,dict):
				continue
			index=_index(entry.get("candidate"),len(candidates))
			if index is None:
				continue
			title=_text(entry.get("title")) or candidates[index]["title"]
			why=_text(entry.get("why"))
			if not why:
				continue
			if published and not entry.get("exceptional"):
				continue
			chosen.append({
				"title":title,
				"why":why,
				"url":candidates[index]["url"],
				"candidate":index,
				"exceptional":bool(entry.get("exceptional")),
				"at":now,
			})
		if len(chosen)==2 and not chosen[1]["exceptional"]:
			chosen=chosen[:1]
		published.extend(chosen)
		memory["last_eval"]=now
		memory["last_model"]=model
		if chosen:
			memory["candidates"]=_without(memory.get("candidates") or [],chosen)

	def _conditions(self,now:float,memory:dict)->list[event.Condition]:
		"""Every item published this week, so a re-check does not drop the store's keys."""
		week=_week(now)
		conditions=[]
		for index,item in enumerate(memory.get("published") or [],1):
			key=f"{self.id}:{week}:{index}"
			conditions.append(event.Condition(self.id,key,"news","World news",event.STATE_INFO,
				item["title"],f"{item['why']} — {item['url']}",checked=now))
		return conditions

	def _roll_week(self,now:float,memory:dict)->None:
		week=_week(now)
		if memory.get("week")!=week:
			memory["week"]=week
			memory["published"]=[]

	def _prune(self,now:float,memory:dict)->None:
		cutoff=now-self.candidate_days*86400
		candidates=[item for item in memory.get("candidates") or [] if item.get("at",0)>=cutoff]
		memory["candidates"]=candidates[-self.max_candidates:]
		seen=memory.get("seen") or {}
		if len(seen)>self.max_seen:
			ordered=sorted(seen.items(),key=lambda pair:pair[1],reverse=True)[:self.max_seen]
			memory["seen"]=dict(ordered)

def _feeds(value:object)->list[dict]:
	if not isinstance(value,list) or not value:
		raise ValueError("feeds must be a non-empty list")
	feeds=[]
	for entry in value:
		if not isinstance(entry,dict):
			raise ValueError("a feed must be an object")
		name=entry.get("name")
		url=entry.get("url")
		if not isinstance(name,str) or not name:
			raise ValueError("a feed needs a name")
		if not isinstance(url,str) or not url.startswith(("http://","https://")):
			raise ValueError(f"feed {name} needs an http(s) url")
		feeds.append({"name":name,"url":url})
	return feeds

def _model(value:object,name:str)->str:
	if not isinstance(value,str) or not value.strip():
		raise ValueError(f"{name} must be a non-empty model id")
	return value.strip()

def _models(value:object)->list[str]:
	if not isinstance(value,list) or not value:
		raise ValueError("eval_models must be a non-empty list")
	return [_model(entry,"eval_models entry") for entry in value]

def _fetch(feeds:list[dict],timeout:float,max_items:int)->list[dict]:
	items=[]
	for feed in feeds:
		try:
			body=_get(feed["url"],timeout)
			parsed=_parse(body,feed["name"])
		except Exception as exc:
			raise ValueError(f"{feed['name']}: {exc}")
		items.extend(parsed[:max_items])
	return items

def _get(url:str,timeout:float)->str:
	request=urllib.request.Request(url,headers={"User-Agent":"marduk/1"})
	with urllib.request.urlopen(request,timeout=timeout) as response:
		return response.read().decode("utf-8","replace")

def _parse(body:str,source:str)->list[dict]:
	root=ET.fromstring(body)
	items=[]
	for node in root.iter():
		name=_tag(node.tag)
		if name=="item":
			items.append(_rss_item(node,source))
		elif name=="entry":
			items.append(_atom_item(node,source))
	return [item for item in items if item["title"] and item["url"]]

def _rss_item(node,source:str)->dict:
	return _item(source,_child(node,"title"),_child(node,"link"),
		_child(node,"description"),_date(_child(node,"pubDate")))

def _atom_item(node,source:str)->dict:
	return _item(source,_child(node,"title"),_atom_link(node),
		_child(node,"summary") or _child(node,"content"),
		_date(_child(node,"published") or _child(node,"updated")))

def _item(source:str,title:str,url:str,summary:str,published:float)->dict:
	return {"title":title,"url":url,"summary":summary,"source":source,"published":published}

def _tag(tag:str)->str:
	return tag.rsplit("}",1)[-1]

def _child(node,name:str)->str:
	for child in node:
		if _tag(child.tag)==name:
			return "".join(child.itertext()).strip()
	return ""

def _atom_link(node)->str:
	for child in node:
		if _tag(child.tag)!="link":
			continue
		if child.get("rel") in (None,"alternate"):
			return (child.get("href") or "").strip()
	return ""

def _date(value:str)->float:
	if not value:
		return time.time()
	try:
		parsed=parsedate_to_datetime(value)
	except (TypeError,ValueError):
		try:
			parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
		except ValueError:
			return time.time()
	if parsed.tzinfo is None:
		parsed=parsed.replace(tzinfo=timezone.utc)
	return parsed.timestamp()

def _pull_prompt(items:list[dict])->str:
	lines=[
		"Compress these world-news feed items into candidates for a weekly digest.",
		"Return only JSON: {\"candidates\":[{\"item\": <number>, \"title\": \"<one line>\", \"summary\": \"<one sentence>\"}]}.",
		"Keep every item that reports a real world event; merge duplicates; drop sport, celebrity, routine market moves and opinion.",
		"Items:",
	]
	for index,item in enumerate(items):
		lines.append(f"[{index}] ({item['source']}) {item['title']}")
		if item.get("summary"):
			lines.append(item["summary"][:400])
	return "\n".join(lines)

def _eval_prompt(candidates:list[dict],published:list[dict])->str:
	lines=[
		"You are the editor of a weekly world-news digest.",
		"Choose at most two candidates that will still matter in a week. Prefer structural change: war, election, disaster, economy, law.",
		"Reject routine politics, sport, celebrity, market noise and anything forgotten by next week. One item is normal; a second only if it is clearly exceptional.",
		"If nothing qualifies, return {\"items\":[]}.",
		"Return only JSON: {\"items\":[{\"candidate\": <number>, \"title\": \"<one line>\", \"why\": \"<one sentence>\", \"exceptional\": true|false}]}.",
	]
	if published:
		lines.append("Already published this week (do not repeat):")
		for item in published:
			lines.append(f"- {item['title']}")
	lines.append("Candidates:")
	for index,item in enumerate(candidates):
		lines.append(f"[{index}] {item['title']} — {item.get('summary','')} ({item['source']})")
	return "\n".join(lines)

def _json(text:str)->dict:
	body=text.strip()
	if "```" in body:
		parts=body.split("```")
		if len(parts)>=2:
			body=parts[1]
	body=body.strip()
	start=body.find("{")
	end=body.rfind("}")
	if start<0 or end<start:
		raise ValueError(f"the model did not return JSON: {text[:200]}")
	try:
		data=json.loads(body[start:end+1])
	except json.JSONDecodeError as exc:
		raise ValueError(f"the model returned invalid JSON: {exc}: {text[:200]}")
	if not isinstance(data,dict):
		raise ValueError("the model returned JSON that is not an object")
	return data

def _index(value:object,length:int)->int|None:
	try:
		index=int(value)
	except (TypeError,ValueError):
		return None
	return index if 0<=index<length else None

def _text(value:object)->str:
	return value.strip() if isinstance(value,str) else ""

def _without(candidates:list[dict],chosen:list[dict])->list[dict]:
	urls={item["url"] for item in chosen}
	return [item for item in candidates if item["url"] not in urls]

def _week(now:float)->str:
	iso=datetime.fromtimestamp(now,tz=timezone.utc).isocalendar()
	return f"{iso.year}-W{iso.week:02d}"

def _default_run_dir()->str:
	return os.path.join(os.path.expanduser("~"),".cache","marduk","model-run")

def _run_model(model:str,prompt:str,timeout:float,run_dir:str|None=None)->str:
	run_dir=_default_run_dir() if run_dir is None else run_dir
	os.makedirs(run_dir,exist_ok=True)
	result=subprocess.run(["opencode","run","--model",model,"--format","json",prompt],
		capture_output=True,text=True,timeout=timeout,cwd=run_dir)
	if result.returncode!=0:
		raise ValueError(f"{model} exited {result.returncode}: {result.stderr.strip()}")
	texts=[]
	for line in result.stdout.splitlines():
		line=line.strip()
		if not line:
			continue
		try:
			record=json.loads(line)
		except json.JSONDecodeError:
			continue
		if record.get("type")=="text":
			texts.append((record.get("part") or {}).get("text",""))
	text="".join(texts).strip()
	if not text:
		raise ValueError(f"{model} returned no text")
	return text

def _eval_with_fallback(models:list[str],prompt:str,timeout:float,call)->tuple[str,str]:
	errors=[]
	for model in models:
		try:
			return call(model,prompt,timeout),model
		except Exception as exc:
			errors.append(f"{model}: {exc}")
	raise ValueError("no evaluation model answered: "+"; ".join(errors))
