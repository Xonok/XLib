"""Check the configured sites over HTTPS."""

import time,urllib.error,urllib.request
from .. import event
from ..config import Config

NAME="site"

OPENER=urllib.request.urlopen

def interval(config:Config)->float:
	return config.site_interval

def stale_after(config:Config)->float:
	return max(config.site_interval*3,180.0)

def check(config:Config,now:float|None=None,opener=None)->list[event.Condition]:
	"""Check every configured site; any HTTP answer means the server is up."""
	now=time.time() if now is None else now
	opener=OPENER if opener is None else opener
	return [_check_one(site,config.site_timeout,now,opener) for site in config.sites]

def _check_one(site:dict,timeout:float,now:float,opener)->event.Condition:
	name=site["name"]
	key=f"site:{name}"
	start=time.monotonic()
	try:
		with opener(site["url"],timeout=timeout) as response:
			code=getattr(response,"status",200) or 200
	except urllib.error.HTTPError as exc:
		code=exc.code
	except (urllib.error.URLError,OSError,ValueError) as exc:
		elapsed=time.monotonic()-start
		reason=getattr(exc,"reason",exc)
		return event.Condition(NAME,key,"health",name,event.STATE_ALERT,f"{name} is down",f"{reason} ({elapsed:.1f}s)",checked=now)
	elapsed=time.monotonic()-start
	if code>=500:
		state,title=event.STATE_ALERT,f"{name} is down"
	elif code>=400:
		state,title=event.STATE_WARN,f"{name} is degraded"
	else:
		state,title=event.STATE_OK,f"{name} is up"
	return event.Condition(NAME,key,"health",name,state,title,f"HTTP {code} ({elapsed:.1f}s)",checked=now)
