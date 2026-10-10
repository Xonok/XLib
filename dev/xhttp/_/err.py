class HTTPError(Exception): pass
class HTTPHeaderInvalid(HTTPError): pass
class HTTPHeaderNewline(HTTPError): pass
class HTTPHeaderTooBig(HTTPError): pass
class HTTPRequestInvalid(HTTPError): pass
class HTTPDoubleDotForbidden(HTTPError): pass
class HTTPHeaderVersion(HTTPError): pass
class HTTPHeaderDuplicate(HTTPError): pass
class HTTPChunkedEncoding(HTTPError): pass
class HTTPNegativeContentLength(HTTPError): pass
class HTTPContentLengthBad(HTTPError): pass
class HTTPPayloadTooBig(HTTPError): pass
class HTTPBodyIncomplete(HTTPError): pass
#this is a HTTPError as a compromise
class JSONDecodeError(HTTPError): pass
#same
class StrDecodeError(HTTPError): pass
class HTTPCapitalizedHeader(HTTPError): pass
class HTTPCodeUnknown(HTTPError): pass
class WSMessageNone(HTTPError): pass
