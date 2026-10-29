"""Read the model catalogues and report new models and paid-to-free changes."""

import json,subprocess,urllib.request
from .. import event

CONSOLE_COMMAND=("opencode","models")
OPENROUTER_URL="https://openrouter.ai/api/v1/models"
MODELS_DEV_URL="https://models.dev/api.json"

class Models:
	"""The console and OpenRouter catalogues, diffed against the last run."""

	def __init__(self,id:str,options:dict):
		self.id=id
		self.powerful=[_term(term) for term in _terms(options.get("powerful"))]
		self.interval_seconds=float(options.get("interval_seconds",3600.0))
		self.timeout_seconds=float(options.get("timeout_seconds",30.0))
		self.stale_seconds=float(options.get("stale_after_seconds",max(self.interval_seconds*3,180.0)))
		self.prices_seconds=float(options.get("prices_refresh_seconds",21600.0))

	def interval(self)->float:
		return self.interval_seconds

	def stale_after(self)->float:
		return self.stale_seconds

	def keys(self)->list[tuple[str,str]]:
		"""A model is news, not a health row."""
		return []

	def check(self,now:float,memory:dict|None=None,console=None,openrouter=None,prices=None)->list[event.Condition]:
		"""Diff both catalogues against the memory; empty memory is the seed."""
		console=self._read_console if console is None else console
		openrouter=self._read_openrouter if openrouter is None else openrouter
		prices=self._read_prices if prices is None else prices
		memory={} if memory is None else memory
		console_ids=console()
		openrouter_models=openrouter()
		if "prices" not in memory or now-memory.get("prices_at",0)>=self.prices_seconds:
			memory["prices"]=_console_free(prices(),console_ids)
			memory["prices_at"]=now
		current=_catalogue(console_ids,openrouter_models,memory["prices"])
		if not memory.get("seeded"):
			memory["seeded"]=True
			memory["seen"]={model_id:entry["free"] for model_id,entry in current.items()}
			return []
		seen=memory.setdefault("seen",{})
		records=[]
		for model_id in sorted(current):
			entry=current[model_id]
			if model_id not in seen:
				records.append(_record(self.id,model_id,"new",entry,now,powerful=self._powerful(model_id)))
			elif seen[model_id] is False and entry["free"] is True and self._powerful(model_id):
				records.append(_record(self.id,model_id,"free",entry,now,powerful=True))
			seen[model_id]=entry["free"]
		return records

	def _powerful(self,model_id:str)->bool:
		lowered=model_id.lower()
		return any(term in lowered for term in self.powerful)

	def _read_console(self)->list[str]:
		return _console(list(CONSOLE_COMMAND),self.timeout_seconds)

	def _read_openrouter(self)->dict:
		return _openrouter_models(_openrouter(OPENROUTER_URL,self.timeout_seconds))

	def _read_prices(self)->dict:
		return _prices(MODELS_DEV_URL,self.timeout_seconds)

def _console(command:list[str],timeout:float)->list[str]:
	result=subprocess.run(command,capture_output=True,text=True,timeout=timeout)
	if result.returncode!=0:
		raise ValueError(f"{' '.join(command)} exited {result.returncode}: {result.stderr.strip()}")
	return [line.strip() for line in result.stdout.splitlines() if line.strip()]

def _openrouter(url:str,timeout:float)->dict:
	return _get_json(url,timeout)

def _prices(url:str,timeout:float)->dict:
	return _get_json(url,timeout)

def _get_json(url:str,timeout:float)->dict:
	"""Fetch JSON; some hosts refuse urllib's default user agent."""
	request=urllib.request.Request(url,headers={"User-Agent":"marduk/1"})
	with urllib.request.urlopen(request,timeout=timeout) as response:
		return json.loads(response.read().decode("utf-8"))

def _normalise(model_id:str)->str:
	if model_id.startswith("openrouter/"):
		return model_id[len("openrouter/"):]
	return model_id

def _catalogue(console_ids:list[str],openrouter:dict,console_free:dict)->dict:
	"""One entry per model, merged across the catalogues that carry it."""
	current={}
	for raw in console_ids:
		model_id=_normalise(raw)
		entry=current.setdefault(model_id,{"where":set(),"free":None})
		entry["where"].add("console")
		entry["free"]=_merge_free(entry["free"],console_free.get(model_id))
	for model_id,model in openrouter.items():
		entry=current.setdefault(model_id,{"where":set(),"free":None})
		entry["where"].add("openrouter")
		entry["free"]=_merge_free(entry["free"],model["free"])
	return current

def _merge_free(old:bool|None,new:bool|None)->bool|None:
	if old is True or new is True:
		return True
	if old is False or new is False:
		return False
	return None

def _console_free(prices:dict,console_ids:list[str])->dict[str,bool]:
	"""The console catalogue's free flag from the model database's costs."""
	free={}
	for raw in console_ids:
		if raw.startswith("openrouter/"):
			continue
		provider,_,model=raw.partition("/")
		if not model:
			continue
		cost=((prices.get(provider) or {}).get("models") or {}).get(model) or {}
		cost=cost.get("cost") or {}
		input_cost=_number(cost.get("input"))
		output_cost=_number(cost.get("output"))
		if input_cost is None or output_cost is None:
			continue
		free[_normalise(raw)]=input_cost==0 and output_cost==0
	return free

def _openrouter_free(pricing:dict)->bool|None:
	prompt=_number(pricing.get("prompt"))
	completion=_number(pricing.get("completion"))
	if prompt is None or completion is None:
		return None
	return prompt==0 and completion==0

def _number(value:object)->float|None:
	try:
		return float(value)
	except (TypeError,ValueError):
		return None

def _openrouter_models(payload:dict)->dict:
	"""{id: {free}} for the OpenRouter catalogue."""
	models={}
	for entry in payload.get("data") or []:
		model_id=entry.get("id")
		if not model_id:
			continue
		models[model_id]={"free":_openrouter_free(entry.get("pricing") or {})}
	return models

def _record(source_id:str,model_id:str,kind:str,entry:dict,now:float,powerful:bool)->event.Condition:
	where=", ".join(sorted(entry["where"]))
	key=f"{source_id}:{kind}:{model_id}"
	if kind=="new":
		title=f"new model: {model_id}" if not powerful else f"new powerful model: {model_id}"
		detail=f"new in {where}" + (", free" if entry["free"] else "")
	else:
		title=f"powerful model now free: {model_id}"
		detail=f"now free in {where}"
	return event.Condition(source_id,key,"news",model_id,event.STATE_INFO,title,detail,checked=now)

def _terms(value:object)->list:
	if value is None:
		return []
	if not isinstance(value,list):
		raise ValueError("powerful must be a list")
	return value

def _term(value:object)->str:
	if not isinstance(value,str) or not value.strip():
		raise ValueError("a powerful entry must be a non-empty string")
	return value.strip().lower()
