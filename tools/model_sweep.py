#!/usr/bin/env python3
"""Sweep HuggingFace for GGUF text-generation models.

Phase 1: Enumerate models via API, extract compact metadata, save to JSON.
Phase 2 (optional): Fetch GGUF headers for survivors to get arch/chat_template.

Usage:
	python3 tools/model_sweep.py [--max-models 5000] [--out /path/to/output.json]
	python3 tools/model_sweep.py --phase2 --input /path/to/output.json

The output is a JSON file with one entry per model. Run judgment in a separate pass
by reading the file.
"""

import argparse,json,os,re,sys,time,urllib.parse,urllib.request

API_BASE = "https://huggingface.co/api/models"
PAGE_SIZE = 100
PAUSE = 0.3 # seconds between API calls

KNOWN_FAMILIES = {
	"qwen", "llama", "gemma", "mistral", "granite", "phi", "deepseek",
	"gpt", "falcon", "yi", "glm", "nemotron", "ornith", "cogito",
	"smollm", "lfm", "olmo", "starcoder", "codellama", "exaone",
	"hermes", "kanana", "ministral", "dots", "ling", "longcat",
}

def fetch_page(params, retries=3):
	url = API_BASE + "?" + urllib.parse.urlencode(params, doseq=True)
	for attempt in range(retries):
		try:
			req = urllib.request.Request(url, headers={"User-Agent": "model-sweep/1"})
			with urllib.request.urlopen(req, timeout=30) as resp:
				return json.loads(resp.read())
		except Exception as e:
			if attempt == retries - 1:
				print(f"  ERROR fetching {url}: {e}", file=sys.stderr)
				return []
			time.sleep(2 ** attempt)
	return []

def estimate_size_gb(filename):
	"""Estimate model size from GGUF filename."""
	m = re.search(r"(\d+(?:\.\d+)?)\s*[Bb]", filename)
	if m:
		params = float(m.group(1))
		# Rough: Q4_K_M ~ 0.5 bytes per param
		return params * 0.5
	return None

def extract_family(model_id):
	"""Extract model family from repo name."""
	name = model_id.split("/")[-1].lower()
	# Remove common suffixes
	for suffix in ["-gguf", "-instruct", "-chat", "-it", "-base", "-v2", "-v3"]:
		name = name.replace(suffix, "")
	# Take first word
	parts = re.split(r"[-_]", name)
	return parts[0] if parts else name

def phase1(args):
	out_path = args.out
	# Resume from existing file
	existing = {}
	if os.path.exists(out_path):
		with open(out_path) as f:
			existing = json.load(f)
		print(f"Resuming: {len(existing.get('models', []))} models already saved")

	models = existing.get("models", [])
	seen_ids = {m["id"] for m in models}
	cursor = existing.get("cursor", None)

	total_fetched = len(models)
	target = args.max_models

	print(f"Target: {target} models. Already have: {total_fetched}")

	pipeline_tags = ["text-generation", "image-text-to-text"]
	tag_idx = 0
	while total_fetched < target:
		current_tag = pipeline_tags[tag_idx % len(pipeline_tags)]
		params = [
			("filter", "gguf"),
			("pipeline_tag", current_tag),
			("sort", "downloads"),
			("limit", PAGE_SIZE),
			("expand[]", "downloads"),
			("expand[]", "likes"),
			("expand[]", "tags"),
			("expand[]", "siblings"),
			("expand[]", "cardData"),
		]
		if cursor:
			params.append(("cursor", cursor))

		url = API_BASE + "?" + urllib.parse.urlencode(params, doseq=True)
		page = None
		link_header = None
		for attempt in range(3):
			try:
				req = urllib.request.Request(url, headers={"User-Agent": "model-sweep/1"})
				with urllib.request.urlopen(req, timeout=30) as resp:
					link_header = resp.headers.get("Link", "")
					page = json.loads(resp.read())
				break
			except Exception as e:
				if attempt == 2:
					print(f"  ERROR: {e}", file=sys.stderr)
					page = []
				time.sleep(2 ** attempt)

		if not page:
			print("No more results or error. Stopping.")
			break

		new_count = 0
		for m in page:
			mid = m.get("id", "")
			if mid in seen_ids:
				continue
			seen_ids.add(mid)

			gguf_files = [s["rfilename"] for s in m.get("siblings", [])
						if s["rfilename"].endswith(".gguf")]
			if not gguf_files:
				continue

			tags = m.get("tags", [])
			tool_tags = [t for t in tags if any(k in t.lower() for k in
						("tool", "function", "agent", "chat"))]

			sizes = [estimate_size_gb(f) for f in gguf_files]
			sizes = [s for s in sizes if s is not None]
			est_size = max(sizes) if sizes else None

			if est_size is not None and est_size > 8:
				continue

			family = extract_family(mid)
			is_known = family in KNOWN_FAMILIES

			entry = {
				"id": mid,
				"pipeline_tag": current_tag,
				"downloads": m.get("downloads", 0),
				"likes": m.get("likes", 0),
				"tags": tags,
				"tool_tags": tool_tags,
				"gguf_files": len(gguf_files),
				"gguf_names": gguf_files[:5],
				"est_size_gb": est_size,
				"family": family,
				"is_known_family": is_known,
				"card_tags": m.get("cardData", {}).get("tags", []),
				"license": m.get("cardData", {}).get("license"),
				"last_modified": m.get("lastModified"),
			}
			models.append(entry)
			new_count += 1
			total_fetched += 1

		with open(out_path, "w") as f:
			json.dump({"models": models, "cursor": cursor, "total": len(models)}, f, indent=1)

		print(f"  Page: {len(page)} results, {new_count} new. Total: {len(models)}")

		if len(page) < PAGE_SIZE:
			print("Last page for this tag.")
			tag_idx += 1
			cursor = None
			if tag_idx >= len(pipeline_tags):
				print("All pipeline tags exhausted. Stopping.")
				break
			print(f"Switching to pipeline_tag: {pipeline_tags[tag_idx]}")
			time.sleep(PAUSE)
			continue

		# Extract cursor from Link header
		m = re.search(r'<([^>]+)>;\s*rel="next"', link_header or "")
		if m:
			next_url = m.group(1)
			parsed = urllib.parse.urlparse(next_url)
			qs = urllib.parse.parse_qs(parsed.query)
			cursor = qs.get("cursor", [None])[0]
		else:
			# No more pages for this tag; switch to next tag
			tag_idx += 1
			cursor = None
			if tag_idx >= len(pipeline_tags):
				print("All pipeline tags exhausted. Stopping.")
				break
			print(f"Switching to pipeline_tag: {pipeline_tags[tag_idx]}")

		time.sleep(PAUSE)

	# Final save
	with open(out_path, "w") as f:
		json.dump({"models": models, "total": len(models)}, f, indent=1)

	# Summary
	print(f"\n=== SWEEP COMPLETE ===")
	print(f"Total models: {len(models)}")
	families = {}
	for m in models:
		families[m["family"]] = families.get(m["family"], 0) + 1
	print(f"Unique families: {len(families)}")
	print("\nTop families by count:")
	for fam, count in sorted(families.items(), key=lambda x: -x[1])[:20]:
		known = " (KNOWN)" if fam in KNOWN_FAMILIES else ""
		print(f"  {fam}: {count}{known}")
	print("\nUnknown families (potential new capabilities):")
	for fam, count in sorted(families.items(), key=lambda x: -x[1]):
		if fam not in KNOWN_FAMILIES:
			print(f"  {fam}: {count}")

