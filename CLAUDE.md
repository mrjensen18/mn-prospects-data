# MN Prospects app data

`state.json` here is what every installed copy of the Minnesota Prospects iPhone app downloads when it opens
(from https://raw.githubusercontent.com/mrjensen18/mn-prospects-data/main/state.json, cached up to 5 minutes).

## "Sync the app"
When asked to sync or update the app:
1. Read the director page with the Artifact tool (`action: "read"`):
   https://claude.ai/artifact/ece4cf82-b6d7-47f1-ac7e-c2771db24b29
2. Run `python3 sync.py <the saved HTML path the read reports>`.
3. If `git diff --stat` shows a change to `state.json`:
   a. Save the previous version: `git show HEAD:state.json > /tmp/old-state.json`
   b. Commit `state.json` only ("Sync tournament data") and push to `main`.
   c. Run `python3 alerts.py /tmp/old-state.json state.json --send` if the `FCM_SERVICE_ACCOUNT`
      environment variable is set, otherwise without `--send`. It prints the alerts it found.
   If nothing changed, say the app is already up to date and send nothing.
4. Report the event/team/game counts sync.py printed, and the alerts (sent, or found but not sent).

Never hand-edit `state.json`, and never push one that sync.py rejected.

## Push alerts
`alerts.py` compares the previous and new `state.json` and sends Firebase Cloud Messaging alerts:
field status changes and new announcements to topic `alerts`; moved or called-off upcoming games to
`team-<team id>` (the app subscribes followers to that topic). The Firebase key lives only in the
`FCM_SERVICE_ACCOUNT` environment variable (the service account JSON, raw or base64-encoded);
this repository is public, so never commit it.
