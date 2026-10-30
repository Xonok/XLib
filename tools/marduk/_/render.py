"""Draw the panel into the pane it is given."""

import re,time
from collections import Counter
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

def _wrap(text:str,width:int)->list[str]:
	"""Split text into lines that fit the pane width."""
	lines=[]
	current=""
	for word in text.split():
		if current and visible_len(current+" "+word)>width:
			lines.append(fit(current,width))
			current=word
		else:
			current=(current+" "+word).strip()
	if current:
		lines.append(fit(current,width))
	return lines or [fit(text,width)]

_DEFAULT_SECTIONS=[("health","HEALTH"),("free","FREE MODELS"),("news","NEWS")]

def _normalize_sections(sections):
	if sections is None:
		return list(_DEFAULT_SECTIONS)
	out=[]
	for entry in sections:
		if isinstance(entry,str):
			out.append((entry,entry.upper()))
		elif isinstance(entry,dict):
			out.append((entry.get("kind",entry.get("name","")),entry.get("title",entry.get("name",""))))
		else:
			out.append((entry[0],entry[1]))
	return out

def render(sources,snapshot:dict,now:float,height:int,width:int,compact:bool=False,notices:list[str]|None=None,sections=None)->list[str]:
	"""Return the frame's lines, capped to the pane it is given."""
	compact=compact or width<46
	head=["=== Marduk ==="]
	for notice in notices or []:
		head.append(fit(f"! {notice}",width))
	head.append(fit(_feeds_line(sources,snapshot,now,width),width))
	for source in sources:
		record=snapshot["sources"].get(source.id)
		if record and record.get("last_error"):
			for line in _wrap(f"! {source.id}: {record['last_error']}",width):
				head.append(line)
	conditions={condition.key:condition for condition in snapshot["conditions"]}
	normalized=_normalize_sections(sections)
	blocks=[]
	for kind,title in normalized:
		if kind=="news":
			items=_news_item_lines(snapshot,width)
			if not items:
				items=[fit("  nothing yet",width)]
			blocks.append((title,kind,items,["",title]))
		else:
			rows=_rows_for_kind(sources,conditions,kind)
			if not rows and kind!="health":
				continue
			row_lines=[]
			if rows:
				if compact:
					row_lines.append(fit(f" {'name':12} {'state':5} {'for':>5}",width))
				else:
					row_lines.append(fit(f"  {'name':22} {'state':6} {'for':>7}",width))
				counts=Counter(name for _,_,name in rows)
				for source,key,name in rows:
					display=f"{source.id}/{name}" if source is not None and counts[name]>1 else name
					condition=conditions.get(key)
					if condition is None:
						state_text="?"
						age="--"
						detail="waiting for the first check"
					else:
						age=format_age(now-condition.since)
						state_text=condition.state
						detail=condition.detail
						if source is None:
							state_text="?"
							detail=f"source {condition.source} is not configured"
						elif store.source_state(snapshot["sources"].get(source.id),now,source.stale_after())!="ok":
							state_text="?"
							detail=f"last {condition.state}: {condition.detail}" if condition.detail else f"last {condition.state}"
					row_lines.append(_health_line(display,state_text,age,detail,width,compact))
			else:
				row_lines.append(fit("  no checks configured",width))
			blocks.append((title,kind,row_lines,["",title]))
	header_lines=list(head)
	block_headers=[b[3] for b in blocks]
	block_items=[b[2] for b in blocks]
	def assemble():
		out=list(header_lines)
		for h,items in zip(block_headers,block_items):
			out=out+list(h)+list(items)
		return out
	lines=assemble()
	if len(lines)<=height:
		return lines
	for i in range(len(block_items)-1,-1,-1):
		while len(assemble())>height and len(block_items[i])>1:
			overflow=len(assemble())-height
			items=block_items[i]
			keep=max(1,len(items)-overflow)
			if keep>=len(items):
				keep=len(items)-1
			block_items[i]=_trim(items,keep)
			if len(assemble())<=height:
				break
		if len(assemble())<=height:
			break
	lines=assemble()
	if len(lines)<=height:
		return lines
	return lines[:max(height,0)]

def _trim(items:list[str],keep:int)->list[str]:
	if keep<=0:
		return []
	if keep>=len(items):
		return items
	return items[:keep-1]+[f"… +{len(items)-keep+1} more"]

def _feeds_line(sources,snapshot:dict,now:float,width:int)->str:
	parts=[]
	for source in sources:
		record=snapshot["sources"].get(source.id)
		state=store.source_state(record,now,source.stale_after())
		if state=="error":
			continue
		age=format_age(store.source_age(record,now)) if record else "--"
		text=f"{source.id} {color_state(state)} {age}"
		parts.append(text)
	if not parts:
		parts=["(none)"]
	return "feeds: "+", ".join(parts)

def _rows_for_kind(sources,snapshot_conditions:dict,kind:str):
	rows=[]
	seen=set()
	if kind=="health":
		for source in sources:
			for key,name in source.keys():
				if key in seen:
					continue
				rows.append((source,key,name))
				seen.add(key)
	for key,condition in snapshot_conditions.items():
		if condition.kind!=kind or key in seen:
			continue
		source=next((item for item in sources if item.id==condition.source),None)
		rows.append((source,key,condition.name))
		seen.add(key)
	return rows

def _news_item_lines(snapshot:dict,width:int)->list[str]:
	lines=[]
	for item in snapshot["news"]:
		stamp=time.strftime("%m-%d %H:%M",time.localtime(item.get("at",0)))
		text=f"  {stamp}  {item.get('title','')}"
		if item.get("detail"):
			text+=f" — {item['detail']}"
		lines.append(fit(text,width))
	return lines

def _health_line(name:str,state:str,age:str,detail:str,width:int,compact:bool)->str:
	if compact:
		return fit(f" {name[:12]:12} {pad(color_state(state),5)} {age:>5}",width)
	return fit(f"  {name[:22]:22} {pad(color_state(state),6)} {age:>7}  {detail}",width)
