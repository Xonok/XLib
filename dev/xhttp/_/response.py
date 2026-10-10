import gzip,json,os
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
	size = len(payload)
	if compress:
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
	folder,mime,compress = config.get(ftype)
	path_tokens = [folder] if folder else []
	path_tokens += path.split("/")
	path_final = os.path.join(os.getcwd(),*path_tokens)
	if not os.path.exists(path_final) or ".." in path_tokens:
		return False
	payload = open(path_final,"rb").read()
	return send_response_full(client,code,payload,compress=compress,content_type=mime,**headers)
def send_not_found(client,config,**headers):
	if send_file(client,404,"404.html",config,**headers) == False:
		return send_response(client,404,**headers)
	return True
