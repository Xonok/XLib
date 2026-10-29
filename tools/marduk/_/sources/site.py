"""Check the configured sites over HTTPS."""

import time,urllib.error,urllib.request
from .. import event

OPENER=urllib.request.urlopen

class Site:
	"""One site-health source: every target checked on one interval."""

	def __init__(self,id:str,options:dict):
		self.id=id
		self.targets=[_target(entry) for entry in _targets(options.get("targets"))]
		for target in self.targets:
			target["key"]=f"{id}:{target['name']}"
		self.interval_seconds=float(options.get("interval_seconds",60.0))
		self.timeout_seconds=float(options.get("timeout_seconds",10.0))
		self.stale_seconds=float(options.get("stale_after_seconds",max(self.interval_seconds*3,180.0)))

	def interval(self)->float:
		return self.interval_seconds

	def stale_after(self)->float:
		return self.stale_seconds

	def keys(self)->list[tuple[str,str]]:
		"""The health keys, so the panel names every target before the first check."""
		return [(target["key"],target["name"]) for target in self.targets]

	def check(self,now:float,opener=None)->list[event.Condition]:
		"""Check every target; any HTTP answer means the server is up."""
		opener=OPENER if opener is None else opener
		return [_check_one(self.id,target,self.timeout_seconds,now,opener) for target in self.targets]

def _targets(value:object)->list:
	if value is None:
		return []
	if not isinstance(value,list):
		raise ValueError("targets must be a list")
	return value

def _target(entry:object)->dict:
	"""Turn one target entry into a name and a URL."""
	if isinstance(entry,str):
		return {"name":entry,"url":f"https://{entry}/"}
	if isinstance(entry,dict):
		name=entry.get("name") or entry.get("url")
		if not name:
			raise ValueError("a target needs a name or a URL")
		return {"name":str(name),"url":str(entry.get("url") or f"https://{name}/")}
	raise ValueError("a target must be a string or an object")

def _check_one(source_id:str,target:dict,timeout:float,now:float,opener)->event.Condition:
	name=target["name"]
	key=target["key"]
	start=time.monotonic()
	try:
		with opener(target["url"],timeout=timeout) as response:
			code=getattr(response,"status",200) or 200
	except urllib.error.HTTPError as exc:
		code=exc.code
	except (urllib.error.URLError,OSError,ValueError) as exc:
		elapsed=time.monotonic()-start
		reason=getattr(exc,"reason",exc)
		return event.Condition(source_id,key,"health",name,event.STATE_ALERT,f"{name} is down",f"{reason} ({elapsed*1000:.0f} ms)",checked=now)
	elapsed=time.monotonic()-start
	if code>=500:
		state,title=event.STATE_ALERT,f"{name} is down"
	elif code>=400:
		state,title=event.STATE_WARN,f"{name} is degraded"
	else:
		state,title=event.STATE_OK,f"{name} is up"
	return event.Condition(source_id,key,"health",name,state,title,f"HTTP {code} ({elapsed*1000:.0f} ms)",checked=now)
