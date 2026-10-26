import _thread,socket,ssl,traceback
from concurrent.futures import Future
from . import err,response,request,helper,websocket

#Server and handler
def serve_forever(addr,handler,handler_args,ssl_keys=None,new_thread=False,promise=None,max_requests=120,redirect_from=None):
	if redirect_from is not None and ssl_keys is None:
		raise err.HTTPRedirectNoSSL("SSL keys must be provided when using redirect_from.")
	if promise is None:
		promise = Future()
	if new_thread:
		_thread.start_new_thread(serve_forever,(addr,handler,handler_args,ssl_keys,False,promise,max_requests,redirect_from))
		return promise
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
		#Why: catch both errors from the same place.
		if redirect_from is not None:
			http_to_https((addr[0],redirect_from),addr[1],True).result()
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
			_thread.start_new_thread(wrap_handler,(handler,handler_args,context,s,c,max_requests))
		except Exception:
			print(traceback.format_exc(),flush=True)
			if s and s.fileno() != -1:
				response.send_response(s,500)
				s.close()
def await_startup(promise,timeout=5):
	promise.result(timeout=timeout)
def wrap_handler(func,func_args,ssl_context,client,client_addr,max_requests):
	buffer = b""
	try:
		if ssl_context:
			client = ssl_context.wrap_socket(client,server_side=True)
		for req_nr in range(max_requests):
			req = request.read_request(client,client_addr,buffer=buffer)
			buffer = req["leftover"]
			accepted = helper.accept_encodings(req["headers"].get("accept-encoding"))
			response.set_accept_encodings(accepted)
			keepalive = helper.has_keepalive(req)
			if req_nr == max_requests-1 or not keepalive:
				response.mark_closing()
			func(req,*func_args)
			response.clear_accept_encodings()
			if not keepalive:
				break
	except err.HTTPHeaderInvalid:
		pass #request ended halfway
	except err.HTTPHeaderVersion:
		if client and client.fileno() != -1:
			response.send_response(client,505)
	except err.HTTPDoubleDotForbidden:
		if client and client.fileno() != -1:
			response.send_response(client,400)
	except TimeoutError:
		pass # idle keep-alive expiry - a normal close, not an error
	except Exception as e:
		if type(e) in [ssl.SSLError,ConnectionResetError,ConnectionAbortedError]:
			return
		print("Ignoring unhandled exception for the sake of stability.(DumbHTTP)",flush=True)
		print(traceback.format_exc(),flush=True)
		try:
			if client:
				response.send_response(client,500)
				client.close()
		except BrokenPipeError:
			return
	if client and client.fileno() != -1:
		client.close()
#File server callback. Combine with serve_forever and a config to serve files.
def serve_files(req,config):
	#TODO: add warning when config has "*" mapped to folder "". Security issue.
	client = req["client"]
	if req["method"] != "GET":
		if client and client.fileno() != -1:
			response.send_response(client,400)
		return
	fpath = req["filepath"]
	if response.send_file(client,200,fpath,config) == False:
		response.send_not_found(client,config)

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
	
	#Why: Closure that captures the value of ctx here. Makes it harder to accidentally pass the wrong context.
	def send_ws(msg):
		websocket.send(ctx,msg)
	
	ctx = websocket.context(req,send_ws)
	if not websocket.handshake(client,key):
		on_close(client,ctx)
		return False
	
	on_open(client,ctx)
	_thread.start_new_thread(websocket.receiver,(client,ctx,on_message,on_close))
	#Blocking call:
	websocket.sender(client,ctx)
	#Signal a successful websocket session, so nothing else would be done:
	return True
def http_to_https(addr,https_port=None,new_thread=False):
	def redirect(req):
		client = req["client"]
		host = req["headers"].get("host")
		if not host:
			#Why: can't construct redirect url without hostname.
			response.send_response(client,400)
			return
		hostname = host[:host.index("]")+1] if host.startswith("[") else host.split(":",1)[0]
		if https_port is None or https_port == 443:
			location = "https://" + hostname + req["target"]
		else:
			location = "https://%s:%d%s" % (hostname,https_port,req["target"])
		response.send_redirect(client,308,location)
	return serve_forever(addr,redirect,(),None,new_thread)
