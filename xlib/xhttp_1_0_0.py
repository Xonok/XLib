## /_/helper.py
import time as _helper__time
import sys as _helper__sys
import email.utils
_helper__email = email

def _helper__datetime_string():
	timestamp = _helper__time.time()
	return _helper__email.utils.formatdate(timestamp, usegmt=True)
def _helper__version_string():
	#TODO: once xhttp is moved to xlib, ensure the version printed here never lies.
	server_version = "xhttp/1.0"
	sys_version = "Python/" + _helper__sys.version.split()[0]
	return server_version + " " + sys_version
def _helper__header_format(header):
	header = header.replace("_","-")
	header = header.replace("\n","")
	header = header.replace("\r","")
	return header
def _helper__has_keepalive(req):
	connection = req["headers"].get("connection","").lower()
	tokens = [t.strip() for t in connection.split(",")]
	if "close" in tokens:
		return False
	if req["protocol"] == "HTTP/1.0":
		return "keep-alive" in tokens
	return True
def _helper__config_valid(config):
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
##! /_/helper.py
## /_/err.py
class _err__HTTPError(Exception): pass
class _err__HTTPHeaderInvalid(_err__HTTPError): pass
class _err__HTTPHeaderNewline(_err__HTTPError): pass
class _err__HTTPHeaderTooBig(_err__HTTPError): pass
class _err__HTTPRequestInvalid(_err__HTTPError): pass
class _err__HTTPDoubleDotForbidden(_err__HTTPError): pass
class _err__HTTPHeaderVersion(_err__HTTPError): pass
class _err__HTTPHeaderDuplicate(_err__HTTPError): pass
class _err__HTTPChunkedEncoding(_err__HTTPError): pass
class _err__HTTPNegativeContentLength(_err__HTTPError): pass
class _err__HTTPContentLengthBad(_err__HTTPError): pass
class _err__HTTPPayloadTooBig(_err__HTTPError): pass
class _err__HTTPBodyIncomplete(_err__HTTPError): pass
#this is a HTTPError as a compromise
class _err__JSONDecodeError(_err__HTTPError): pass
#same
class _err__StrDecodeError(_err__HTTPError): pass
class _err__HTTPCapitalizedHeader(_err__HTTPError): pass
class _err__HTTPCodeUnknown(_err__HTTPError): pass
class _err__WSMessageNone(_err__HTTPError): pass
class _err__WSMessageMustBeString(_err__HTTPError): pass
##! /_/err.py
## /_/request.py
import json as _request__json
import traceback as _request__traceback
from urllib.parse import urlparse as _request__urlparse

__request__MB = 1024*1024
#Read operations
def _request__read_request(client,client_addr,max_header_len=8192,max_content_len=100*__request__MB,buffer=b""):
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
			raise _err__HTTPHeaderTooBig("Header too big.")
		chunk = client.recv(min(4096,max_header_len-len(buffer)))
		if not chunk:
			break
		buffer.extend(chunk)
	if not header_end_idx:
		raise _err__HTTPHeaderInvalid("Header invalid.")
	header_str = buffer[:header_end_idx].decode("iso-8859-1")
	header_lines = header_str.split("\r\n")
	req_line = header_lines.pop(0)
	req_tokens = req_line.split(None,2)
	if len(req_tokens) < 2:
		raise _err__HTTPRequestInvalid("Request is malformed.")
	method,target = req_tokens[0],req_tokens[1]
	if ".." in target:
		raise _err__HTTPDoubleDotForbidden("Request target must not contain '..'.")
	filepath = _request__urlparse(target).path
	if filepath.startswith("/"):
		filepath = filepath[1:]
	protocol = req_tokens[2] if len(req_tokens) == 3 else "HTTP/0.9"
	if protocol not in ["HTTP/0.9","HTTP/1.0","HTTP/1.1"]:
		raise _err__HTTPHeaderVersion("Unknown header version.")
	headers = {}
	for line in header_lines:
		if not line.strip(): continue
		if ":" not in line: raise _err__HTTPHeaderInvalid("Header invalid.")
		if "\n" in line or "\r" in line: raise _err__HTTPHeaderNewline("Newline and carriage return are forbidden in headers.")
		header,value = line.split(":",1)
		header = header.lower()
		if header in headers:
			raise _err__HTTPHeaderDuplicate("Duplicate headers are not allowed.")
		headers[header] = value.strip()
	if "chunked" in headers.get("transfer-encoding","").lower():
		raise _err__HTTPChunkedEncoding("Chunked encoding not supported.")
	cl = headers.get("content-length","0")
	if not cl.isdigit():
		raise _err__HTTPContentLengthBad("Content length invalid.")
	cl = int(cl)
	if cl < 0:
		raise _err__HTTPNegativeContentLength("Content length must never be negative.")
	payload = buffer[header_end_idx:]
	leftover = bytearray()
	if len(payload) > cl:
		leftover = payload[cl:]
		payload = payload[:cl]
	if cl:
		if cl > max_content_len:
			raise _err__HTTPPayloadTooBig("The payload is bigger than allowed.")
		while len(payload) < cl:
			chunk = client.recv(min(4096,cl-len(payload)))
			if not chunk:
				raise _err__HTTPBodyIncomplete("Incomplete payload.")
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
def _request__read_json(client,client_addr,max_header_len=8192,max_content_len=100*__request__MB):
	result = _request__read_request(client,client_addr,max_header_len,max_content_len)
	try:
		result["payload"] = _request__json.loads(result["payload"])
	except _request__json.JSONDecodeError as e:
		raise _err__JSONDecodeError(_request__traceback.format_exc())
	return result
