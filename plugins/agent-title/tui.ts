// Names a session after the window it belongs to.
//
// A window is created by `oc-agent` with its own name (`secretary-2`), and the
// session it opens carries that title. A `/new` creates a fresh session with
// no title; this puts the window's name on it, from `OPENCODE_AGENT_NAME`,
// which the launcher exports. A session started outside the launcher has no
// window name, and falls back to the agent's own name.
//
// It runs in the TUI, not in the server, because the TUI is the only part
// that knows both halves: `process.env` here is the window's environment (the
// shared service has one environment for the whole machine, so a server
// plugin can only ever see the agent), and the router says which session this
// window is showing.
//
// The route is polled because opencode exposes no route-change event, and
// because between a `/new` and the first message the route is `home` — there
// is no session to name yet. So the rename lands the moment the window is
// showing the new session, which is the same moment the old server-side
// plugin renamed it, and the guard is unchanged: only a session whose title
// is still a default one is renamed, so a title a person set is never fought.
import { writeFileSync } from "node:fs"
import { Plugin } from "@opencode/plugin/tui"

const MARKER = "/tmp/opencode/agent-title-loaded.marker"
const SKIP_AGENTS = new Set(["build", "general", "explore", "compaction", "summary", "title", "plan", "directories"])
const WORKER_PREFIX = "worker-"
const DEFAULT_TITLE_RE = /^(New session|Child session)( - \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)?$/

function windowName() {
	const name = process.env.OPENCODE_AGENT_NAME
	return typeof name === "string" && name.trim() ? name.trim() : ""
}

function isDefaultTitle(title) {
	if (!title) return true
	return DEFAULT_TITLE_RE.test(title)
}

function shouldSkip(agent) {
	if (!agent) return true
	if (SKIP_AGENTS.has(agent)) return true
	return agent.startsWith(WORKER_PREFIX)
}

export default Plugin.define({
	id: "agent-title",
	setup(context) {
		const window = windowName()
		const named = new Set()

		const name = (sessionID) => {
			if (named.has(sessionID)) return
			const session = context.data.session.get(sessionID)
			if (!session) return
			const agent = session.agent ?? ""
			if (shouldSkip(agent)) return
			if (!isDefaultTitle(session.title)) return
			const wanted = window || agent
			named.add(sessionID)
			Promise.resolve(context.client.session.update({ sessionID, title: wanted }))
				.catch(() => named.delete(sessionID))
		}

		const report = () => {
			try {
				const route = context.ui.router.current()
				if (route?.type === "session") name(route.sessionID)
			} catch {}
		}

		// A plain filesystem write, not an RPC, so it is safe at setup time.
		// It proves the TUI entrypoint loaded, which is the failure mode that
		// looks like a working plugin: a bad export is silently ignored. The
		// window name goes in it, so the file also proves the TUI can see the
		// launcher's environment — a server-side copy would show nothing.
		try {
			writeFileSync(MARKER, window ? `tui ${window}` : "tui")
		} catch {}

		report()
		const timer = setInterval(report, 1000)
		return () => clearInterval(timer)
	},
})
