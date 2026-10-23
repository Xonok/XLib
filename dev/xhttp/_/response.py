import gzip,json,os,threading
from http import HTTPStatus
from . import err,helper

http_responses = {s.value: s.phrase for s in HTTPStatus}

#Write operations
#Sends a simple response - no payload.
def send_response(client,code,**headers):
	for k,v in headers.items():
		k = str(k)
		v = str(v)
		if k != k.lower():
			raise err.HTTPCapitalizedHeader("Capitalized letter detected in header. Please don't do that.")
		if "\r" in k or "\n" in k or "\r" in v or "\n" in v:
			raise err.HTTPHeaderNewline("Newline and carriage return are forbidden in headers.")
	if is_closing() and "connection" not in headers:
		headers["connection"] = "close"
	if "date" not in headers:
		headers["date"] = helper.datetime_string()
	if "server" not in headers:
		headers["server"] = helper.version_string()
	if "content-length" not in headers:
		headers["content-length"] = 0
	if headers.get("content-length",0) < 0:
		raise err.HTTPNegativeContentLength("Content length must never be negative.")
	protocol = "HTTP/1.1"
	if code not in http_responses:
		raise err.HTTPCodeUnknown("Unknown HTTP code")
	msg = http_responses[code]
	sendbuffer = bytearray()
	sendbuffer.extend(("%s %d %s\r\n" % (protocol,code,msg)).encode("iso-8859-1","strict"))
	for k,v in headers.items():
		k = helper.header_format(k)
		sendbuffer.extend(("%s: %s\r\n" % (k,v)).encode('iso-8859-1', 'strict'))
	sendbuffer.extend(b"\r\n")
	try:
		client.sendall(sendbuffer)
	except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
		return
	return True
#Sends a full response, including payload.
def send_response_full(client,code,payload,compress=True,**headers):
	headers = {helper.header_format(k):v for k,v in list(headers.items())}
	accept_encodings = get_accept_encodings()
	gzip_accepted = helper.accept_gzip(accept_encodings)
	size = len(payload)
	if compress and gzip_accepted:
		payload2 = gzip.compress(payload)
		size2 = len(payload2)
		if size2 < size:
			payload = payload2
			size = size2
			headers["content-encoding"] = "gzip"
	headers["content-length"] = size
	if "content-type" not in headers:
		headers["content-type"] = "text/plain"
	if "access-control-allow-origin" not in headers:
		headers["access-control-allow-origin"] = "*"
	if not send_response(client,code,**headers): return
	try:
		client.sendall(payload)
	except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
		return
	return True
def send_str(client,code,msg,compress=True,**headers):
	return send_response_full(client,code,msg.encode("utf-8"),compress,**headers)
def send_json(client,code,data,compress=True,**headers):
	return send_str(client,code,json.dumps(data),compress,**headers)
def send_redirect(client,code,target,**headers):
	return send_response(client,code,location=target,**headers)
def send_file(client,code,path,config,**headers):
	_,ftype = os.path.splitext(path)
	fconfig = config.get(ftype,config.get("*"))
	if not fconfig:
		#Why: config doesn't say to serve this type of file, so don't.
		return False
	folder = fconfig["folder"]
	mime = fconfig["mime"]
	compress = fconfig.get("compress")
	path_root = os.path.realpath(os.getcwd())
	if folder:
		path_root = os.path.realpath(os.path.join(os.getcwd(),folder))
	path_full = os.path.realpath(os.path.join(path_root,*path.split("/")))
	if os.path.commonpath([path_root,path_full]) != path_root:
		return False
	if not os.path.isfile(path_full):
		return False
	if ".." in path.split("/"):
		return False
	with open(path_full,"rb") as f:
		payload = f.read()
	return send_response_full(client,code,payload,compress=compress,content_type=mime,**headers)
def send_not_found(client,config,**headers):
	if send_file(client,404,"404.html",config,**headers) == False:
		return send_response(client,404,**headers)
	return True
#helpers
_state = threading.local()
def mark_closing(): _state.closing = True
def is_closing(): return getattr(_state,"closing",False)
def set_accept_encodings(accepted): _state.accept_encodings = accepted
def get_accept_encodings(): return getattr(_state,"accept_encodings",None)
def clear_accept_encodings(): return delattr(_state,"accept_encodings")
