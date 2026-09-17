#!/usr/bin/env python3
"""Session tracker for schema cache (XLib)."""
import json,sys
from pathlib import Path

CACHE_DIR = Path(__file__).parent / ".schema_cache"
SESSION_FILE = CACHE_DIR / "session_state.json"

def load_state():
	if SESSION_FILE.exists():
		with open(SESSION_FILE) as f:
			return json.load(f)
	return {"turn": 0, "compact_after": False, "last_ids": [], "subagent_parent_ids": None}

def save_state(s):
	SESSION_FILE.write_text(json.dumps(s, indent=2) + "\n")

def is_first_turn():
	return load_state().get("turn", 0) == 0

def mark_turn():
	s = load_state(); s["turn"] = s.get("turn", 0) + 1; save_state(s)

def mark_compact():
	s = load_state(); s["compact_after"] = True; save_state(s)

def clear_compact():
	s = load_state(); s["compact_after"] = False; save_state(s)

def set_subagent_ids(ids):
	s = load_state(); s["subagent_parent_ids"] = ids; save_state(s)

def get_subagent_ids():
	return load_state().get("subagent_parent_ids")

if __name__ == "__main__":
	cmd = sys.argv[1] if len(sys.argv) > 1 else ""
	if cmd == "first-turn": print("TURN=1" if is_first_turn() else "TURN>1")
	elif cmd == "subsequent-turn": print("TURN>1" if not is_first_turn() else "TURN=1")
	elif cmd in ("turn", "next-turn"): mark_turn(); print("TURN_MARKED")
	elif cmd == "compact": mark_compact(); print("COMPACT=SET")
	elif cmd == "clear-compact": clear_compact(); print("COMPACT=CLEAR")
	elif cmd == "subagent-init":
		import subprocess
		ids_raw = subprocess.check_output([sys.executable, str(Path(__file__).parent / "tool_schema_cache.py"), "subsequent-turn"], text=True)
		set_subagent_ids(json.loads(ids_raw).get("tool_ids", []))
		print("SUBAGENT_INIT_OK")
	elif cmd == "state": print(json.dumps(load_state()))
	else: print("Usage: session_tracker.py <first-turn|subsequent-turn|turn|compact|clear-compact|subagent-init|state>")
