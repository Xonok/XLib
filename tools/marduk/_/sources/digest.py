"""Pull world-news feeds once a day and publish one item from yesterday."""

import json,os,subprocess,time,urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from .. import event

DEFAULT_PULL_MODEL="openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
DEFAULT_EVAL_MODELS=("opencode/big-pickle","opencode/deepseek-v4.1-flash")

class Digest:
	"""One daily run: pull the feeds, then pick yesterday's most important item."""

	def __init__(self,id:str,options:dict):
		self.id=id
		self.feeds=_feeds(options.get("feeds"))
		self.pull_model=_model(options.get("pull_model",DEFAULT_PULL_MODEL),"pull_model")
		self.eval_models=_models(options.get("eval_models",list(DEFAULT_EVAL_MODELS)))
		self.interval_seconds=float(options.get("interval_seconds",86400.0))
		self.stale_seconds=float(options.get("stale_after_seconds",max(self.interval_seconds*3,180.0)))
		self.timeout_seconds=float(options.get("timeout_seconds",180.0))
		self.max_items=int(options.get("max_items_per_feed",20))
		self.max_new=int(options.get("max_new_items",60))
		self.max_candidates=int(options.get("max_candidates",200))
		self.max_seen=int(options.get("max_seen",2000))
		self.max_age_days=float(options.get("max_age_days",3.0))
		self.candidate_days=float(options.get("candidate_days",3.0))
		self.accept_all=bool(options.get("accept_all",False))
		self.run_dir=options.get("run_dir") or _default_run_dir()

	def interval(self)->float:
		return self.interval_seconds

	def stale_after(self)->float:
		return self.stale_seconds

	def keys(self)->list[tuple[str,str]]:
		"""The digest is news, not a health row."""
		return []

	def check(self,now:float,memory:dict|None=None,items=None,call=None)->list[event.Condition]:
		"""Pull new items, evaluate yesterday's candidates, and return the latest pick."""
		memory={} if memory is None else memory
		self._migrate(memory)
		call=(lambda model,prompt,timeout: _run_model(model,prompt,timeout,self.run_dir)) if call is None else call
		items=_fetch(self.feeds,self.timeout_seconds,self.max_items) if items is None else items
		fresh=self._fresh(items,now,memory)
		if fresh:
			memory.setdefault("candidates",[]).extend(self._pull(fresh,now,memory,call))
		self._prune(now,memory)
		self._evaluate(now,memory,call)
		return self._conditions(now,memory)

	def _migrate(self,memory:dict)->None:
		"""A weekly-state memory has no day field; start clean rather than guess."""
		if memory.get("version")==2:
			return
		if memory:
			memory.clear()
		memory["version"]=2

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
				"day":_day(float(item.get("published") or now)),
				"at":now,
			})
		seen=memory.setdefault("seen",{})
		for item in fresh:
			seen[item["url"]]=now
		return result

	def _evaluate(self,now:float,memory:dict,call)->None:
		"""Pick exactly one candidate from yesterday, once that day has ended."""
		target=_day(now-86400)
		if memory.get("last_eval_day")==target:
			return
		candidates=[item for item in memory.get("candidates") or [] if item.get("day")==target]
		if not candidates:
			return
		memory["published_pool"]=list(candidates)
		if self.accept_all:
			memory["published"]=[{
				"title":item.get("title",""),
				"why":item.get("summary","") or "accepted (accept_all mode)",
				"url":item.get("url",""),
				"day":target,
				"at":now,
			} for item in candidates]
			memory["last_eval_day"]=target
			memory["last_model"]="accept-all"
			memory["candidates"]=[item for item in memory.get("candidates") or [] if item.get("day")!=target]
			return
		prompt=_eval_prompt(candidates)
		text,model=_eval_with_fallback(self.eval_models,prompt,self.timeout_seconds,call)
		data=_json(text)
		items=data.get("items")
		if not isinstance(items,list) or not items:
			raise ValueError(f"{model} did not pick an item")
		chosen=None
		for entry in items:
			if not isinstance(entry,dict):
				continue
			index=_index(entry.get("candidate"),len(candidates))
			if index is None:
				continue
			why=_text(entry.get("why")) or candidates[index].get("summary") or "picked from yesterday's candidates"
			chosen={
				"title":_text(entry.get("title")) or candidates[index]["title"],
				"why":why,
				"url":candidates[index]["url"],
				"day":target,
				"at":now,
			}
			break
		if chosen is None:
			raise ValueError(f"{model} returned no usable item")
		memory["published"]=[chosen]
		memory["last_eval_day"]=target
		memory["last_model"]=model
		memory["candidates"]=[item for item in memory.get("candidates") or [] if item.get("day")!=target]

	def _conditions(self,now:float,memory:dict)->list[event.Condition]:
		"""The daily pick(s); accept_all publishes every candidate."""
		published=memory.get("published") or []
		if not published:
			return []
		day=published[-1]["day"]
		result=[]
		for index,item in enumerate(published):
			if len(published)==1:
				key=f"{self.id}:{item['day']}"
			else:
				key=f"{self.id}:{item['day']}:{index}"
			result.append(event.Condition(self.id,key,"news","World news",event.STATE_INFO,
				item["title"],f"Pick for {item['day']}. {item['why']} — {item['url']}",
				checked=_day_end(now),replace=True))
		return result

	def _prune(self,now:float,memory:dict)->None:
		cutoff=now-self.candidate_days*86400
		target=_day(now-86400)
		candidates=[item for item in memory.get("candidates") or []
			if item.get("at",0)>=cutoff and item.get("day","")>=target]
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
		parsed=parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
	return parsed.timestamp()

def _pull_prompt(items:list[dict])->str:
	lines=[
		"Compress these world-news feed items into candidates for a daily digest.",
		"Return only JSON: {\"candidates\":[{\"item\": <number>, \"title\": \"<one line>\", \"summary\": \"<one sentence>\"}]}.",
		"Keep every item that reports a real world event; merge duplicates; drop sport, celebrity, routine market moves and opinion.",
		"Items:",
	]
	for index,item in enumerate(items):
		lines.append(f"[{index}] ({item['source']}) {item['title']}")
		if item.get("summary"):
			lines.append(item["summary"][:400])
	return "\n".join(lines)

def _eval_prompt(candidates:list[dict])->str:
	lines=[
		"You are the editor of a daily world-news digest.",
		"Pick exactly one candidate — the most interesting or important story from yesterday.",
		"Prefer structural change: war, election, disaster, economy, law, science, public health. Reject sport, celebrity, routine market moves, routine weather and opinion.",
		"Return only JSON: {\"items\":[{\"candidate\": <number>, \"title\": \"<one line>\", \"why\": \"<one sentence>\"}]}.",
		"One item, not zero and not two.",
		"Candidates (all published yesterday):",
	]
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

def _day(now:float)->str:
	return datetime.fromtimestamp(now).strftime("%Y-%m-%d")

def _day_end(now:float)->float:
	"""The last second of yesterday, so the entry is dated to the day it covers."""
	start=datetime.fromtimestamp(now).replace(hour=0,minute=0,second=0,microsecond=0)
	return start.timestamp()-1.0

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