def _request__read_str(client,client_addr,max_header_len=8192,max_content_len=100*__request__MB):
	result = _request__read_request(client,client_addr,max_header_len,max_content_len)
	try:
		result["payload"] = result["payload"].decode("utf-8")
	except UnicodeDecodeError as e:
		raise _err__StrDecodeError(_request__traceback.format_exc())
	return result
def _request__read_exact(client,length,leftover=bytearray()):
	buffer = bytearray()
	while len(buffer) < length and len(leftover) > 0:
		chunk = leftover[:min(length-len(buffer),len(leftover))]
		del leftover[:len(chunk)]
		buffer.extend(chunk)
	while len(buffer) < length:
		chunk = client.recv(length-len(buffer))
		if not chunk:
			raise _err__HTTPBodyIncomplete("Incomplete payload.")
		buffer.extend(chunk)
	return buffer
##! /_/request.py
## /_/response.py
import gzip as _response__gzip
import json as _response__json
import os as _response__os
from http import HTTPStatus as _response__HTTPStatus

_response__http_responses = {s.value: s.phrase for s in _response__HTTPStatus}

#Write operations
#Sends a simple response - no payload.
def _response__send_response(client,code,**headers):
	for k,v in headers.items():
		k = str(k)
		v = str(v)
		if k != k.lower():
			raise _err__HTTPCapitalizedHeader("Capitalized letter detected in header. Please don't do that.")
		if "\r" in k or "\n" in k or "\r" in v or "\n" in v:
			raise _err__HTTPHeaderNewline("Newline and carriage return are forbidden in headers.")
	if "date" not in headers:
		headers["date"] = _helper__datetime_string()
	if "server" not in headers:
		headers["server"] = _helper__version_string()
	if "content-length" not in headers:
		headers["content-length"] = 0
	if headers.get("content-length",0) < 0:
		raise _err__HTTPNegativeContentLength("Content length must never be negative.")
	protocol = "HTTP/1.1"
	if code not in _response__http_responses:
		raise _err__HTTPCodeUnknown("Unknown HTTP code")
	msg = _response__http_responses[code]
	sendbuffer = bytearray()
	sendbuffer.extend(("%s %d %s\r\n" % (protocol,code,msg)).encode("iso-8859-1","strict"))
	for k,v in headers.items():
		k = _helper__header_format(k)
		sendbuffer.extend(("%s: %s\r\n" % (k,v)).encode('iso-8859-1', 'strict'))
	sendbuffer.extend(b"\r\n")
	try:
		client.sendall(sendbuffer)
	except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
		return
	return True
#Sends a full response, including payload.
def _response__send_response_full(client,code,payload,compress=True,**headers):
	headers = {_helper__header_format(k):v for k,v in list(headers.items())}
	size = len(payload)
	if compress:
		payload2 = _response__gzip.compress(payload)
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
	if not _response__send_response(client,code,**headers): return
	try:
		client.sendall(payload)
	except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
		return
	return True
def _response__send_str(client,code,msg,compress=True,**headers):
	return _response__send_response_full(client,code,msg.encode("utf-8"),compress,**headers)
