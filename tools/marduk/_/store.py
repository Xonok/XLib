"""The on-disk state: conditions, transitions and source health."""

import contextlib,copy,json,os,tempfile,threading,fcntl
from . import event

STATE_VERSION=1

class Store:
	"""The panel's memory, loaded from one JSON file and written atomically."""

	def __init__(self,path:str):
		self.path=os.path.expanduser(path)
		self.conditions={}
		self.news=[]
		self.sources={}
		self.retention_seconds=7*24*3600
		self.load_error=""
		self._lock=threading.Lock()
		self._file_lock_path=self.path+".lock"
		self._mtime=0.0
		self.load()

	def _external_lock(self):
		"""Cross-process lock (flock) so manual editors and other daemons don't race."""
		os.makedirs(os.path.dirname(self.path) or ".",exist_ok=True)
		fd=os.open(self._file_lock_path,os.O_RDWR|os.O_CREAT,0o644)
		@contextlib.contextmanager
		def _ctx():
			try:
				fcntl.flock(fd,fcntl.LOCK_EX)
				yield
			finally:
				fcntl.flock(fd,fcntl.LOCK_UN)
				os.close(fd)
		return _ctx()

	def _disk_mtime(self)->float:
		try:
			return os.path.getmtime(self.path)
		except OSError:
			return 0.0

	def _load_unlocked(self)->None:
		try:
			with open(self.path,encoding="utf-8") as file:
				data=json.load(file)
		except FileNotFoundError:
			self.conditions={}
			self.news=[]
			self.sources={}
			self.load_error=""
			self._mtime=self._disk_mtime()
			return
		except (OSError,ValueError) as exc:
			self.load_error=f"{type(exc).__name__}: {exc}"
			return
		if not isinstance(data,dict) or data.get("version")!=STATE_VERSION:
			self.load_error=f"unsupported state in {self.path}"
			return
		try:
			self.conditions={key:event.Condition.from_dict(value) for key,value in data.get("conditions",{}).items()}
		except (AttributeError,KeyError,TypeError,ValueError) as exc:
			self.load_error=f"malformed condition in {self.path}: {exc}"
			return
		self.news=list(data.get("news",[]))
		self.sources=dict(data.get("sources",{}))
		self.load_error=""
		self._mtime=self._disk_mtime()

	def load(self)->None:
		with self._external_lock():
			with self._lock:
				self._load_unlocked()

	def _reload_if_changed_unlocked(self)->None:
		mtime=self._disk_mtime()
		if mtime and mtime!=self._mtime:
			self._load_unlocked()

	def _save_unlocked(self)->None:
		with self._lock:
			data={"version":STATE_VERSION,"conditions":{key:value.to_dict() for key,value in self.conditions.items()},"news":self.news,"sources":self.sources}
		directory=os.path.dirname(self.path)
		if directory:
			os.makedirs(directory,exist_ok=True)
		fd,tmp=tempfile.mkstemp(dir=directory or ".",prefix=".state-",suffix=".json")
		try:
			with os.fdopen(fd,"w",encoding="utf-8") as file:
				json.dump(data,file,indent=1,sort_keys=True)
				file.write("\n")
			os.replace(tmp,self.path)
		except BaseException:
			try:
				os.unlink(tmp)
			except OSError:
				pass
			raise
		self._mtime=self._disk_mtime()

	def save(self)->None:
		with self._external_lock():
			self._save_unlocked()

	def apply(self,source_name:str,conditions:list[event.Condition],now:float,memory:dict|None=None)->None:
		"""Fold one complete check into the store and keep the transitions."""
		with self._external_lock():
			self._reload_if_changed_unlocked()
			with self._lock:
				seen=set()
				for condition in conditions:
					seen.add(condition.key)
					old=self.conditions.get(condition.key)
					condition.since=old.since if old is not None and old.state==condition.state else now
					record=event.transition(old,condition)
					if condition.replace:
						self.news=[item for item in self.news if item.get("source")!=source_name]
						if condition.state!=event.STATE_OK:
							self.news.append(event.record(condition))
					elif record is not None:
						self.news.append(record)
					self.conditions[condition.key]=condition
				for key in list(self.conditions):
					if self.conditions[key].source==source_name and key not in seen:
						del self.conditions[key]
				cutoff=now-self.retention_seconds
				self.news=[item for item in self.news if item.get("at",0)>=cutoff]
				self.news.sort(key=lambda item:item.get("at",0),reverse=True)
				self._mark_source(source_name,now,None)
				if memory is not None:
					self.sources[source_name]["memory"]=memory
			self._save_unlocked()

	def memory(self,source_name:str)->dict:
		"""The source's own memory, copied so a failed run changes nothing."""
		with self._external_lock():
			self._reload_if_changed_unlocked()
			with self._lock:
				record=self.sources.get(source_name) or {}
				return copy.deepcopy(record.get("memory") or {})

	def fail(self,source_name:str,now:float,error:str)->None:
		"""Record a failed run; the last conditions stay where they are."""
		with self._external_lock():
			self._reload_if_changed_unlocked()
			with self._lock:
				self._mark_source(source_name,now,error)
			self._save_unlocked()

	def _mark_source(self,source_name:str,now:float,error:str|None)->None:
		record=self.sources.setdefault(source_name,{})
		record["last_run"]=now
		if error:
			record["last_error"]=error
		else:
			record["last_ok"]=now
			record["last_error"]=""

	def snapshot(self,now:float)->dict:
		with self._external_lock():
			self._reload_if_changed_unlocked()
			with self._lock:
				return {"conditions":list(self.conditions.values()),"news":list(self.news),"sources":{name:dict(record) for name,record in self.sources.items()}}

def source_state(record:dict|None,now:float,stale_after:float)->str:
	"""The source's health: waiting, error, stale or ok."""
	if not record or "last_run" not in record:
		return "waiting"
	if record.get("last_error"):
		return "error"
	if now-record.get("last_ok",0)>stale_after:
		return "stale"
	return "ok"

def source_age(record:dict|None,now:float)->float:
	"""Seconds since the last successful check, or since the last run."""
	if not record:
		return 0.0
	return now-record.get("last_ok",record.get("last_run",now))
