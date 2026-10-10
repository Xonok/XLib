"""
API needed:
DONE - Set a daemon to listen for connections(options: address,new thread, ssl, callback to use after accept)
DONE - function to read a request
DONE - function to send a response(with payload too)
DONE - Function to use to accept callback for serving files.
TBD - Function to use to accept callback when setting up websocket.
(these last 2 can be chained: first use websocket one, then if that falls through, handle as plain file server)
"""

from ._ import helper,err,websocket,request,response,server

_MB = 1024*1024

#Server and handler
def serve_forever(addr,handler,handler_args,ssl_keys=None,new_thread=False,promise=None):
	return server.serve_forever(addr,handler,handler_args,ssl_keys,new_thread,promise)
def await_startup(promise,timeout=5):
	return server.await_startup(promise,timeout)
def wrap_handler(func,func_args,ssl_context,client,client_addr,max_requests=120):
	return server.wrap_handler(func,func_args,ssl_context,client,client_addr,max_requests)
#File server callback. Combine with serve_forever and a config to serve files.
def serve_files(req,config):
	return server.serve_files(req,config)
#Web socket callback. Combine with serve_forever to handle connections.
def serve_websocket(req,on_message=None,on_open=None,on_close=None):
	return server.serve_websocket(req,on_message,on_open,on_close)

#Read operations
def read_request(client,client_addr,max_header_len=8192,max_content_len=100*_MB,buffer=b""):
	return request.read_request(client,client_addr,max_header_len,max_content_len,buffer)
def read_json(client,client_addr,max_header_len=8192,max_content_len=100*_MB):
	return request.read_json(client,client_addr,max_header_len,max_content_len)
def read_str(client,client_addr,max_header_len=8192,max_content_len=100*_MB):
	return request.read_str(client,client_addr,max_header_len,max_content_len)
def read_exact(client,length):
	return request.read_exact(client,length)

#Write operations
#Sends a simple response - no payload.
def send_response(client,code,**headers):
	return response.send_response(client,code,**headers)
#Sends a full response, including payload.
def send_response_full(client,code,payload,compress=True,**headers):
	return response.send_response_full(client,code,payload,compress,**headers)
def send_str(client,code,msg,compress=True,**headers):
	return response.send_str(client,code,msg,compress,**headers)
def send_json(client,code,data,compress=True,**headers):
	return response.send_json(client,code,data,compress,**headers)
def send_redirect(client,code,target,**headers):
	return response.send_redirect(client,code,target,**headers)
def send_file(client,code,path,config,**headers):
	return response.send_file(client,code,path,config,**headers)
def send_not_found(client,config,**headers):
	return response.send_not_found(client,config,**headers)

#Helpers
def config_valid(config):
	return helper.config_valid(config)
