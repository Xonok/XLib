"""Load the panel configuration."""

import json
from pathlib import Path

DEFAULT_CONFIG_PATH="~/.config/marduk/config.json"
DEFAULT_STATE_PATH="~/.local/share/marduk/state.json"

class Config:
	"""The panel's settings, loaded from one JSON file."""

	def __init__(self,path:Path|str|None=None):
		self.path=Path(path).expanduser() if path else Path(DEFAULT_CONFIG_PATH).expanduser()
		self.sites=[]
		self.site_interval=60.0
		self.site_timeout=10.0
		self.news_retention_days=7.0
		self.state_path=Path(DEFAULT_STATE_PATH).expanduser()
		self.error=""
		self.load()

	def load(self)->None:
		try:
			with open(self.path,encoding="utf-8") as file:
				data=json.load(file)
		except FileNotFoundError:
			self.error=f"no config at {self.path}"
			return
		except (OSError,ValueError) as exc:
			self.error=f"{type(exc).__name__}: {exc}"
			return
		try:
			self._read(data)
		except (TypeError,ValueError) as exc:
			self.error=f"{self.path}: {exc}"

	def _read(self,data:object)->None:
		if not isinstance(data,dict):
			raise ValueError("the config must be an object")
		sites=data.get("sites",[])
		if not isinstance(sites,list):
			raise ValueError("sites must be a list")
		self.sites=[_site(entry) for entry in sites]
		self.site_interval=float(data.get("site_interval_seconds",self.site_interval))
		self.site_timeout=float(data.get("site_timeout_seconds",self.site_timeout))
		self.news_retention_days=float(data.get("news_retention_days",self.news_retention_days))
		if "state_path" in data:
			self.state_path=Path(data["state_path"]).expanduser()

def _site(entry:object)->dict:
	"""Turn one site entry into a name and a URL."""
	if isinstance(entry,str):
		return {"name":entry,"url":f"https://{entry}/"}
	if isinstance(entry,dict):
		name=entry.get("name") or entry.get("url")
		if not name:
			raise ValueError("a site needs a name or a URL")
		return {"name":str(name),"url":str(entry.get("url") or f"https://{name}/")}
	raise ValueError("a site must be a string or an object")
