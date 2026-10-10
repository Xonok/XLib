import _thread,socket,ssl,traceback
from concurrent.futures import Future
from . import err,response,request,helper,websocket

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
				response.send_response(s,500)
				s.close()
def await_startup(promise,timeout=5):
	promise.result(timeout=timeout)
def wrap_handler(func,func_args,ssl_context,client,client_addr,max_requests=120):
	buffer = b""
	try:
		if ssl_context:
			client = ssl_context.wrap_socket(client,server_side=True)
		for _ in range(max_requests):
			req = request.read_request(client,client_addr,buffer=buffer)
			buffer = req["leftover"]
			func(req,*func_args)
			if not helper.has_keepalive(req):
				break
	except err.HTTPHeaderVersion:
		if client and client.fileno() != -1:
			response.send_response(client,505)
			client.close()
	except TimeoutError:
		pass # idle keep-alive expiry - a normal close, not an error
	except Exception as e:
		try:
			if client:
				response.send_response(client,500)
				client.close()
		except BrokenPipeError:
			return
		if type(e) in [ssl.SSLError,ConnectionResetError,ConnectionAbortedError]:
			return
		print("Ignoring unhandled exception for the sake of stability.(DumbHTTP)")
		print(traceback.format_exc())
	if client and client.fileno() != -1:
		client.close()
#File server callback. Combine with serve_forever and a config to serve files.
def serve_files(req,config):
	client = req["client"]
	if req["method"] != "GET":
		if client and client.fileno() != -1:
			response.send_response(client,400)
			client.close()
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
		return
	
	on_open(client,ctx)
	_thread.start_new_thread(websocket.sender,(client,ctx))
	_thread.start_new_thread(websocket.receiver,(client,ctx,on_message,on_close))
	return ctx
