"""Watch the Traveller player files for new joins and returns."""

import json,os,time
from .. import event

class Players:
	"""One player feed: joins and returns after a configured absence."""

	def __init__(self,id:str,options:dict):
		self.id=id
		self.data_path=str(_required(options,"data_path"))
		self.absence_seconds=float(options.get("absence_days",14.0))*86400.0
		self.interval_seconds=float(options.get("interval_seconds",300.0))
		self.stale_seconds=float(options.get("stale_after_seconds",max(self.interval_seconds*3,180.0)))

	def interval(self)->float:
		return self.interval_seconds

	def stale_after(self)->float:
		return self.stale_seconds

	def keys(self)->list[tuple[str,str]]:
		"""A player is news, not a health row."""
		return []

	def check(self,now:float,memory:dict|None=None)->list[event.Condition]:
		"""Read the player records and diff the last-active times."""
		memory={} if memory is None else memory
		players=_read_players(self.data_path)
		if not memory.get("seeded"):
			memory["seeded"]=True
			memory["seen"]={name:record["last_active"] for name,record in players.items()}
			return []
		seen=memory.setdefault("seen",{})
		records=[]
		for name in sorted(players):
			record=players[name]
			last=record["last_active"]
			if name not in seen:
				records.append(_record(self.id,name,"new",now,record))
			else:
				away=last-seen[name]
				if away>self.absence_seconds:
					records.append(_record(self.id,name,"return",now,record,away=away))
				if last>seen[name]:
					seen[name]=last
			seen.setdefault(name,last)
		return records

def _required(options:dict,key:str)->str:
	value=options.get(key)
	if not isinstance(value,str) or not value:
		raise ValueError(f"players needs a {key}")
	return os.path.expanduser(value)

def _read_players(data_path:str)->dict:
	"""Every player the game lists, with their created and last-active times."""
	with open(os.path.join(data_path,"users.json"),encoding="utf-8") as file:
		names=json.load(file)
	if not isinstance(names,list):
		raise ValueError("users.json must be a list of names")
	players={}
	for name in names:
		record=_read_player(os.path.join(data_path,"users",f"{name}.json"))
		if record is not None:
			players[str(name)]=record
	return players

def _read_player(path:str)->dict|None:
	try:
		with open(path,encoding="utf-8") as file:
			data=json.load(file)
	except (OSError,ValueError):
		return None
	props=data.get("props") or {}
	created=_number(props.get("created"))
	last_active=_number(props.get("last_active"))
	if created is None or last_active is None:
		return None
	return {"created":created,"last_active":last_active}

def _number(value:object)->float|None:
	if isinstance(value,bool) or not isinstance(value,(int,float)):
		return None
	return float(value)

def _record(source_id:str,name:str,kind:str,now:float,record:dict,away:float=0.0)->event.Condition:
	key=f"{source_id}:{kind}:{name}"
	if kind=="new":
		title=f"new player: {name}"
		detail=f"joined {_date(record['created'])}"
	else:
		days=max(1,int(away//86400))
		title=f"{name} returned after {days} day{'s' if days!=1 else ''}"
		detail=f"last active {_date(record['last_active'])}, away {days} days"
	return event.Condition(source_id,key,"news",name,event.STATE_INFO,title,detail,checked=now)

def _date(epoch:float)->str:
	return time.strftime("%Y-%m-%d",time.localtime(epoch))
