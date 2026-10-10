import json,traceback
from urllib.parse import urlparse
from . import err

_MB = 1024*1024
#Read operations
def read_request(client,client_addr,max_header_len=8192,max_content_len=100*_MB,buffer=b""):
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
		if cl > max_content_len:
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
def read_json(client,client_addr,max_header_len=8192,max_content_len=100*_MB):
	result = read_request(client,client_addr,max_header_len,max_content_len)
	try:
		result["payload"] = json.loads(result["payload"])
	except json.JSONDecodeError as e:
		raise err.JSONDecodeError(traceback.format_exc())
	return result
def read_str(client,client_addr,max_header_len=8192,max_content_len=100*_MB):
	result = read_request(client,client_addr,max_header_len,max_content_len)
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
