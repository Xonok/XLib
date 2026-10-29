"""The config: source entries, their options, and the failures that must be visible."""
import json,os,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk._ import config

def _write(folder, data):
	path = os.path.join(folder, "config.json")
	with open(path, "w", encoding="utf-8") as file:
		json.dump(data, file)
	return path

def _config(folder, data):
	return config.Config(_write(folder, data))

def test_the_defaults_when_the_config_is_empty():
	with tempfile.TemporaryDirectory() as folder:
		conf = _config(folder, {})
		xtest.equal(conf.sources, [], "no sources configured")
		xtest.equal(conf.news_retention_days, 7.0, "seven days is the default")
		xtest.equal(conf.error, "", "an empty config is valid")

def test_a_source_entry_keeps_its_kind_id_and_options():
	with tempfile.TemporaryDirectory() as folder:
		conf = _config(folder, {"sources": [{"kind": "site", "interval_seconds": 30,
			"targets": [{"name": "a", "url": "https://a/"}]}]})
		source = conf.sources[0]
		xtest.equal(source["kind"], "site", "the kind is kept")
		xtest.equal(source["id"], "site", "the id defaults to the kind")
		xtest.equal(source["interval_seconds"], 30, "the kind's options are kept")

def test_two_instances_of_one_kind_can_coexist():
	with tempfile.TemporaryDirectory() as folder:
		conf = _config(folder, {"sources": [
			{"kind": "site", "id": "public", "targets": [{"name": "a"}]},
			{"kind": "site", "id": "private", "targets": [{"name": "b"}]}]})
		xtest.equal([source["id"] for source in conf.sources], ["public", "private"],
			"the ids distinguish the instances")

def test_duplicate_ids_are_a_config_error():
	with tempfile.TemporaryDirectory() as folder:
		conf = _config(folder, {"sources": [
			{"kind": "site", "targets": [{"name": "a"}]},
			{"kind": "site", "targets": [{"name": "b"}]}]})
		xtest.contains("unique", conf.error, "the duplicate id is named")

def test_sources_must_be_a_list():
	with tempfile.TemporaryDirectory() as folder:
		conf = _config(folder, {"sources": 5})
		xtest.contains("sources must be a list", conf.error, "the shape is named")

def test_a_source_must_be_an_object():
	with tempfile.TemporaryDirectory() as folder:
		conf = _config(folder, {"sources": ["site"]})
		xtest.contains("a source must be an object", conf.error, "the entry is named")

def test_a_source_needs_a_kind():
	with tempfile.TemporaryDirectory() as folder:
		conf = _config(folder, {"sources": [{"targets": []}]})
		xtest.contains("needs a kind", conf.error, "the missing kind is named")

def test_an_unknown_top_level_key_is_an_error():
	with tempfile.TemporaryDirectory() as folder:
		conf = _config(folder, {"sites": ["example.com"]})
		xtest.contains("unknown config key: sites", conf.error,
			"the old config shape is named instead of silently ignored")

def test_a_missing_config_is_an_error():
	with tempfile.TemporaryDirectory() as folder:
		conf = config.Config(os.path.join(folder, "absent.json"))
		xtest.contains("no config at", conf.error, "the missing file is named")
		xtest.equal(conf.sources, [], "no sources come from no config")

def test_malformed_json_is_an_error():
	with tempfile.TemporaryDirectory() as folder:
		path = os.path.join(folder, "config.json")
		with open(path, "w", encoding="utf-8") as file:
			file.write("not json")
		conf = config.Config(path)
		xtest.true(conf.error, "the parse failure is reported")

def test_the_state_path_and_retention_can_be_overridden():
	with tempfile.TemporaryDirectory() as folder:
		conf = _config(folder, {"state_path": os.path.join(folder, "state.json"),
			"news_retention_days": 2})
		xtest.equal(str(conf.state_path), os.path.join(folder, "state.json"),
			"the config's state path wins")
		xtest.equal(conf.news_retention_days, 2.0, "the retention is the config's")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
