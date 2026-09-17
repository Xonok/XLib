#!/usr/bin/env python3
"""Prompt builder — integrates schema cache safely (XLib)."""
import argparse,json,subprocess,sys
from pathlib import Path
SCRIPT_DIR = Path(__file__).parent

def run_cache(cmd):
	script = SCRIPT_DIR / "tool_schema_cache.py"
	return subprocess.run([sys.executable, str(script), cmd], capture_output=True, text=True).stdout

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--system", default="")
	parser.add_argument("--history", default="")
	parser.add_argument("--message", default="")
	parser.add_argument("--output", default="")
	args = parser.parse_args()
	tracker = SCRIPT_DIR / "session_tracker.py"
	state_before = json.loads(subprocess.run([sys.executable, str(tracker), "state"], capture_output=True, text=True).stdout or "{}")
	is_first = state_before.get("turn", 0) == 0
	after_compact = state_before.get("compact_after", False)
	if after_compact:
		tools_block = run_cache("first-turn")
		subprocess.run([sys.executable, str(tracker), "clear-compact"], capture_output=True)
	elif is_first:
		tools_block = run_cache("first-turn")
	else:
		tools_block = run_cache("subsequent-turn")
	subprocess.run([sys.executable, str(tracker), "turn"], capture_output=True)
	updated = json.loads(subprocess.run([sys.executable, str(tracker), "state"], capture_output=True, text=True).stdout or "{}")
	subagent_ids = updated.get("subagent_parent_ids")
	subagent_note = f"# Inherited parent tool IDs (subagent): {subagent_ids}\n" if subagent_ids else ""
	prompt = f"{args.system}\n{args.history}\n{subagent_note}{tools_block}\n{args.message}"
	if args.output:
		Path(args.output).write_text(prompt)
		print(f"Prompt written to {args.output}")
	else:
		print(prompt)
if __name__ == "__main__":
	main()
