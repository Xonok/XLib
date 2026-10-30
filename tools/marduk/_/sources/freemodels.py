"""List the currently-free models in a configured provider as a free section."""

import json,subprocess,urllib.request
from .. import event

CONSOLE_COMMAND=("opencode","models")
OPENROUTER_URL="https://openrouter.ai/api/v1/models"
MODELS_DEV_URL="https://models.dev/api.json"

class FreeModels:
	"""Free models in a provider, shown as a live list rather than news."""

	def __init__(self,id:str,options:dict):
		self.id=id
		self.prefixes=[_term(term) for term in _terms(options.get("prefixes",[]))]
		self.interval_seconds=float(options.get("interval_seconds",3600.0))
		self.timeout_seconds=float(options.get("timeout_seconds",30.0))
		self.stale_seconds=float(options.get("stale_after_seconds",max(self.interval_seconds*3,180.0)))
		self.prices_seconds=float(options.get("prices_refresh_seconds",21600.0))

	def interval(self)->float:
		return self.interval_seconds

	def stale_after(self)->float:
		return self.stale_seconds

	def keys(self)->list[tuple[str,str]]:
		"""Dynamic: the rows come from the store once the first check lands."""
		return []

	def check(self,now:float,memory:dict|None=None,console=None,openrouter=None,prices=None)->list[event.Condition]:
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
		records=[]
		for model_id in sorted(current):
			entry=current[model_id]
			if entry["free"] is not True:
				continue
			if self.prefixes and not any(term in model_id for term in self.prefixes):
				continue
			where=", ".join(sorted(entry["where"]))
			records.append(event.Condition(self.id,f"{self.id}:{model_id}","free",model_id,event.STATE_OK,where,detail=where,checked=now))
		return records

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
	request=urllib.request.Request(url,headers={"User-Agent":"marduk/1"})
	with urllib.request.urlopen(request,timeout=timeout) as response:
		return json.loads(response.read().decode("utf-8"))

def _normalise(model_id:str)->str:
	if model_id.startswith("openrouter/"):
		return model_id[len("openrouter/"):]
	return model_id

def _catalogue(console_ids:list[str],openrouter:dict,console_free:dict)->dict:
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

def _openrouter_models(payload:dict)->dict:
	models={}
	for entry in payload.get("data") or []:
		model_id=entry.get("id")
		if not model_id:
			continue
		pricing=entry.get("pricing") or {}
		prompt=_number(pricing.get("prompt"))
		completion=_number(pricing.get("completion"))
		free=None
		if prompt is not None and completion is not None:
			free=prompt==0 and completion==0
		models[model_id]={"free":free}
	return models

def _number(value:object)->float|None:
	try:
		return float(value)
	except (TypeError,ValueError):
		return None

def _terms(value:object)->list:
	if value is None:
		return []
	if not isinstance(value,list):
		raise ValueError("prefixes must be a list")
	return value

def _term(value:object)->str:
	if not isinstance(value,str) or not value.strip():
		raise ValueError("a prefixes entry must be a non-empty string")
	return value.strip().lower()
