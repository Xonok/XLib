// Reports which opencode instance this process is, and which session it is on.
//
// WHY (2026-10-21). The shared opencode service knows every session but not
// which client process owns one: `/api/session/active` is "the sessions owned
// by this OpenCode process" — the *service* — the session table carries no
// pid, and `session.viewed` carries no client either. So when a window does
// `/new`, the new session is unattributable from outside, and marduk shows
// the window twice: the dead session the registry still names, and the live
// one it cannot place.
//
// The one party that knows is the opencode process itself. This file runs
// inside the TUI — `process.pid` here is the instance's pid, and
// `ctx.ui.router.current()` is the session the window is on. So the instance
// reports itself, keyed by its own pid, and the process is the identity: not
// the kitty window, and not the session.
//
// THE CONTRACT. One file per process, `~/.opencode/instances/<pid>.json`:
//
//   {"pid": 10116, "cwd": "/srv/agents",
//    "sessionID": "ses_ea53c242…", "at": 1792560442000}
//
// `sessionID` is null while the window is on no session — which is the
// honest answer between a `/new` and the first message of the new one, and a
// state the panel has to be able to show rather than paper over.
//
// marduk reads this directory; see tools/marduk/_/instance.py for the reader
// and tools/marduk/_/session_watcher.py for the join.
//
// The file is written atomically (temp file, then rename) because marduk
// reads it from another process and a half-written file would read as a
// window with no session.
import { mkdirSync, renameSync, rmSync, writeFileSync } from "node:fs"
import { homedir } from "node:os"
import { join } from "node:path"
import { Plugin } from "@opencode/plugin/tui"

const DIR = join(homedir(), ".opencode", "instances")

export default Plugin.define({
	id: "instance-report",
	setup(ctx: any) {
		let last = ""
		const report = () => {
			try {
				const route = ctx.ui.router.current()
				const sessionID = route?.type === "session" ? route.sessionID : null
				// The state, not the whole file: `at` changes every second, and
				// the file is written when the state changes, not every tick.
				const state = JSON.stringify({ sessionID, cwd: process.cwd() })
				if (state === last) return
				last = state
				const body = JSON.stringify({
					pid: process.pid,
					cwd: process.cwd(),
					sessionID,
					at: Date.now(),
				})
				mkdirSync(DIR, { recursive: true })
				const target = join(DIR, `${process.pid}.json`)
				const temp = `${target}.${process.pid}.tmp`
				writeFileSync(temp, body)
				renameSync(temp, target)
			} catch {}
		}
		report()
		const timer = setInterval(report, 1000)
		return () => {
			clearInterval(timer)
			try {
				rmSync(join(DIR, `${process.pid}.json`), { force: true })
			} catch {}
		}
	},
})
