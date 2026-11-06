"""NIM is reachable directly, and its key lives where `/connect` put it.

The gap this closes: NIM answers on this host (probed 2026-11-06) but the instrument had
no `nim` provider, no key reader and no registry entry, so a whole free pool was invisible.
The key is in opencode's `credential` table, not `auth.json`, exactly like Z.ai's.

The second half of the file is the registry's own shape: every NIM entry must share the
`nim` aggregate group and a limit below the provider's per-model figure, because the
group's limit is what keeps two waves from adding up to an account block.
"""
import json,os,sqlite3,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0,os.path.join(REPO,"dev","xtest"))
sys.path.insert(0,os.path.join(REPO,"tools","modelbench"))
import xtest,transport

def _auth_file(data):
	f = tempfile.NamedTemporaryFile("w",suffix=".json",delete=False)
	json.dump(data,f)
	f.close()
	return f.name

def _db_file(key):
	handle = tempfile.NamedTemporaryFile(suffix=".db",delete=False)
	handle.close()
	path = handle.name
	db = sqlite3.connect(path)
	db.execute("create table credential (integration_id text, value text, active int, time_updated int)")
	db.execute("insert into credential values ('nvidia',?,1,1)",(json.dumps({"type":"key","key":key}),))
	db.commit()
	db.close()
	return path

def _with(auth=None,db=None):
	saved = (transport.AUTH_PATH,transport.DB_PATH)
	transport.AUTH_PATH = auth
	if db is not None:
		transport.DB_PATH = db
	return saved

def test_the_nvidia_key_comes_from_the_credential_table():
	auth = _auth_file({"google":{"key":"g-key"}})
	db = _db_file("n-from-db")
	saved = _with(auth=auth,db=db)
	try:
		xtest.equal(transport._nvidia_key(),"n-from-db",
			"NIM's key is in the credential table; auth.json has only google/openrouter")
	finally:
		transport.AUTH_PATH,transport.DB_PATH = saved
		os.unlink(auth); os.unlink(db)

def test_the_auth_json_store_wins_when_it_has_the_key():
	auth = _auth_file({"nvidia":{"key":"n-from-auth"}})
	db = _db_file("n-from-db")
	saved = _with(auth=auth,db=db)
	try:
		xtest.equal(transport._nvidia_key(),"n-from-auth")
	finally:
		transport.AUTH_PATH,transport.DB_PATH = saved
		os.unlink(auth); os.unlink(db)

def test_a_missing_key_is_a_transport_error_with_a_fix():
	auth = _auth_file({"google":{"key":"g-key"}})
	db = tempfile.NamedTemporaryFile(suffix=".db",delete=False).name
	saved = _with(auth=auth,db=db)
	try:
		xtest.raises(transport.TransportError,transport._nvidia_key,
			"a missing credential must be loud, not a KeyError")
	finally:
		transport.AUTH_PATH,transport.DB_PATH = saved
		os.unlink(auth); os.unlink(db)

def test_the_nim_header_is_a_bearer_key():
	auth = _auth_file({"nvidia":{"key":"n-key"}})
	saved = _with(auth=auth)
	try:
		xtest.equal(transport._auth_headers({"provider":"nim"})["Authorization"],
			"Bearer n-key","NIM's OpenAI-compatible path takes the key as a bearer")
	finally:
		transport.AUTH_PATH,transport.DB_PATH = saved
		os.unlink(auth)

def test_every_nim_entry_is_in_the_aggregate_group():
	import tomllib
	path = os.path.join(REPO,"tools","modelbench","models.toml")
	reg = tomllib.load(open(path,"rb"))
	nim = {name:model for name,model in reg.items() if model.get("provider") == "nim"}
	xtest.true(nim,"the registry must have NIM subjects once the route exists")
	for name,model in nim.items():
		xtest.equal(model.get("aggregate"),"nim",f"{name} must share NIM's aggregate window")
		xtest.true(model.get("aggregate_rpm") and model["aggregate_rpm"] < 40,
			f"{name}'s aggregate limit must sit below the provider's per-model 40")
		xtest.equal(model.get("transport"),"http",f"{name} is a direct route")
		xtest.contains("integrate.api.nvidia.com",model.get("endpoint") or "")

def test_an_aggregate_group_without_a_limit_is_refused():
	reg = {"broken":{"id":"x","provider":"nim","transport":"http","endpoint":"https://x",
		"aggregate":"nim"}}
	problems = transport.validate_registry(reg)
	xtest.true(any("aggregate_rpm" in p for p in problems),
		"a group with no limit is a no-op, and a silent one")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
