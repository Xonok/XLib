"""Load the panel configuration."""

import json
from pathlib import Path

DEFAULT_CONFIG_PATH="~/.config/marduk/config.json"
DEFAULT_STATE_PATH="~/.local/share/marduk/state.json"
_GLOBAL_KEYS={"sources","news_retention_days","state_path"}

class Config:
	"""The panel's settings, loaded from one JSON file."""

	def __init__(self,path:Path|str|None=None):
		self.path=Path(path).expanduser() if path else Path(DEFAULT_CONFIG_PATH).expanduser()
		self.sources=[]
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
		unknown=sorted(set(data)-_GLOBAL_KEYS)
		if unknown:
			raise ValueError(f"unknown config key: {', '.join(unknown)}")
		self.sources=[_source(entry) for entry in _as_list(data.get("sources",[]),"sources")]
		names=[entry["id"] for entry in self.sources]
		if len(set(names))!=len(names):
			raise ValueError("source ids must be unique")
		self.news_retention_days=float(data.get("news_retention_days",self.news_retention_days))
		if "state_path" in data:
			self.state_path=Path(data["state_path"]).expanduser()

def _as_list(value:object,name:str)->list:
	if not isinstance(value,list):
		raise ValueError(f"{name} must be a list")
	return value

def _source(entry:object)->dict:
	"""Normalise one source entry: a kind, an id and that kind's own options."""
	if not isinstance(entry,dict):
		raise ValueError("a source must be an object")
	kind=entry.get("kind")
	if not isinstance(kind,str) or not kind:
		raise ValueError("a source needs a kind")
	name=entry.get("id",kind)
	if not isinstance(name,str) or not name:
		raise ValueError(f"source {kind}: id must be a non-empty string")
	return {**entry,"kind":kind,"id":name}
