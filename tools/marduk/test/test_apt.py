"""The apt check: a fixed candidate is news, a missing one is a source error."""
import os,sys,tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
	os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(REPO, "dev", "xtest"))
sys.path.insert(0, REPO)

import xtest
from tools.marduk._ import event,store
from tools.marduk._.sources import apt,build

def _source(**options):
	options.setdefault("packages", [
		{"name": "linux-image", "fixed": "6.8.0-45"},
		{"name": "virt-manager", "fixed": "4.1.0-2"},
	])
	return apt.Apt("apt", options)

def _policy(values):
	def policy(name):
		return values[name]
	return policy

def _compare(result):
	def compare(candidate, fixed):
		return result
	return compare

def _raise(exc):
	def policy(name):
		raise exc
	return policy

def test_a_fixed_candidate_is_news():
	conditions = _source(packages=[{"name": "linux-image", "fixed": "6.8.0-45"}]).check(1000.0,
		_policy({"linux-image": "6.8.0-45"}), _compare(True))
	condition = conditions[0]
	xtest.equal(condition.state, event.STATE_INFO, "a fix is information")
	xtest.equal(condition.kind, "news", "a package state is not a health row")
	xtest.equal(condition.key, "apt:linux-image", "the key names the source and package")
	xtest.contains("can be fixed by apt upgrade", condition.title, "the title says what to do")
	xtest.contains("candidate 6.8.0-45", condition.detail, "the candidate is in the detail")
	xtest.contains("fix at 6.8.0-45", condition.detail, "the threshold is in the detail")

def test_a_candidate_below_the_fix_is_quiet():
	conditions = _source(packages=[{"name": "linux-image", "fixed": "6.8.0-45"}]).check(1000.0,
		_policy({"linux-image": "6.8.0-40"}), _compare(False))
	xtest.equal(conditions[0].state, event.STATE_OK, "a candidate below the fix is ok")
	xtest.contains("not fixed yet", conditions[0].title, "the title says it is not fixed")

def test_one_condition_per_package():
	conditions = _source().check(1000.0,
		_policy({"linux-image": "6.8.0-45", "virt-manager": "4.1.0-1"}), lambda candidate, fixed: True)
	xtest.equal([condition.key for condition in conditions], ["apt:linux-image", "apt:virt-manager"],
		"one condition per package, in config order")

def test_the_comparison_gets_the_candidate_and_the_fixed_version():
	seen = []
	def compare(candidate, fixed):
		seen.append((candidate, fixed))
		return True
	_source().check(1000.0,
		_policy({"linux-image": "6.8.0-45", "virt-manager": "4.1.0-2"}), compare)
	xtest.equal(seen, [("6.8.0-45", "6.8.0-45"), ("4.1.0-2", "4.1.0-2")],
		"the candidate and the package's own threshold reach the comparison")

def test_a_missing_candidate_is_a_source_error():
	raised = False
	try:
		_source(packages=[{"name": "linux-image", "fixed": "6.8.0-45"}]).check(1000.0,
			_policy({"linux-image": None}), _compare(True))
	except ValueError as exc:
		raised = "linux-image" in str(exc)
	xtest.true(raised, "a package with no candidate names itself in the error")

def test_a_failed_apt_call_is_a_source_error():
	raised = False
	try:
		_source(packages=[{"name": "linux-image", "fixed": "6.8.0-45"}]).check(1000.0,
			_raise(ValueError("apt-cache policy linux-image exited 100: boom")), _compare(True))
	except ValueError as exc:
		raised = "exited 100" in str(exc)
	xtest.true(raised, "the failed command is reported")

class Result:
	def __init__(self, returncode, stdout="", stderr=""):
		self.returncode = returncode
		self.stdout = stdout
		self.stderr = stderr

def test_the_candidate_is_read_from_apt_output():
	output = "bash:\n  Installed: 5.3-4\n  Candidate: 5.3-5\n  Version table:\n"
	xtest.equal(apt._candidate(output), "5.3-5", "the Candidate line is the version")

def test_a_missing_candidate_line_is_none():
	xtest.equal(apt._candidate("bash:\n  Installed: 5.3-4\n"), None,
		"a package with no candidate has no version")

def test_a_none_candidate_is_none():
	xtest.equal(apt._candidate("bash:\n  Candidate: (none)\n"), None,
		"apt's (none) is no version")

