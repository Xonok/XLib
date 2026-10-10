import traceback,queue,hashlib,base64,struct
from . import err,request,response

web_magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
def handshake(client,key):
	key_hash = hashlib.sha1((key+web_magic).encode())
	response_key = base64.b64encode(key_hash.digest()).decode()
	headers_response = {
		"upgrade": "websocket",
		"connection": "upgrade",
		"sec-websocket-accept": response_key,
		"content-length": 0
	}
	try:
		return response.send_response(client,101,**headers_response) or False
	except Exception as e:
		print(traceback.format_exc())
		return False
def context(req,send_ws):
	return {
		"data": {},
		"_send": queue.Queue(),
		"req": req,
		"send_ws": send_ws
	}
def _recv(client,ctx):
	leftover = ctx["req"]["leftover"]
	b1 = request.read_exact(client,1,leftover)[0]
	b2 = request.read_exact(client,1,leftover)[0]
	fin = (b1 >> 7) & 1 #leftmost bit
	op = b1 & 0x0F #last 4 bits
	size = b2 & 0x7F #last 7 bits(we're ignoring the one that says whether there is a mask)
	if size == 126:
		size_bytes = request.read_exact(client,2,leftover)
		size = struct.unpack('>H', size_bytes)[0]
	elif size == 127:
		size_bytes = request.read_exact(client,8,leftover)
		size = struct.unpack('>Q', size_bytes)[0]
	
	mask = request.read_exact(client,4,leftover)
	data = request.read_exact(client,size,leftover)
	msg = ""
	if op == 1 or op == 9:
		unmasked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
	if op == 1:
		msg = unmasked.decode("utf-8")
	if op == 9:
		_send_pong(client,unmasked,ctx)
	return msg,op
def _send_pong(client,payload,ctx):
	if len(payload) > 125:
		raise ValueError("Pong payload must be 125 bytes or less")
	b1 = 0b10001010 # 0x8A
	b2 = len(payload)
	frame = bytearray([b1, b2])
	frame.extend(payload)
	ctx["_send"].put(payload)
def send(ctx,msg):
	if msg is None:
		raise err.WSMessageNone("Websocket message must not be None.")
	response_bytes = bytearray()
	response_bytes.extend(map(ord,msg))
	msg_length = len(response_bytes)
	if msg_length <= 125:
		header = bytearray([0x81, msg_length])
	elif msg_length <= 65535:
		header = bytearray([0x81, 126]) + struct.pack('>H', msg_length)
	else:
		header = bytearray([0x81, 127]) + struct.pack('>Q', msg_length)
	response_data = bytearray(header)
	response_data.extend(response_bytes)
	ctx["_send"].put(response_bytes)
def receiver(client,ctx,on_message,on_close):
	while True:
		try:
			msg,op = _recv(client,ctx)
			#op 8 is close socket
			if op == 8: break
			#op 1 is text frame. Most common for us.
			if op == 1:
				on_message(client,ctx,msg)
				continue
			if op == 9:
				continue
			print(op)
			#if other opcodes show up, print them
		except Exception:
			print("Websocket error: ")
			print(traceback.format_exc())
			on_close(client,ctx)
			ctx["_send"].put(None)
			break
def sender(client,ctx):
	while True:
		msg = ctx["_send"].get()
		if msg is None:
			break
		try:
			client.sendall(msg)
		except Exception as e:
			if type(e) in [BrokenPipeError,ConnectionResetError,ConnectionAbortedError]:
				pass
			print(traceback.format_exc())
			break
