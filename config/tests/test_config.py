import config,json,os,tempfile,xtest

def test_merge_overrides_and_preserves():
	default = {"a": 1, "nested": {"x": 1, "y": 2}, "keep": 0}
	override = {"a": 5, "nested": {"x": 9}}
	merged = config.merge(default, override)
	xtest.equal(merged["a"], 5)
	xtest.equal(merged["nested"]["x"], 9)
	xtest.equal(merged["nested"]["y"], 2)
	xtest.equal(merged["keep"], 0)

def test_difference_only_diffs():
	default = {"a": 1, "nested": {"x": 1, "y": 2}, "keep": 0}
	override = {"a": 5, "nested": {"x": 9}}
	diff = config.difference(default, override)
	xtest.equal(diff, {"a": 5, "nested": {"x": 9}})

def test_difference_no_change():
	default = {"a": 1, "b": 2}
	diff = config.difference(default, default)
	xtest.same(diff, config._UNSET)

def test_missing_nested():
	default = {"top": {"a": 1, "b": 2}}
	override = {"top": {"a": 1}}
	miss = config.missing(default, override)
	xtest.equal(miss, ["top.b"])

def test_read_autocreates_from_default():
	with tempfile.TemporaryDirectory() as tmp:
		os.makedirs(os.path.join(tmp, "default"))
		with open(os.path.join(tmp, "default", "x.json"), "w") as f:
			json.dump({"a": 1, "b": 2}, f)
		config.configure(tmp)
		result = config.read("x")
		xtest.equal(result, {"a": 1, "b": 2})
		xtest.equal(os.path.isfile(os.path.join(tmp, "x.json")), True)

def test_fill_omissions():
	with tempfile.TemporaryDirectory() as tmp:
		os.makedirs(os.path.join(tmp, "default"))
		with open(os.path.join(tmp, "default", "y.json"), "w") as f:
			json.dump({"a": 1, "b": 2}, f)
		with open(os.path.join(tmp, "y.json"), "w") as f:
			json.dump({"a": 9}, f)
		config.configure(tmp)
		config.no_omissions("y")
		result = config.read("y")
		xtest.equal(result, {"a": 9, "b": 2})

def test_strict_omissions_raises():
	with tempfile.TemporaryDirectory() as tmp:
		os.makedirs(os.path.join(tmp, "default"))
		with open(os.path.join(tmp, "default", "z.json"), "w") as f:
			json.dump({"a": 1, "b": 2}, f)
		with open(os.path.join(tmp, "z.json"), "w") as f:
			json.dump({"a": 9}, f)
		config.configure(tmp)
		config.no_omissions("z", strict=True)
		def do_read():
			config.read("z")
		xtest.raises(ValueError, do_read)

def test_save_diff_only():
	with tempfile.TemporaryDirectory() as tmp:
		os.makedirs(os.path.join(tmp, "default"))
		with open(os.path.join(tmp, "default", "w.json"), "w") as f:
			json.dump({"a": 1, "b": 2}, f)
		config.configure(tmp)
		config.save("w", {"a": 7, "b": 2}, diff_only=True)
		with open(os.path.join(tmp, "w.json")) as f:
			written = json.load(f)
		xtest.equal(written, {"a": 7})
