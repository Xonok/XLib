import time,sys
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
