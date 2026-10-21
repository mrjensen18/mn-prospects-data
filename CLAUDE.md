# MN Prospects app data

`state.json` here is what every installed copy of the Minnesota Prospects iPhone app downloads when it opens
(from https://raw.githubusercontent.com/mrjensen18/mn-prospects-data/main/state.json, cached up to 5 minutes).

## "Sync the app"
When asked to sync or update the app:
1. Read the director page with the Artifact tool (`action: "read"`):
   https://claude.ai/artifact/ece4cf82-b6d7-47f1-ac7e-c2771db24b29
2. Run `python3 sync.py <the saved HTML path the read reports>`.
3. If `git diff --stat` shows a change to `state.json`, commit it ("Sync tournament data") and push to `main`.
   If nothing changed, say the app is already up to date.
4. Report the event/team/game counts sync.py printed.

Never hand-edit `state.json`, and never push one that sync.py rejected.