def test_the_policy_reads_the_candidate_from_the_command():
	def run(args, **kwargs):
		xtest.equal(args, ["apt-cache", "policy", "bash"], "the package is the argument")
		xtest.equal(kwargs["timeout"], 30, "the timeout is passed")
		return Result(0, stdout="bash:\n  Candidate: 5.3-5\n")
	xtest.equal(apt._policy(30, run)("bash"), "5.3-5", "the command's candidate is returned")

def test_a_failed_policy_command_names_the_package():
	def run(args, **kwargs):
		return Result(100, stderr="boom")
	raised = False
	try:
		apt._policy(30, run)("bash")
	except ValueError as exc:
		raised = "bash" in str(exc) and "boom" in str(exc)
	xtest.true(raised, "the package and the stderr are in the error")

def test_version_at_least_uses_dpkgs_return_code():
	def success(args, **kwargs):
		xtest.equal(args, ["dpkg", "--compare-versions", "2.0", "ge", "1.0"], "the versions are arguments")
		return Result(0)
	def less(args, **kwargs):
		return Result(1)
	xtest.true(apt.version_at_least("2.0", "1.0", success), "0 means the version is at least")
	xtest.true(not apt.version_at_least("1.0", "2.0", less), "1 means it is below")

def test_a_failed_comparison_is_an_error():
	def failure(args, **kwargs):
		return Result(2, stderr="bad version")
	raised = False
	try:
		apt.version_at_least("x", "y", failure)
	except ValueError as exc:
		raised = "bad version" in str(exc)
	xtest.true(raised, "dpkg's own error is reported")

def test_the_default_interval_is_an_hour():
	source = _source()
	xtest.equal(source.interval(), 3600.0, "the default interval is an hour")
	xtest.equal(source.stale_after(), 10800.0, "the stale threshold is three intervals")

def test_the_options_set_the_interval_and_stale_after():
	source = _source(interval_seconds=60.0, stale_after_seconds=90.0)
	xtest.equal(source.interval(), 60.0, "the interval is the option")
	xtest.equal(source.stale_after(), 90.0, "an explicit stale threshold wins")

def test_the_source_declares_no_health_rows():
	xtest.equal(_source().keys(), [], "package state is news only")

def test_the_condition_key_includes_the_source_id():
	conditions = apt.Apt("pkg", {"packages": [{"name": "linux-image", "fixed": "1"}]}).check(1000.0,
		_policy({"linux-image": "1"}), _compare(True))
	xtest.equal(conditions[0].key, "pkg:linux-image", "the id prefixes the key")

def test_packages_must_be_a_list():
	raised = False
	try:
		apt.Apt("apt", {"packages": 5})
	except ValueError:
		raised = True
	xtest.true(raised, "a malformed package list is a config error")

def test_a_package_needs_a_name_and_a_fixed_version():
	raised = False
	try:
		apt.Apt("apt", {"packages": [{"name": "linux-image"}]})
	except ValueError as exc:
		raised = "fixed version" in str(exc)
	xtest.true(raised, "a package without a threshold is a config error")

def test_a_package_must_be_an_object():
	raised = False
	try:
		apt.Apt("apt", {"packages": ["linux-image"]})
	except ValueError:
		raised = True
	xtest.true(raised, "a bare package name has no threshold")

def test_the_kind_is_registered():
	sources, notices = build([{"kind": "apt", "id": "apt", "packages": []}])
	xtest.equal(len(sources), 1, "the apt kind is built from config")
	xtest.equal(notices, [], "the known kind is not a notice")

def test_a_fix_that_was_absent_becomes_one_news_item():
	with tempfile.TemporaryDirectory() as folder:
		state = store.Store(os.path.join(folder, "state.json"))
		state.load()
		source = _source(packages=[{"name": "linux-image", "fixed": "2.0"}])
		state.apply("apt", source.check(1000.0, _policy({"linux-image": "1.0"}), _compare(False)), 1000.0)
		xtest.equal(len(state.news), 0, "a package below the fix is silent")
		state.apply("apt", source.check(1060.0, _policy({"linux-image": "2.0"}), _compare(True)), 1060.0)
		xtest.equal(len(state.news), 1, "reaching the fix is one news item")
		state.apply("apt", source.check(1120.0, _policy({"linux-image": "2.0"}), _compare(True)), 1120.0)
		xtest.equal(len(state.news), 1, "an unchanged fix adds nothing")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
