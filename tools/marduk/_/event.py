"""The condition record and the transitions it produces."""

import time

STATE_OK="ok"
STATE_WARN="warn"
STATE_ALERT="alert"
STATE_INFO="info"

class Condition:
	"""The current state of one check, keyed by its source and key."""

	__slots__=("source","key","kind","name","state","title","detail","since","checked","replace")

	def __init__(self,source:str,key:str,kind:str,name:str,state:str,title:str="",detail:str="",since:float|None=None,checked:float|None=None,replace:bool=False):
		now=time.time()
		self.source=source
		self.key=key
		self.kind=kind
		self.name=name
		self.state=state
		self.title=title or name
		self.detail=detail
		self.since=now if since is None else since
		self.checked=now if checked is None else checked
		self.replace=replace

	def to_dict(self)->dict:
		return {"source":self.source,"key":self.key,"kind":self.kind,"name":self.name,"state":self.state,"title":self.title,"detail":self.detail,"since":self.since,"checked":self.checked,"replace":self.replace}

	@classmethod
	def from_dict(cls,data:dict)->"Condition":
		return cls(data["source"],data["key"],data["kind"],data["name"],data["state"],data.get("title",""),data.get("detail",""),data.get("since"),data.get("checked"),data.get("replace",False))

def record(condition:Condition)->dict:
	"""The news record for one condition, without deciding whether it is a change."""
	recovered=condition.state==STATE_OK
	title=f"{condition.name} recovered" if recovered else condition.title
	return {"id":f"{condition.key}@{int(condition.checked*1000)}","source":condition.source,"key":condition.key,"state":condition.state,"title":title,"detail":condition.detail,"at":condition.checked,"recovered":recovered}

def transition(old:Condition|None,new:Condition)->dict|None:
	"""Return the news record for a change, or None when the state held."""
	if old is not None and old.state==new.state:
		return None
	if old is None and new.state==STATE_OK:
		return None
	return record(new)
