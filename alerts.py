"""Work out which push alerts an update calls for, and send them through Firebase Cloud Messaging.

Usage:
  python3 alerts.py OLD_STATE.json NEW_STATE.json           # print the alerts only
  python3 alerts.py OLD_STATE.json NEW_STATE.json --send    # print and send them

Alerts:
  topic "alerts"     a field's status changes (delayed, rained out, closed, back on time),
                     or the director posts an announcement (weather, game management)
  topic "team-<id>"  a not-yet-played game for that team moves day, time or field, or is called off

Sending needs the environment variable FCM_SERVICE_ACCOUNT holding the Firebase service account
JSON. Never put that key in this repository; it is public.
"""
import base64, json, os, re, subprocess, sys, tempfile, time
import urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta

FS = {"ontime": "On time", "delayed": "Delayed", "rainout": "Rained out", "closed": "Closed"}
MAX_TEAM_ALERTS = 40  # a schedule rebuild should not flood phones
TITLE = "MN Prospects"


def team_topic(team_id):
    # must match teamTopic() in the app's notify.js
    return "team-" + re.sub(r"[^a-z0-9_.~-]", "-", str(team_id).lower())


def fmt_time(t):
    if not t:
        return "time TBD"
    h, m = (int(x) for x in t.split(":"))
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def fmt_day(d):
    return datetime.strptime(d, "%Y-%m-%d").strftime("%a %b %-d")


def field_line(name, x):
    label = FS.get(x.get("s"), "Updated")
    if x.get("s") == "delayed" and x.get("delay"):
        label += " " + x["delay"]
    line = f"{name}: {label}"
    return line + (f" ({x['note']})" if x.get("note") else "")


def field_alerts(old, new):
    o, n = old.get("fieldStatus") or {}, new.get("fieldStatus") or {}
    changed = []
    for name, x in n.items():
        if not x.get("s"):
            continue
        before = o.get(name) or {}
        if any(before.get(k) != x.get(k) for k in ("s", "delay", "note")):
            changed.append((name, x))
    if not changed:
        return []
    # worst news first
    order = {"rainout": 0, "closed": 1, "delayed": 2, "ontime": 3}
    changed.sort(key=lambda nx: order.get(nx[1].get("s"), 4))
    if all(x.get("s") == "ontime" for _, x in changed):
        title = "Fields back on time" if len(changed) > 1 else f"{changed[0][0]} back on time"
    else:
        bad = [nx for nx in changed if nx[1].get("s") != "ontime"]
        title = "Field update" if len(bad) > 1 else f"{bad[0][0]}: {field_line(*bad[0]).split(': ', 1)[1]}"
    body = "\n".join(field_line(nm, x) for nm, x in changed)
    return [{"topic": "alerts", "title": title, "body": body}]


def announcement_alerts(old, new):
    seen = {(a.get("ts"), a.get("text")) for a in old.get("announcements") or []}
    return [{"topic": "alerts", "title": TITLE, "body": a["text"]}
            for a in new.get("announcements") or []
            if (a.get("ts"), a.get("text")) not in seen and a.get("text")]


def game_alerts(old, new):
    names = {t["id"]: t["name"] for t in new.get("teams", [])}
    venues = {v["id"]: v["name"] for v in new.get("venues", [])}
    before = {g["id"]: g for g in old.get("games", [])}
    cutoff = (date.today() - timedelta(days=1)).isoformat()
    out = []
    for g in new.get("games", []):
        b = before.get(g["id"])
        if not b or not g.get("day") or g["day"] < cutoff or g.get("status") == "final":
            continue
        called_off = g.get("status") == "np" and b.get("status") != "np"
        moved = any(b.get(k) != g.get(k) for k in ("day", "time", "venueId", "field"))
        if not (called_off or moved):
            continue
        home = names.get(g.get("home")) or g.get("homeLabel") or "TBD"
        away = names.get(g.get("away")) or g.get("awayLabel") or "TBD"
        where = " · ".join(x for x in (venues.get(g.get("venueId")), g.get("field")) if x)
        for team, opp in ((g.get("home"), away), (g.get("away"), home)):
            if not team or team not in names:
                continue
            if called_off:
                title, body = "Game called off", f"{names[team]} vs {opp}, {fmt_day(g['day'])} {fmt_time(g.get('time'))}"
            else:
                title = "Game rescheduled"
                body = f"{names[team]} vs {opp} is now {fmt_day(g['day'])} {fmt_time(g.get('time'))}"
                body += (f" · {where}" if where else "")
                if b.get("day") and (b.get("day"), b.get("time")) != (g["day"], g.get("time")):
                    body += f" (was {fmt_day(b['day'])} {fmt_time(b.get('time'))})"
            out.append({"topic": team_topic(team), "title": title, "body": body})
    return out[:MAX_TEAM_ALERTS]


def access_token(sa):
    now = int(time.time())
    b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d, separators=(",", ":")).encode()).rstrip(b"=")
    unsigned = b64({"alg": "RS256", "typ": "JWT"}) + b"." + b64({
        "iss": sa["client_email"], "scope": "https://www.googleapis.com/auth/firebase.messaging",
        "aud": "https://oauth2.googleapis.com/token", "iat": now, "exp": now + 3600})
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as f:
        f.write(sa["private_key"])
    try:
        sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", f.name], input=unsigned,
                             capture_output=True, check=True).stdout
    finally:
        os.unlink(f.name)
    jwt = (unsigned + b"." + base64.urlsafe_b64encode(sig).rstrip(b"=")).decode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": jwt}).encode())
    return json.load(urllib.request.urlopen(req, timeout=30))["access_token"]


def service_account():
    # the key file's JSON, either as-is or base64-encoded onto one line (easier to paste into settings)
    raw = os.environ["FCM_SERVICE_ACCOUNT"].strip()
    return json.loads(raw if raw.startswith("{") else base64.b64decode(raw))


def send(alerts):
    sa = service_account()
    token = access_token(sa)
    url = f"https://fcm.googleapis.com/v1/projects/{sa['project_id']}/messages:send"
    failed = 0
    for a in alerts:
        msg = {"message": {"topic": a["topic"], "notification": {"title": a["title"], "body": a["body"]},
                           "apns": {"payload": {"aps": {"sound": "default"}}}}}
        req = urllib.request.Request(url, data=json.dumps(msg).encode(), headers={
            "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as e:
            failed += 1
            print(f"FAILED {a['topic']}: {e.code} {e.read().decode()[:300]}")
    return failed


def main():
    old, new = (json.load(open(p, encoding="utf8")) for p in sys.argv[1:3])
    alerts = field_alerts(old, new) + announcement_alerts(old, new) + game_alerts(old, new)
    for a in alerts:
        print(f"[{a['topic']}] {a['title']} — {a['body']}")
    if not alerts:
        print("No alerts")
    elif "--send" in sys.argv:
        if not os.environ.get("FCM_SERVICE_ACCOUNT"):
            sys.exit("FCM_SERVICE_ACCOUNT is not set; alerts were not sent.")
        failed = send(alerts)
        print(f"Sent {len(alerts) - failed} of {len(alerts)} alerts")
        sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