def _response__send_json(client,code,data,compress=True,**headers):
	return _response__send_str(client,code,_response__json.dumps(data),compress,**headers)
def _response__send_redirect(client,code,target,**headers):
	return _response__send_response(client,code,location=target,**headers)
def _response__send_file(client,code,path,config,**headers):
	_,ftype = _response__os.path.splitext(path)
	fconfig = config.get(ftype,config.get("*"))
	if not fconfig:
		#Why: config doesn't say to serve this type of file, so don't.
		return False
	folder = fconfig["folder"]
	mime = fconfig["mime"]
	compress = fconfig.get("compress")
	path_tokens = [folder] if folder else []
	path_tokens += path.split("/")
	path_final = _response__os.path.join(_response__os.getcwd(),*path_tokens)
	if not _response__os.path.exists(path_final) or ".." in path_tokens:
		return False
	payload = open(path_final,"rb").read()
	return _response__send_response_full(client,code,payload,compress=compress,content_type=mime,**headers)
def _response__send_not_found(client,config,**headers):
	if _response__send_file(client,404,"404.html",config,**headers) == False:
		return _response__send_response(client,404,**headers)
	return True
##! /_/response.py
## /_/websocket.py
import traceback as _websocket__traceback
import queue as _websocket__queue
import hashlib as _websocket__hashlib
import base64 as _websocket__base64
import struct as _websocket__struct

_websocket__web_magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
def _websocket__handshake(client,key):
	key_hash = _websocket__hashlib.sha1((key+_websocket__web_magic).encode())
	response_key = _websocket__base64.b64encode(key_hash.digest()).decode()
	headers_response = {
		"upgrade": "websocket",
		"connection": "upgrade",
		"sec-websocket-accept": response_key,
		"content-length": 0
	}
	try:
		resp = _response__send_response(client,101,**headers_response)
		if resp:
			client.settimeout(None)
		return resp or False
	except Exception as e:
		print(_websocket__traceback.format_exc(),flush=True)
		return False
def _websocket__context(req,send_ws):
	return {
		"data": {},
		"_send": _websocket__queue.Queue(),
		"req": req,
		"send_ws": send_ws
	}
def __websocket__recv(client,ctx):
	leftover = ctx["req"]["leftover"]
	b1 = _request__read_exact(client,1,leftover)[0]
	b2 = _request__read_exact(client,1,leftover)[0]
	fin = (b1 >> 7) & 1 #leftmost bit
	op = b1 & 0x0F #last 4 bits
	size = b2 & 0x7F #last 7 bits(we're ignoring the one that says whether there is a mask)
	if size == 126:
		size_bytes = _request__read_exact(client,2,leftover)
		size = _websocket__struct.unpack('>H', size_bytes)[0]
	elif size == 127:
		size_bytes = _request__read_exact(client,8,leftover)
		size = _websocket__struct.unpack('>Q', size_bytes)[0]
	
	mask = _request__read_exact(client,4,leftover)
	data = _request__read_exact(client,size,leftover)
	msg = ""
	if op == 1 or op == 9:
		unmasked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
	if op == 1:
		msg = unmasked.decode("utf-8")
	if op == 9:
		__websocket__send_pong(client,unmasked,ctx)
	return msg,op
def __websocket__send_pong(client,payload,ctx):
	if len(payload) > 125:
		raise ValueError("Pong payload must be 125 bytes or less")
	b1 = 0b10001010 # 0x8A
	b2 = len(payload)
	frame = bytearray([b1, b2])
	frame.extend(payload)
	ctx["_send"].put(frame)
def _websocket__send(ctx,msg):
	if msg is None:
		raise _err__WSMessageNone("Websocket message must not be None.")
	if type(msg) != str:
		raise _err__WSMessageMustBeString("websocket messages must be strings.")
	response_bytes = bytearray()
	response_bytes.extend(map(ord,msg))
	msg_length = len(response_bytes)
	if msg_length <= 125:
		header = bytearray([0x81, msg_length])
	elif msg_length <= 65535:
		header = bytearray([0x81, 126]) + _websocket__struct.pack('>H', msg_length)
	else:
		header = bytearray([0x81, 127]) + _websocket__struct.pack('>Q', msg_length)
	response_data = bytearray(header)
	response_data.extend(response_bytes)
	ctx["_send"].put(response_data)
