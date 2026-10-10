"""
API needed:
DONE - Set a daemon to listen for connections(options: address,new thread, ssl, callback to use after accept)
DONE - function to read a request
DONE - function to send a response(with payload too)
DONE - Function to use to accept callback for serving files.
TBD - Function to use to accept callback when setting up websocket.
(these last 2 can be chained: first use websocket one, then if that falls through, handle as plain file server)
"""

import _thread,socket,traceback,ssl,os,gzip,json,hashlib
from http import HTTPStatus
from urllib.parse import urlparse
from concurrent.futures import Future
from ._ import helper,err,websocket

_MB = 1024*1024
http_responses = {s.value: s.phrase for s in HTTPStatus}

#Server and handler
def serve_forever(addr,handler,handler_args,ssl_keys=None,new_thread=False,promise=None):
	if promise is None:
		promise = Future()
	if new_thread:
		_thread.start_new_thread(serve_forever,(addr,handler,handler_args,ssl_keys,False,promise))
		return
	try:
		context = None
		if ssl_keys is not None:
			certificate,private_key = ssl_keys
			context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
			context.load_cert_chain(certificate,private_key)
		sock = socket.socket()
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		sock.bind((addr))
		sock.listen()
		print("Serving you forever:",addr)
		promise.set_result(True)
	except Exception as e:
		promise.set_exception(e)
		raise
	while True:
		s = None
		#Why: listener must never crash.
		try:
			s,c = sock.accept()
			s.settimeout(60)
			_thread.start_new_thread(wrap_handler,(handler,handler_args,context,s,c))
		except Exception:
			print(traceback.format_exc())
			if s and s.fileno() != -1:
				send_response(s,500)
				s.close()
def await_startup(promise,timeout=5):
	promise.result(timeout=timeout)
def wrap_handler(func,func_args,ssl_context,client,client_addr,max_requests=120):
	buffer = b""
	try:
		if ssl_context:
			client = ssl_context.wrap_socket(client,server_side=True)
		for _ in range(max_requests):
			req = read_request(client,client_addr,buffer=buffer)
			buffer = req["leftover"]
			func(req,*func_args)
			if not helper.has_keepalive(req):
				break
	except err.HTTPHeaderVersion:
		if client and client.fileno() != -1:
			send_response(client,505)
			client.close()
	except TimeoutError:
		pass # idle keep-alive expiry - a normal close, not an error
	except Exception as e:
		try:
			if client:
				send_response(client,500)
				client.close()
		except BrokenPipeError:
			return
		if type(e) in [ssl.SSLError,ConnectionResetError,ConnectionAbortedError]:
			return
		print("Ignoring unhandled exception for the sake of stability.(DumbHTTP)")
		print(traceback.format_exc())
	if client and client.fileno() != -1:
		client.close()

#Read operations
def read_request(client,client_addr,max_header_len=8192,max_content_length=100*_MB,buffer=b""):
	if max_header_len < 1:
		raise Exception("Max header len must never be 0 or negative.")
	header_end = b"\r\n\r\n"
	buffer = bytearray(buffer)
	header_end_idx = 0
	while True:
		idx = buffer.find(header_end)
		if idx != -1:
			header_end_idx = idx + len(header_end)
			break
		if len(buffer) == max_header_len:
			raise err.HTTPHeaderTooBig("Header too big.")
		chunk = client.recv(min(4096,max_header_len-len(buffer)))
		if not chunk:
			break
		buffer.extend(chunk)
	if not header_end_idx: raise err.HTTPHeaderInvalid("Header invalid.")
	header_str = buffer[:header_end_idx].decode("iso-8859-1")
	header_lines = header_str.split("\r\n")
	req_line = header_lines.pop(0)
	req_tokens = req_line.split(None,2)
	if len(req_tokens) < 2:
		raise err.HTTPRequestInvalid("Request is malformed.")
	method,target = req_tokens[0],req_tokens[1]
	if ".." in target:
		raise err.HTTPDoubleDotForbidden("Request target must not contain '..'.")
	filepath = urlparse(target).path
	if filepath.startswith("/"):
		filepath = filepath[1:]
	protocol = req_tokens[2] if len(req_tokens) == 3 else "HTTP/0.9"
	if protocol not in ["HTTP/0.9","HTTP/1.0","HTTP/1.1"]:
		raise err.HTTPHeaderVersion("Unknown header version.")
	headers = {}
	for line in header_lines:
		if not line.strip(): continue
		if ":" not in line: raise err.HTTPHeaderInvalid("Header invalid.")
		if "\n" in line or "\r" in line: raise err.HTTPHeaderNewline("Newline and carriage return are forbidden in headers.")
		header,value = line.split(":",1)
		header = header.lower()
		if header in headers:
			raise err.HTTPHeaderDuplicate("Duplicate headers are not allowed.")
		headers[header] = value.strip()
	if "chunked" in headers.get("transfer-encoding","").lower():
		raise err.HTTPChunkedEncoding("Chunked encoding not supported.")
	cl = headers.get("content-length","0")
	if not cl.isdigit():
		raise err.HTTPContentLengthBad("Content length invalid.")
	cl = int(cl)
	if cl < 0:
		raise err.HTTPNegativeContentLength("Content length must never be negative.")
	payload = buffer[header_end_idx:]
	leftover = b""
	if len(payload) > cl:
		leftover = payload[cl:]
		payload = payload[:cl]
	if cl:
		if cl > max_content_length:
			raise err.HTTPPayloadTooBig("The payload is bigger than allowed.")
		while len(payload) < cl:
			chunk = client.recv(min(4096,cl-len(payload)))
			if not chunk:
				raise err.HTTPBodyIncomplete("Incomplete payload.")
			payload.extend(chunk)
	
	return {
		"client": client,
		"client_addr": client_addr,
		"method": method,
		"target": target,
		"filepath": filepath,
		"protocol": protocol,
		"headers": headers,
		"payload": payload,
		"leftover": leftover
	}
