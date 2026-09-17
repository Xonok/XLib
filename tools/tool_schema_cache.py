#!/usr/bin/env python3
"""
Tool Schema Caching — reduces per-turn token cost by sending full schemas once,
then referencing them by stable ID in subsequent turns.

Usage:
	python3 tool_schema_cache.py init                 # Generate schema definitions + IDs
	python3 tool_schema_cache.py first-turn           # Output full schemas (turn 1)
	python3 tool_schema_cache.py subsequent-turn      # Output IDs only (turn 2+)
	python3 tool_schema_cache.py id read              # Get stable ID for a tool
	python3 tool_schema_cache.py schema read          # Get full schema for a tool
	python3 tool_schema_cache.py verify               # Check if cached IDs match current schemas

This tool lives in /storage/GitHub/Fun/XLib/tools/tool_schema_cache.py
"""

import argparse,hashlib,json,os,sys
from pathlib import Path

TOOLS_DIR = Path(__file__).parent
SCHEMA_CACHE_DIR = TOOLS_DIR / ".schema_cache"
SCHEMA_CACHE_DIR.mkdir(exist_ok=True)

DEFINITIONS_FILE = SCHEMA_CACHE_DIR / "definitions.json"
IDS_FILE = SCHEMA_CACHE_DIR / "ids.json"

DEFAULT_TOOLS = [
	"read", "write", "edit", "grep", "glob", "bash",
	"task", "webfetch", "websearch", "todowrite", "skill"
]

TOOL_SCHEMAS = {
	"read": {
		"name": "read",
		"description": "Read a file from the filesystem",
		"parameters": {
			"type": "object",
			"properties": {
				"filePath": {"type": "string", "description": "Absolute path to the file"},
				"offset": {"type": "integer", "description": "Line number to start from (1-indexed)"},
				"limit": {"type": "integer", "description": "Maximum number of lines to read"}
			},
			"required": ["filePath"]
		}
	},
	"write": {
		"name": "write",
		"description": "Write a file to the filesystem",
		"parameters": {
			"type": "object",
			"properties": {
				"filePath": {"type": "string", "description": "Absolute path to the file"},
				"content": {"type": "string", "description": "Content to write"}
			},
			"required": ["filePath", "content"]
		}
	},
	"edit": {
		"name": "edit",
		"description": "Perform exact string replacement in a file",
		"parameters": {
			"type": "object",
			"properties": {
				"filePath": {"type": "string", "description": "Absolute path to the file"},
				"oldString": {"type": "string", "description": "Text to replace"},
				"newString": {"type": "string", "description": "Text to replace with"},
				"replaceAll": {"type": "boolean", "description": "Replace all occurrences", "default": False}
			},
			"required": ["filePath", "oldString", "newString"]
		}
	},
	"grep": {
		"name": "grep",
		"description": "Search file contents using regex",
		"parameters": {
			"type": "object",
			"properties": {
				"pattern": {"type": "string", "description": "Regex pattern to search for"},
				"path": {"type": "string", "description": "Directory to search in"},
				"include": {"type": "string", "description": "File pattern to include (e.g. *.py)"}
			},
			"required": ["pattern"]
		}
	},
	"glob": {
		"name": "glob",
		"description": "Find files by glob pattern",
		"parameters": {
			"type": "object",
			"properties": {
				"pattern": {"type": "string", "description": "Glob pattern (e.g. **/*.py)"},
				"path": {"type": "string", "description": "Directory to search in"}
			},
			"required": ["pattern"]
		}
	},
	"bash": {
		"name": "bash",
		"description": "Execute a bash command",
		"parameters": {
			"type": "object",
			"properties": {
				"command": {"type": "string", "description": "Command to execute"},
				"timeout": {"type": "integer", "description": "Timeout in milliseconds", "default": 120000},
				"workdir": {"type": "string", "description": "Working directory"}
			},
			"required": ["command"]
		}
	},
	"task": {
		"name": "task",
		"description": "Launch a subagent for complex multi-step tasks",
		"parameters": {
			"type": "object",
			"properties": {
				"description": {"type": "string", "description": "Short description of the task"},
				"prompt": {"type": "string", "description": "Detailed task prompt"},
				"subagent_type": {"type": "string", "description": "Type of subagent to use"},
				"task_id": {"type": "string", "description": "Optional task_id to resume a previous session"}
			},
			"required": ["description", "prompt", "subagent_type"]
		}
	},
	"webfetch": {
		"name": "webfetch",
		"description": "Fetch content from a URL",
		"parameters": {
			"type": "object",
			"properties": {
				"url": {"type": "string", "description": "URL to fetch"},
				"format": {"type": "string", "description": "Format: text, markdown, html", "enum": ["text", "markdown", "html"], "default": "markdown"},
				"timeout": {"type": "integer", "description": "Timeout in seconds", "default": 120}
			},
			"required": ["url"]
		}
	},
	"websearch": {
		"name": "websearch",
		"description": "Search the web",
		"parameters": {
			"type": "object",
			"properties": {
				"query": {"type": "string", "description": "Search query"},
				"numResults": {"type": "integer", "description": "Number of results", "default": 8},
				"livecrawl": {"type": "string", "description": "Live crawl mode", "enum": ["fallback", "preferred"], "default": "fallback"},
				"type": {"type": "string", "description": "Search type", "enum": ["auto", "fast", "deep"], "default": "auto"},
				"contextMaxCharacters": {"type": "integer", "description": "Max context chars", "default": 10000}
			},
			"required": ["query"]
		}
	},
	"todowrite": {
		"name": "todowrite",
		"description": "Create and maintain a structured task list",
		"parameters": {
			"type": "object",
			"properties": {
				"todos": {
					"type": "array",
					"items": {
						"type": "object",
						"properties": {
							"content": {"type": "string"},
							"status": {"type": "string", "enum": ["pending", "in_progress", "completed", "cancelled"]},
							"priority": {"type": "string", "enum": ["high", "medium", "low"]}
						},
						"required": ["content", "status", "priority"]
					}
				}
			},
			"required": ["todos"]
		}
	},
	"skill": {
		"name": "skill",
		"description": "Load a specialized skill",
		"parameters": {
			"type": "object",
			"properties": {
				"name": {"type": "string", "description": "Skill name from available_skills"}
			},
			"required": ["name"]
		}
	}
}

