"""Draw the panel into the pane it is given."""

import re,time
from . import store

_ANSI=re.compile(r"\033\[[0-9;]*m")
_COLOR={"ok":"\033[32m","warn":"\033[33m","alert":"\033[31m","info":"\033[36m","?":"\033[2m","waiting":"\033[2m","stale":"\033[33m","error":"\033[31m"}

def visible_len(text:str)->int:
	"""Return the length of a string without its ANSI escape codes."""
	return len(_ANSI.sub("",text))

def fit(text:str,width:int)->str:
	"""Cut a line to the pane width, counting visible characters only."""
	if visible_len(text)<=width:
		return text
	out=[]
	visible=0
	index=0
	while index<len(text) and visible<max(width-1,0):
		match=_ANSI.match(text,index)
		if match:
			out.append(match.group(0))
			index=match.end()
			continue
		out.append(text[index])
		visible+=1
		index+=1
	return "".join(out)+"…\033[0m"

def pad(text:str,width:int)->str:
	"""Pad to a visible width, so a coloured value keeps its column."""
	missing=width-visible_len(text)
	return text+" "*missing if missing>0 else text

def color_state(state:str)->str:
	return f"{_COLOR.get(state,'')}{state}\033[0m"

def format_age(seconds:float)->str:
	seconds=max(0,seconds)
	if seconds<60:
		return f"{int(seconds)}s"
	if seconds<3600:
		return f"{int(seconds/60)}m"
	if seconds<86400:
		return f"{int(seconds/3600)}h{int(seconds%3600/60):02d}m"
	return f"{int(seconds/86400)}d"

def render(config,sources,snapshot:dict,now:float,height:int,width:int,compact:bool=False,notices:list[str]|None=None)->list[str]:
	"""Return the frame's lines, capped to the pane it is given."""
	compact=compact or width<46
	head=["=== Marduk ==="]
	for notice in notices or []:
		head.append(fit(f"! {notice}",width))
	head.append(fit(_feeds_line(config,sources,snapshot,now,width),width))
	health=["","HEALTH"]+_health_lines(config,sources,snapshot,now,width,compact)
	news=["","NEWS"]+_news_lines(snapshot,width)
	lines=head+health+news
	if len(lines)<=height:
		return lines
	items=news[2:]
	keep=max(0,len(items)-(len(lines)-height))
	news=["","NEWS"]+_trim(items,keep) if keep>0 else []
	lines=head+health+news
	if len(lines)<=height:
		return lines
	items=health[2:]
	keep=max(0,len(items)-(len(lines)-height))
	health=["","HEALTH"]+_trim(items,keep)
	lines=head+health+news
	if len(lines)<=height:
		return lines
	return lines[:max(height,0)]

def _trim(items:list[str],keep:int)->list[str]:
	if keep<=0:
		return []
	if keep>=len(items):
		return items
	return items[:keep-1]+[f"… +{len(items)-keep+1} more"]

def _feeds_line(config,sources,snapshot:dict,now:float,width:int)->str:
	parts=[]
	for source in sources:
		record=snapshot["sources"].get(source.NAME)
		state=store.source_state(record,now,source.stale_after(config))
		age=format_age(store.source_age(record,now)) if record else "--"
		text=f"{source.NAME} {color_state(state)} {age}"
		if record and record.get("last_error"):
			text+=f" ({record['last_error']})"
		parts.append(text)
	if not parts:
		return "feeds: (none)"
	return "feeds: "+", ".join(parts)

def _health_lines(config,sources,snapshot:dict,now:float,width:int,compact:bool)->list[str]:
	by_key={condition.key:condition for condition in snapshot["conditions"]}
	source_by_name={source.NAME:source for source in sources}
	site=source_by_name.get("site")
	stale=site.stale_after(config) if site else 180.0
	record=snapshot["sources"].get("site")
	state=store.source_state(record,now,stale)
	lines=[]
	if compact:
		lines.append(fit(f" {'site':12} {'state':5} {'for':>5}",width))
	else:
		lines.append(fit(f"  {'site':22} {'state':6} {'for':>7}",width))
	for site_config in config.sites:
		name=site_config["name"]
		condition=by_key.get(f"site:{name}")
		if condition is None:
			state_text="?"
			age="--"
			detail="waiting for the first check"
		else:
			age=format_age(now-condition.since)
			state_text=condition.state
			detail=condition.detail
			if state!="ok":
				state_text="?"
				detail=f"last {condition.state}: {condition.detail}" if condition.detail else f"last {condition.state}"
		lines.append(_health_line(name,state_text,age,detail,width,compact))
	if not config.sites:
		lines.append(fit("  no checks configured",width))
	return lines

def _health_line(name:str,state:str,age:str,detail:str,width:int,compact:bool)->str:
	if compact:
		return fit(f" {name[:12]:12} {pad(color_state(state),5)} {age:>5}",width)
	return fit(f"  {name[:22]:22} {pad(color_state(state),6)} {age:>7}  {detail}",width)

def _news_lines(snapshot:dict,width:int)->list[str]:
	lines=[]
	for item in snapshot["news"]:
		stamp=time.strftime("%m-%d %H:%M",time.localtime(item.get("at",0)))
		text=f"  {stamp}  {item.get('title','')}"
		if item.get("detail"):
			text+=f" — {item['detail']}"
		lines.append(fit(text,width))
	return lines or [fit("  nothing yet",width)]