def phase2(args):
	"""Fetch GGUF headers for survivors to get arch/chat_template."""
	in_path = args.input
	out_path = args.out or in_path

	with open(in_path) as f:
		data = json.load(f)
	models = data["models"]

	# Filter to models that look interesting (not known family, or tool tags)
	candidates = [m for m in models if not m.get("is_known_family") or m.get("tool_tags")]
	print(f"Phase 2: {len(candidates)} candidates from {len(models)} models")

	# For each, try to fetch GGUF metadata
	# This requires downloading the first ~1MB of the GGUF file
	# We'll use the HF resolve URL
	for i, m in enumerate(candidates):
		if m.get("gguf_meta"):
			continue
		# Pick the smallest Q4/Q5 GGUF file
		gguf_names = m.get("gguf_names", [])
		target_file = None
		for name in gguf_names:
			if "Q4_K_M" in name or "Q4_K_S" in name:
				target_file = name
				break
		if not target_file and gguf_names:
			target_file = gguf_names[0]

		if not target_file:
			continue

		url = f"https://huggingface.co/{m['id']}/resolve/main/{target_file}"
		try:
			req = urllib.request.Request(url, headers={"User-Agent": "model-sweep/1", "Range": "bytes=0-1048575"})
			with urllib.request.urlopen(req, timeout=30) as resp:
				header = resp.read()
			# Parse GGUF header (magic + version + tensor count + metadata count)
			# GGUF magic: "GGUF" (4 bytes) + version (uint32)
			if header[:4] == b"GGUF":
				# Try to extract key metadata
				# This is a simplified parse - just check if chat_template exists
				has_template = b"chat_template" in header
				m["gguf_meta"] = {
					"has_chat_template": has_template,
					"header_size": len(header),
					"file": target_file,
				}
			else:
				m["gguf_meta"] = {"error": "not GGUF"}
		except Exception as e:
			m["gguf_meta"] = {"error": str(e)}

		if (i + 1) % 10 == 0:
			print(f"  Processed {i+1}/{len(candidates)}")
			with open(out_path, "w") as f:
				json.dump({"models": models, "total": len(models)}, f, indent=1)

		time.sleep(PAUSE)

	with open(out_path, "w") as f:
		json.dump({"models": models, "total": len(models)}, f, indent=1)
	print(f"Phase 2 complete. Results saved to {out_path}")

def main():
	parser = argparse.ArgumentParser(description="Sweep HuggingFace for GGUF models")
	parser.add_argument("--max-models", type=int, default=5000)
	parser.add_argument("--out", default="/storage/Agents/library/ai/model-sweep-results.json")
	parser.add_argument("--phase2", action="store_true", help="Fetch GGUF headers for survivors")
	parser.add_argument("--input", default=None, help="Input file for phase 2")
	args = parser.parse_args()

	if args.phase2:
		if not args.input:
			args.input = args.out
		phase2(args)
	else:
		phase1(args)

if __name__ == "__main__":
	main()
