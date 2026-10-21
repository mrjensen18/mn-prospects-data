"""Copy the tournament data out of a saved copy of the director page into state.json.

Usage: python3 sync.py <saved-page.html>
"""
import json, re, sys
from pathlib import Path

html = Path(sys.argv[1]).read_text(encoding="utf8")
m = re.search(r'<script type="application/json" id="state">(.*?)</script>', html, re.S)
if not m:
    sys.exit("No <script id=\"state\"> block found in that page.")
data = json.loads(m.group(1))
if not isinstance(data.get("events"), list) or not data["events"]:
    sys.exit("State block has no events; refusing to publish it.")
out = Path(__file__).with_name("state.json")
out.write_text(m.group(1), encoding="utf8")
print(f"Wrote {out.name}: {len(data['events'])} events, {len(data.get('teams', []))} teams, {len(data.get('games', []))} games")
