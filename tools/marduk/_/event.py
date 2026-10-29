"""The condition record and the transitions it produces."""

import time

STATE_OK="ok"
STATE_WARN="warn"
STATE_ALERT="alert"
STATE_INFO="info"

class Condition:
	"""The current state of one check, keyed by its source and key."""

	__slots__=("source","key","kind","name","state","title","detail","since","checked")

	def __init__(self,source:str,key:str,kind:str,name:str,state:str,title:str="",detail:str="",since:float|None=None,checked:float|None=None):
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

	def to_dict(self)->dict:
		return {"source":self.source,"key":self.key,"kind":self.kind,"name":self.name,"state":self.state,"title":self.title,"detail":self.detail,"since":self.since,"checked":self.checked}

	@classmethod
	def from_dict(cls,data:dict)->"Condition":
		return cls(data["source"],data["key"],data["kind"],data["name"],data["state"],data.get("title",""),data.get("detail",""),data.get("since"),data.get("checked"))

def transition(old:Condition|None,new:Condition)->dict|None:
	"""Return the news record for a change, or None when the state held."""
	if old is not None and old.state==new.state:
		return None
	if old is None and new.state==STATE_OK:
		return None
	recovered=new.state==STATE_OK
	title=f"{new.name} recovered" if recovered else new.title
	return {"id":f"{new.key}@{int(new.checked*1000)}","source":new.source,"key":new.key,"state":new.state,"title":title,"detail":new.detail,"at":new.checked,"recovered":recovered}