def read_json(client,client_addr,max_header_len=8192,max_content_length=100*_MB):
	result = read_request(client,client_addr,max_header_len,max_content_length)
	try:
		result["payload"] = json.loads(result["payload"])
	except json.JSONDecodeError as e:
		raise err.JSONDecodeError(traceback.format_exc())
	return result
def read_str(client,client_addr,max_header_len=8192,max_content_length=100*_MB):
	result = read_request(client,client_addr,max_header_len,max_content_length)
	try:
		result["payload"] = result["payload"].decode("utf-8")
	except UnicodeDecodeError as e:
		raise err.StrDecodeError(traceback.format_exc())
	return result
def read_exact(client,length):
	buffer = bytearray()
	while len(buffer) < length:
		chunk = client.recv(length-len(buffer))
		if not chunk:
			raise err.HTTPBodyIncomplete("Incomplete payload.")
		buffer.extend(chunk)
	return buffer

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
	return send_response_full(client,code,payload,compress=compress,**headers)
def send_not_found(client,config,**headers):
	if send_file(client,404,"404.html",config,**headers) == False:
		return send_response(client,404,**headers)
	return True

#File server callback. Combine with serve_forever and a config to serve files.
def serve_files(req,config):
	client = req["client"]
	if req["method"] != "GET":
		if client and client.fileno() != -1:
			send_response(client,400)
			client.close()
		return
	fpath = req["filepath"]
	if send_file(client,200,fpath,config) == False:
		send_not_found(client,config)

#Web socket callback. Combine with serve_forever to handle connections.
def serve_websocket(req,on_message=None,on_open=None,on_close=None):
	client = req["client"]
	method = req["method"]
	headers = req["headers"]
	upgrade = headers.get("upgrade","").lower()
	connection = headers.get("connection","").lower()
	key = headers.get("sec-websocket-key")
	version = headers.get("sec-websocket-version")
	
	if method.upper() != "GET": return
	if upgrade != "websocket": return
	if "upgrade" not in connection: return
	if key is None: return
	if version is None: return
	
	#Why: Closure that captures the value of client here. Makes it harder to accidentally pass the wrong client.
	def send_ws(msg):
		websocket.send(client,msg)
	
	ctx = websocket.context(req,send_ws)
	if not websocket.handshake(client,key):
		on_close(client,ctx)
		return
	
	on_open(client,ctx)
	_thread.start_new_thread(websocket.sender,(client,ctx))
	_thread.start_new_thread(websocket.receiver,(client,ctx,on_message,on_close))
	return ctx

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
		if type(config["folder"]) != str:
			return False,"Key 'folder' must be a string."
		if type(config["mime"]) != str:
			return False,"Key 'mime' must be a string."
		if type(config["compress"]) != bool:
			return False,"Key 'compress' must be a bool."
	return True,None
