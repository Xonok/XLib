"""The per-file claim commands are gone; check-clean and the role notes stay.

The ruling (human, 2026-10-21, epiq `5S8FY10`): **a worktree per ticket is
the boundary**, so the per-file claim mechanism is retired. `claim`, `release`,
`release-all` and `status` go. `check-clean` stays, because it reads the
*working tree* — so it needs no shared state, works in any checkout, and sees
across worktrees, while the claim system's key was the absolute path, which a
worktree changes without changing the file.

These tests pin that surface. A command that is documented as gone and still
answers is worse than one that was never there, and the audit found the whole
mechanism had been advisory since nothing checked it at commit time.
"""
import os,subprocess,sys

# xtest, found relative to this file rather than to the working directory: a
# path relative to the cwd only works from the repository root, and a test
# that runs from one directory and fails from another is worse than one that
# never runs.
sys.path.insert(0, os.path.join(
	os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
	"dev", "xtest"))
import xtest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOL = os.path.join(ROOT, "tools", "agent-coord.py")

def _run(*args):
	return subprocess.run([sys.executable, TOOL, *args],
		capture_output=True, text=True)

def test_claim_is_not_a_command():
	proc = _run("claim", "somefile.py")
	xtest.not_equal(proc.returncode, 0, "claim must not answer any more")
	xtest.contains("invalid choice", proc.stderr, "and it must say why")

def test_release_is_not_a_command():
	proc = _run("release", "somefile.py")
	xtest.not_equal(proc.returncode, 0, "release must not answer any more")
	xtest.contains("invalid choice", proc.stderr, "and it must say why")

def test_release_all_is_not_a_command():
	proc = _run("release-all")
	xtest.not_equal(proc.returncode, 0, "release-all must not answer any more")
	xtest.contains("invalid choice", proc.stderr, "and it must say why")

def test_status_is_not_a_command():
	proc = _run("status")
	xtest.not_equal(proc.returncode, 0, "status must not answer any more")
	xtest.contains("invalid choice", proc.stderr, "and it must say why")

def test_check_clean_still_answers():
	"""The one that stays: it reads the working tree, so it needs no shared state."""
	proc = _run("check-clean", "--help")
	xtest.equal(proc.returncode, 0, "check-clean is the guard that survives")
	xtest.contains("check-clean", proc.stdout, "and it is still in the command list")

def test_the_role_note_commands_stay():
	"""Role-note claims are a different thing, and the ticket keeps them."""
	for command in ("role-claim", "role-release", "role-status"):
		proc = _run(command, "--help")
		xtest.equal(proc.returncode, 0, f"{command} stays: it guards the role notes")

def test_the_tool_still_runs():
	proc = _run("--help")
	xtest.equal(proc.returncode, 0, "the tool starts")

if __name__ == "__main__":
	sys.exit(xtest.run(__file__))