def _websocket__receiver(client,ctx,on_message,on_close):
	while True:
		try:
			msg,op = __websocket__recv(client,ctx)
			#op 8 is close socket
			if op == 8:
				ctx["_send"].put(None)
				on_close(client,ctx)
				break
			#op 1 is text frame. Most common for us.
			if op == 1:
				on_message(client,ctx,msg)
				continue
			if op == 9:
				continue
			print(op,flush=True)
			#if other opcodes show up, print them
		except Exception:
			print("Websocket error: ",flush=True)
			print(_websocket__traceback.format_exc(),flush=True)
			on_close(client,ctx)
			ctx["_send"].put(None)
			break
def _websocket__sender(client,ctx):
	while True:
		msg = ctx["_send"].get()
		if msg is None:
			break
		try:
			client.sendall(msg)
		except Exception as e:
			print(_websocket__traceback.format_exc(),flush=True)
			if type(e) in [BrokenPipeError,ConnectionResetError,ConnectionAbortedError]:
				break
			break
##! /_/websocket.py
## /_/server.py
import _thread as __server__thread
import socket as _server__socket
import ssl as _server__ssl
import traceback as _server__traceback
from concurrent.futures import Future as _server__Future

#Server and handler
def _server__serve_forever(addr,handler,handler_args,ssl_keys=None,new_thread=False,promise=None):
	if promise is None:
		promise = _server__Future()
	if new_thread:
		__server__thread.start_new_thread(_server__serve_forever,(addr,handler,handler_args,ssl_keys,False,promise))
		return promise
	try:
		context = None
		if ssl_keys is not None:
			certificate,private_key = ssl_keys
			context = _server__ssl.create_default_context(_server__ssl.Purpose.CLIENT_AUTH)
			context.load_cert_chain(certificate,private_key)
		sock = _server__socket.socket()
		sock.setsockopt(_server__socket.SOL_SOCKET, _server__socket.SO_REUSEADDR, 1)
		sock.bind((addr))
		sock.listen()
		print("Serving you forever:",addr,flush=True)
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
			__server__thread.start_new_thread(_server__wrap_handler,(handler,handler_args,context,s,c))
		except Exception:
			print(_server__traceback.format_exc(),flush=True)
			if s and s.fileno() != -1:
				_response__send_response(s,500)
				s.close()
def _server__await_startup(promise,timeout=5):
	promise.result(timeout=timeout)
def _server__wrap_handler(func,func_args,ssl_context,client,client_addr,max_requests=1):
	buffer = b""
	try:
		if ssl_context:
			client = ssl_context.wrap_socket(client,server_side=True)
		for _ in range(max_requests):
			req = _request__read_request(client,client_addr,buffer=buffer)
			buffer = req["leftover"]
			func(req,*func_args)
			if not _helper__has_keepalive(req):
				break
	except _err__HTTPHeaderVersion:
		if client and client.fileno() != -1:
			_response__send_response(client,505)
			client.close()
	except TimeoutError:
		pass # idle keep-alive expiry - a normal close, not an error
	except Exception as e:
		if type(e) in [_server__ssl.SSLError,ConnectionResetError,ConnectionAbortedError]:
			return
		print("Ignoring unhandled exception for the sake of stability.(DumbHTTP)",flush=True)
		print(_server__traceback.format_exc(),flush=True)
		try:
			if client:
				_response__send_response(client,500)
				client.close()
		except BrokenPipeError:
			return
	if client and client.fileno() != -1:
		client.close()
#File server callback. Combine with serve_forever and a config to serve files.
def _server__serve_files(req,config):
	client = req["client"]
	if req["method"] != "GET":
		if client and client.fileno() != -1:
			_response__send_response(client,400)
			client.close()
		return
	fpath = req["filepath"]
	if _response__send_file(client,200,fpath,config) == False:
		_response__send_not_found(client,config)

#Web socket callback. Combine with serve_forever to handle connections.
def _server__serve_websocket(req,on_message=None,on_open=None,on_close=None):
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
	
	#Why: Closure that captures the value of ctx here. Makes it harder to accidentally pass the wrong context.
	def send_ws(msg):
		_websocket__send(ctx,msg)
	
	ctx = _websocket__context(req,send_ws)
	if not _websocket__handshake(client,key):
		on_close(client,ctx)
		return False
	
	on_open(client,ctx)
	__server__thread.start_new_thread(_websocket__receiver,(client,ctx,on_message,on_close))
	#Blocking call:
	_websocket__sender(client,ctx)
	#Signal a successful websocket session, so nothing else would be done:
	return True
