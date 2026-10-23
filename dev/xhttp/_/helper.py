import time,sys,re
import email.utils

def datetime_string():
	timestamp = time.time()
	return email.utils.formatdate(timestamp, usegmt=True)
def version_string():
	#TODO: once xhttp is moved to xlib, ensure the version printed here never lies.
	server_version = "xhttp/1.0"
	sys_version = "Python/" + sys.version.split()[0]
	return server_version + " " + sys_version
def header_format(header):
	header = header.replace("_","-")
	header = header.replace("\n","")
	header = header.replace("\r","")
	return header
def has_keepalive(req):
	connection = req["headers"].get("connection","").lower()
	tokens = [t.strip() for t in connection.split(",")]
	if "close" in tokens:
		return False
	if req["protocol"] == "HTTP/1.0":
		return "keep-alive" in tokens
	return True
def accept_encodings(accept_encoding):
	accepts = {}
	if accept_encoding == None:
		return None
	accept_encoding = accept_encoding.strip().lower()
	encodings = accept_encoding.split(",")
	for e in encodings:
		e = e.strip()
		if e == "": continue
		parts = re.split("[;=]",e)
		count = len(parts)
		enc = parts[0].strip()
		key = (parts[1] if count > 1 else "").strip()
		try:
			val = float((parts[2] if count > 2 else "1.0").strip())
		except:
			val = 1.0
		if key == "q" and val == 0:
			accepts[enc] = False
		elif accepts.get(enc) != False:
			accepts[enc] = True
		else:
			pass #specific beats general
	return accepts
def accept_gzip(encodings):
	if encodings is None: return True
	if encodings == {}: return False
	if "gzip" in encodings: return encodings["gzip"]
	if "*" in encodings: return encodings["*"]
	return False
def config_valid(config):
	#TODO: support * as a fallback.
	#use this once after loading config, don't use it on every request
	if not isinstance(config,dict):
		return False,"Config must be a dictionary"
	for k,v in config.items():
		if not k.startswith("."):
			return False,"Each config entry must have a key that starts with a dot, because the keys are file formats."
		if "folder" not in v or "mime" not in v or "compress" not in v:
			return False,"Each config entry must contain these keys: folder, mime, compress"
		if type(v["folder"]) != str:
			return False,"Key 'folder' must be a string."
		if type(v["mime"]) != str:
			return False,"Key 'mime' must be a string."
		if type(v["compress"]) != bool:
			return False,"Key 'compress' must be a bool."
	return True,None
