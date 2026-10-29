"""Check whether a watched package has a fixed candidate version."""

import subprocess
from .. import event

class Apt:
	"""One package-version source: each watched package checked on one interval."""

	def __init__(self,id:str,options:dict):
		self.id=id
		self.packages=[_package(entry) for entry in _packages(options.get("packages"))]
		self.interval_seconds=float(options.get("interval_seconds",3600.0))
		self.timeout_seconds=float(options.get("timeout_seconds",30.0))
		self.stale_seconds=float(options.get("stale_after_seconds",max(self.interval_seconds*3,180.0)))

	def interval(self)->float:
		return self.interval_seconds

	def stale_after(self)->float:
		return self.stale_seconds

	def keys(self)->list[tuple[str,str]]:
		"""A package's state is news, not a health row."""
		return []

	def check(self,now:float,policy=None,compare=None)->list[event.Condition]:
		"""Check every watched package against its fixed version."""
		policy=_policy(self.timeout_seconds) if policy is None else policy
		compare=version_at_least if compare is None else compare
		return [_check_one(self.id,package,now,policy,compare) for package in self.packages]

def _policy(timeout:float,run=None):
	run=subprocess.run if run is None else run
	def policy(name:str)->str|None:
		result=run(["apt-cache","policy",name],capture_output=True,text=True,timeout=timeout)
		if result.returncode!=0:
			raise ValueError(f"apt-cache policy {name} exited {result.returncode}: {result.stderr.strip()}")
		return _candidate(result.stdout)
	return policy

def version_at_least(candidate:str,fixed:str,run=None)->bool:
	"""Whether a Debian version is at or above another, by dpkg's own ordering."""
	run=subprocess.run if run is None else run
	result=run(["dpkg","--compare-versions",candidate,"ge",fixed],capture_output=True,text=True)
	if result.returncode==0:
		return True
	if result.returncode==1:
		return False
	raise ValueError(f"dpkg --compare-versions {candidate} ge {fixed} exited {result.returncode}: {result.stderr.strip()}")

def _candidate(output:str)->str|None:
	for line in output.splitlines():
		if not line.strip().startswith("Candidate:"):
			continue
		value=line.split(":",1)[1].strip()
		return None if value in ("","(none)") else value
	return None

def _packages(value:object)->list:
	if value is None:
		return []
	if not isinstance(value,list):
		raise ValueError("packages must be a list")
	return value

def _package(entry:object)->dict:
	if not isinstance(entry,dict):
		raise ValueError("a package must be an object")
	name=entry.get("name")
	fixed=entry.get("fixed")
	if not isinstance(name,str) or not name:
		raise ValueError("a package needs a name")
	if not isinstance(fixed,str) or not fixed:
		raise ValueError(f"package {name} needs a fixed version")
	return {"name":name,"fixed":fixed}

def _check_one(source_id:str,package:dict,now:float,policy,compare)->event.Condition:
	name=package["name"]
	candidate=policy(name)
	if not candidate:
		raise ValueError(f"{name} has no candidate version")
	fixed=package["fixed"]
	key=f"{source_id}:{name}"
	detail=f"candidate {candidate} (fix at {fixed})"
	if compare(candidate,fixed):
		return event.Condition(source_id,key,"news",name,event.STATE_INFO,f"{name} can be fixed by apt upgrade",detail,checked=now)
	return event.Condition(source_id,key,"news",name,event.STATE_OK,f"{name} is not fixed yet",detail,checked=now)