##! /_/server.py
## xhttp.py
"""
API needed:
DONE - Set a daemon to listen for connections(options: address,new thread, ssl, callback to use after accept)
DONE - function to read a request
DONE - function to send a response(with payload too)
DONE - Function to use to accept callback for serving files.
TBD - Function to use to accept callback when setting up websocket.
(these last 2 can be chained: first use websocket one, then if that falls through, handle as plain file server)
"""

_MB = 1024*1024

#Server and handler
def serve_forever(addr,handler,handler_args,ssl_keys=None,new_thread=False,promise=None):
	return _server__serve_forever(addr,handler,handler_args,ssl_keys,new_thread,promise)
def await_startup(promise,timeout=5):
	return _server__await_startup(promise,timeout)
def wrap_handler(func,func_args,ssl_context,client,client_addr,max_requests=120):
	return _server__wrap_handler(func,func_args,ssl_context,client,client_addr,max_requests)
#File server callback. Combine with serve_forever and a config to serve files.
def serve_files(req,config):
	return _server__serve_files(req,config)
#Web socket callback. Combine with serve_forever to handle connections.
def serve_websocket(req,on_message=None,on_open=None,on_close=None):
	return _server__serve_websocket(req,on_message,on_open,on_close)

#Read operations
def read_request(client,client_addr,max_header_len=8192,max_content_len=100*_MB,buffer=b""):
	return _request__read_request(client,client_addr,max_header_len,max_content_len,buffer)
def read_json(client,client_addr,max_header_len=8192,max_content_len=100*_MB):
	return _request__read_json(client,client_addr,max_header_len,max_content_len)
def read_str(client,client_addr,max_header_len=8192,max_content_len=100*_MB):
	return _request__read_str(client,client_addr,max_header_len,max_content_len)
def read_exact(client,length):
	return _request__read_exact(client,length)

#Write operations
#Sends a simple response - no payload.
def send_response(client,code,**headers):
	return _response__send_response(client,code,**headers)
#Sends a full response, including payload.
def send_response_full(client,code,payload,compress=True,**headers):
	return _response__send_response_full(client,code,payload,compress,**headers)
def send_str(client,code,msg,compress=True,**headers):
	return _response__send_str(client,code,msg,compress,**headers)
def send_json(client,code,data,compress=True,**headers):
	return _response__send_json(client,code,data,compress,**headers)
def send_redirect(client,code,target,**headers):
	return _response__send_redirect(client,code,target,**headers)
def send_file(client,code,path,config,**headers):
	return _response__send_file(client,code,path,config,**headers)
def send_not_found(client,config,**headers):
	return _response__send_not_found(client,config,**headers)

#Helpers
def config_valid(config):
	return _helper__config_valid(config)

#Errors
err_HTTPError = _err__HTTPError #the generic error that contains all the others
err_HTTPHeaderInvalid = _err__HTTPHeaderInvalid
err_HTTPHeaderNewline = _err__HTTPHeaderNewline
err_HTTPHeaderTooBig = _err__HTTPHeaderTooBig
err_HTTPRequestInvalid = _err__HTTPRequestInvalid
err_HTTPDoubleDotForbidden = _err__HTTPDoubleDotForbidden
err_HTTPHeaderVersion = _err__HTTPHeaderVersion
err_HTTPHeaderDuplicate = _err__HTTPHeaderDuplicate
err_HTTPChunkedEncoding = _err__HTTPChunkedEncoding
err_HTTPNegativeContentLength = _err__HTTPNegativeContentLength
err_HTTPContentLengthBad = _err__HTTPContentLengthBad
err_HTTPPayloadTooBig = _err__HTTPPayloadTooBig
err_HTTPBodyIncomplete = _err__HTTPBodyIncomplete
err_JSONDecodeError = _err__JSONDecodeError
err_StrDecodeError = _err__StrDecodeError
err_HTTPCapitalizedHeader = _err__HTTPCapitalizedHeader
err_HTTPCodeUnknown = _err__HTTPCodeUnknown
err_WSMessageNone = _err__WSMessageNone
err_WSMessageMustBeString = _err__WSMessageMustBeString
##! xhttp.py