def schema_hash(schema):
	"""Stable hash of a schema for versioning."""
	return hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()[:12]

def generate_ids():
	"""Generate stable IDs for all tools."""
	ids = {}
	for name in DEFAULT_TOOLS:
		schema = TOOL_SCHEMAS[name]
		h = schema_hash(schema)
		ids[name] = f"{name}_v{h}"
	return ids

def load_definitions():
	if DEFINITIONS_FILE.exists():
		with open(DEFINITIONS_FILE) as f:
			return json.load(f)
	return {}

def save_definitions(defs):
	with open(DEFINITIONS_FILE, "w") as f:
		json.dump(defs, f, indent=2)
		f.write("\n")

def load_ids():
	if IDS_FILE.exists():
		with open(IDS_FILE) as f:
			return json.load(f)
	return {}

def save_ids(ids):
	with open(IDS_FILE, "w") as f:
		json.dump(ids, f, indent=2)
		f.write("\n")

def cmd_init(args):
	"""Initialize schema cache with current tool definitions."""
	ids = generate_ids()
	defs = {name: TOOL_SCHEMAS[name] for name in DEFAULT_TOOLS}
	save_ids(ids)
	save_definitions(defs)
	print("Initialized schema cache:")
	for name, id_ in ids.items():
		print(f"  {name} -> {id_}")
	print(f"\nDefinitions saved to {DEFINITIONS_FILE}")
	print(f"IDs saved to {IDS_FILE}")

def cmd_first_turn(args):
	"""Output full schemas for turn 1."""
	ids = load_ids() or generate_ids()
	defs = load_definitions() or {name: TOOL_SCHEMAS[name] for name in DEFAULT_TOOLS}
	
	output = {
		"tools": [],
		"schema_version": "1"
	}
	for name in DEFAULT_TOOLS:
		if name in defs:
			output["tools"].append({
				"id": ids.get(name, f"{name}_v0"),
				"schema": defs[name]
			})
	json.dump(output, sys.stdout, indent=2)
	print()

def cmd_subsequent_turn(args):
	"""Output only tool IDs for turn 2+."""
	ids = load_ids() or generate_ids()
	
	output = {
		"tool_ids": [ids.get(name, f"{name}_v0") for name in DEFAULT_TOOLS],
		"schema_version": "1"
	}
	json.dump(output, sys.stdout, indent=2)
	print()

def cmd_id(args):
	"""Get stable ID for a specific tool."""
	ids = load_ids() or generate_ids()
	tool = args.tool
	if tool in ids:
		print(ids[tool])
	else:
		print(f"unknown tool: {tool}", file=sys.stderr)
		sys.exit(1)

def cmd_schema(args):
	"""Get full schema for a specific tool."""
	defs = load_definitions() or {name: TOOL_SCHEMAS[name] for name in DEFAULT_TOOLS}
	tool = args.tool
	if tool in defs:
		json.dump(defs[tool], sys.stdout, indent=2)
		print()
	else:
		print(f"unknown tool: {tool}", file=sys.stderr)
		sys.exit(1)

def cmd_verify(args):
	"""Verify cached IDs match current schemas."""
	ids = load_ids()
	if not ids:
		print("No cached IDs found. Run 'init' first.")
		return
	
	current_ids = generate_ids()
	mismatched = []
	for name in DEFAULT_TOOLS:
		if ids.get(name) != current_ids.get(name):
			mismatched.append((name, ids.get(name), current_ids.get(name)))
	
	if mismatched:
		print("SCHEMA MISMATCH - definitions have changed:")
		for name, old, new in mismatched:
			print(f"  {name}: {old} -> {new}")
		print("\nRun 'init' to regenerate cache.")
		sys.exit(1)
	else:
		print("All schema IDs match current definitions.")

def main():
	parser = argparse.ArgumentParser(prog="tool-schema-cache")
	sub = parser.add_subparsers(dest="command", required=True)
	
	sub.add_parser("init", help="Generate schema definitions and stable IDs")
	sub.add_parser("first-turn", help="Output full schemas for turn 1")
	sub.add_parser("subsequent-turn", help="Output only tool IDs for turn 2+")
	p = sub.add_parser("id", help="Get stable ID for a tool")
	p.add_argument("tool")
	p = sub.add_parser("schema", help="Get full schema for a tool")
	p.add_argument("tool")
	sub.add_parser("verify", help="Check if cached IDs match current schemas")
	
	args = parser.parse_args()
	{
		"init": cmd_init,
		"first-turn": cmd_first_turn,
		"subsequent-turn": cmd_subsequent_turn,
		"id": cmd_id,
		"schema": cmd_schema,
		"verify": cmd_verify
	}[args.command](args)

if __name__ == "__main__":
	main()
