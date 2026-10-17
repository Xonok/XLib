"""Connection to the OpenCode background service.

v2 dropped the per-process `--port 0` server: one shared service owns every
session, and it requires HTTP Basic auth. Both facts replace what the old
port-file protocol used to carry.
"""

import base64,json,subprocess,urllib.error,urllib.request
from pathlib import Path

SERVICE_CONFIG=Path.home()/".config"/"opencode"/"service.json"
SERVICE_USER="opencode"

def resolve_url(timeout:int=15) -> str:
	"""Base URL of the running service, or "" when it cannot be asked."""
	try:
		done=subprocess.run(["opencode","service","status"],capture_output=True,text=True,timeout=timeout)
	except (OSError,subprocess.SubprocessError):
		return ""
	for line in done.stdout.splitlines():
		line=line.strip()
		if line.startswith("http://"):
			return line.rstrip("/")
	return ""

def password() -> str:
	"""Local service password, or "" when the config is missing or unreadable."""
	try:
		return json.loads(SERVICE_CONFIG.read_text()).get("password","")
	except (OSError,json.JSONDecodeError,AttributeError):
		return ""

def auth_headers(pw:str) -> dict:
	"""Headers carrying Basic auth for the local service."""
	token=base64.b64encode(f"{SERVICE_USER}:{pw}".encode()).decode()
	return {"Authorization":f"Basic {token}"}

def get_json(url:str,pw:str,timeout:float=10.0):
	"""GET and decode JSON, or None when the call fails in any way."""
	req=urllib.request.Request(url,headers={**auth_headers(pw),"Accept":"application/json"})
	try:
		with urllib.request.urlopen(req,timeout=timeout) as response:
			return json.loads(response.read())
	except (urllib.error.URLError,OSError,json.JSONDecodeError,ValueError):
		return None

def _as_list(payload) -> list:
	"""Normalise a list-or-envelope response body to a list."""
	if isinstance(payload,list):
		return payload
	if isinstance(payload,dict) and isinstance(payload.get("data"),list):
		return payload["data"]
	return []

def all_sessions(base_url:str,pw:str):
	"""Every session the service knows, or None when it could not be asked."""
	payload=get_json(f"{base_url}/api/session",pw)
	if payload is None:
		return None
	return _as_list(payload)

def active_session_ids(base_url:str,pw:str):
	"""Ids of sessions running right now, or None when the service could not be asked.

	None is deliberately not the same as an empty set: a failed query must not
	read as "nothing is running", which would retire every agent on a momentary
	blip and reset their ages.
	"""
	payload=get_json(f"{base_url}/api/session/active",pw)
	if payload is None:
		return None
	if isinstance(payload,dict) and isinstance(payload.get("data"),dict):
		payload=payload["data"]
	if not isinstance(payload,dict):
		return None
	return set(payload.keys())

def session_workspace(session:dict) -> str:
	"""Working directory of a session, or "" when the service does not say."""
	location=session.get("location")
	if isinstance(location,dict):
		return location.get("directory","")
	if isinstance(location,str):
		return location
	return ""
