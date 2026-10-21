# MN Prospects app data

Live tournament data for the Minnesota Prospects Baseball Tournaments iPhone app.

The app downloads `state.json` from
https://raw.githubusercontent.com/mrjensen18/mn-prospects-data/main/state.json
each time it opens. Replacing that file updates every phone without a new App Store release.

`state.json` is the `<script id="state">` block of the director page published in Claude.

To update it, publish the director page in Claude, then ask Claude (in a session with this repo) to "sync the app". See CLAUDE.md.
