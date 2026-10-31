"""The direct path can reach Z.ai, whose key is in a different store.

The gap this closes: Z.ai is the one provider `/connect` wrote into opencode's
`credential` table rather than `auth.json` (verified 2026-10-31: auth.json held
only google and openrouter). A reader that only knew auth.json would report a
connected provider as missing its key, which reads as "connect it again" rather
than "the instrument has no route".

The key is read lazily and never printed; the tests use throwaway keys.
"""
import json,os,sqlite3,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest
import transport

def _auth_file(data):
	f = tempfile.NamedTemporaryFile("w",suffix=".json",delete=False)
	json.dump(data,f)
	f.close()
	return f.name

def _db_file(key):
	"""A throwaway opencode-shaped database with one Z.ai credential row."""
	handle = tempfile.NamedTemporaryFile(suffix=".db",delete=False)
	handle.close()
	path = handle.name
	db = sqlite3.connect(path)
	db.execute("create table credential (integration_id text, value text)")
	db.execute("insert into credential values ('zai',?)",
		(json.dumps({"type":"key","key":key}),))
	db.commit()
	db.close()
	return path

def _with(auth=None,db=None):
	saved = (transport.AUTH_PATH,transport.DB_PATH)
	transport.AUTH_PATH = auth
	if db is not None:
		transport.DB_PATH = db
	return saved

def test_the_auth_json_store_wins_when_it_has_the_key():
	auth = _auth_file({"zai":{"key":"z-from-auth"}})
	db = _db_file("z-from-db")
	saved = _with(auth=auth,db=db)
	try:
		xtest.equal(transport._zai_key(),"z-from-auth")
	finally:
		transport.AUTH_PATH,transport.DB_PATH = saved
		os.unlink(auth); os.unlink(db)

def test_the_credential_table_is_the_fallback():
	"""Z.ai's real location on this host; a key read from auth.json only is invisible."""
	auth = _auth_file({"google":{"key":"g-key"}})
	db = _db_file("z-from-db")
	saved = _with(auth=auth,db=db)
	try:
		xtest.equal(transport._zai_key(),"z-from-db")
	finally:
		transport.AUTH_PATH,transport.DB_PATH = saved
		os.unlink(auth); os.unlink(db)

def test_a_missing_key_is_a_transport_error_with_a_fix():
	auth = _auth_file({"google":{"key":"g-key"}})
	db = _db_file("unused")
	os.unlink(db)
	saved = _with(auth=auth,db=db)
	try:
		xtest.raises(transport.TransportError,transport._zai_key,
			"a missing credential must be loud, not a KeyError")
	finally:
		transport.AUTH_PATH,transport.DB_PATH = saved
		os.unlink(auth)

def test_the_zai_header_is_a_bearer_key():
	auth = _auth_file({"zai":{"key":"z-key"}})
	saved = _with(auth=auth)
	try:
		xtest.equal(transport._auth_headers({"provider":"zai"})["Authorization"],
			"Bearer z-key","Z.ai's OpenAI-compatible path takes the key as a bearer")
	finally:
		transport.AUTH_PATH,transport.DB_PATH = saved
		os.unlink(auth)

def test_the_registry_has_a_zai_subject():
	"""A branch with no entry is a route nothing can be measured on."""
	import tomllib
	path = os.path.join(REPO,"tools","modelbench","models.toml")
	reg = tomllib.load(open(path,"rb"))
	model = reg.get("glm-4.7-flash") or {}
	xtest.equal(model.get("provider"),"zai")
	xtest.equal(model.get("transport"),"http")
	xtest.contains("z.ai",model.get("endpoint") or "")
	xtest.equal(model.get("rpm"),5,"the free tier's measured 5 requests a minute")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
