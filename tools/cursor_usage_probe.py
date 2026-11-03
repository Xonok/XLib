#!/usr/bin/env python3
"""Record a Cursor usage snapshot for the dollar/percent calibration experiment.

Reads the Cursor access token from Cursor's own SQLite state (read-only) and
queries https://api2.cursor.sh/auth/usage-summary, then appends one JSON line
to ~/.local/share/skynet/cursor-usage.jsonl. The token is never printed or
written. Run it periodically (cron/systemd timer) to build the time series.
"""
import datetime,json,os,sqlite3,urllib.request

STATE_DB = os.path.expanduser("~/.config/Cursor/User/globalStorage/state.vscdb")
OUTPUT = os.path.expanduser("~/.local/share/skynet/cursor-usage.jsonl")
URL = "https://api2.cursor.sh/auth/usage-summary"
USER_AGENT = "cursor-usage-probe/1.0"

def read_token():
	conn = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True)
	try:
		rows = conn.execute(
			"SELECT value FROM ItemTable WHERE key = 'cursorAuth/accessToken'"
		).fetchall()
	finally:
		conn.close()
	if not rows:
		raise SystemExit("no Cursor access token found")
	value = rows[0][0]
	try:
		parsed = json.loads(value)
	except (TypeError, ValueError):
		parsed = value
	if isinstance(parsed, dict):
		for key in ("value", "accessToken", "token"):
			if key in parsed:
				parsed = parsed[key]
				break
	token = str(parsed).strip()
	if not token:
		raise SystemExit("empty Cursor access token")
	return token

def fetch_summary(token):
	request = urllib.request.Request(
		URL,
		headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
	)
	with urllib.request.urlopen(request, timeout=10) as response:
		return json.loads(response.read().decode("utf-8"))

def main():
	token = read_token()
	summary = fetch_summary(token)
	now = datetime.datetime.now().astimezone()
	record = {
		"timestamp": now.timestamp(),
		"iso": now.isoformat(),
		"billingCycleStart": summary.get("billingCycleStart"),
		"billingCycleEnd": summary.get("billingCycleEnd"),
		"membershipType": summary.get("membershipType"),
		"limitType": summary.get("limitType"),
		"isUnlimited": summary.get("isUnlimited"),
		"individual": summary.get("individualUsage", {}),
	}
	os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
	with open(OUTPUT, "a", encoding="utf-8") as handle:
		handle.write(json.dumps(record, sort_keys=True) + "\n")
	individual = record["individual"]
	plan = individual.get("plan", {}) if isinstance(individual, dict) else {}
	print(
		f"recorded {record['iso']}: "
		f"auto={plan.get('autoPercentUsed')}% "
		f"api={plan.get('apiPercentUsed')}% "
		f"total={plan.get('totalPercentUsed')}% "
		f"used={plan.get('used')}/{plan.get('limit')}"
	)

if __name__ == "__main__":
	main()
