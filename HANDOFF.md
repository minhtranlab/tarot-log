# Tarot Log: handoff notes

Personal tarot-draw web app for Minh (iPhone mostly, sometimes iPad/laptop). He uses Rider-Waite-Smith, keeps a Notion Tarot Log and "Sổ Tay Kinh Nghiệm" (78-card notebook). He writes casual mixed Vietnamese/English, wants short direct replies, and prefers Claude to pause for confirmation instead of assuming. Replies to him: mostly Vietnamese, brief.

## What exists (all live)
- **Site**: https://minhtranlab.github.io/tarot-log/ (this repo, public, GitHub Pages from `main` root). Single static `index.html` + `cards/*.jpg` (78 RWS scans) + icons + `manifest.webmanifest`. Title and home-screen name "Tarot Log", gold eight-point star icon.
- **History storage**: a Google Sheet through an Apps Script web app (tab `Log`, plus a `README` tab). The web app address and passcode are NOT in this repo (public). Minh has them; his private handoff copy has them. Each device connects once via a setup link `SITE#u=<urlencoded web app url>&t=<passcode>` (the fragment never reaches a server) or by pasting that link into History > "Google Sheet connection". Home-screen web apps on iOS have their own storage, so they need the link pasted once too.
- **Legacy**: Claude artifact "Pocket Tarot" (claude.ai/artifact/VQQzMFvCY1pmsZejDJzYCW, v8). Same app but history lived in the artifact `db`, which Minh found reset. Superseded by the site; leave it.

## App features
Modes: **Draw for me** and **I drew by hand** (pick cards manually from a searchable 78-card picker with upright/reversed, + Jumper, + Extra slots, Save). Spreads: Compare options (N options × M cards, default 3×3, named options), single card, Past/Present/Future, Situation/Challenge/Advice, Horseshoe (7), Celtic Cross (10, true cross layout, card 2 rotated). Reversed toggle. Jumpers: 10% one, 1% two, 0.1% three extra cards per option/spread. Exact uniform draw (crypto rejection sampling, Fisher-Yates, no repeats across the whole table). Animated dealing from a deck pile, tap a card to zoom, tap again to flip: back shows EN + VI keywords, VI image description, VI "why this picture means that". "+ Card" clarifier button. Question field (included in Copy). History: 20 at a time, Show 20 more / Show all, notes ("what happened"), Open, Copy, Delete (tap twice), Sync now. Copy output for Notion/chat.

## How history sync works (index.html, `store` object)
- Writes go to a localStorage **outbox** (`tarotOutbox`) and are flushed one at a time to the Apps Script web app (POST text/plain JSON, no preflight). Device cache in `pocketTarotHistory`; connection in `tarotCfg`.
- A draw is saved immediately when dealt (put), later changes are patches (extras, option names, notes while typing with a debounce). Question edits after a draw do NOT overwrite that draw in draw mode (they belong to the next draw); in hand mode Save re-saves.
- Apps Script API: `GET ?action=list&offset&limit&token` -> `{ok, items, total}` newest first; `POST {token, action: put|patch|del, ...}`. Row columns: id, ts, date, spread, question, reading (readable text), note, manual, json. Text columns are forced to plain text so "=..." in a question is not a formula.
- Bug already fixed (Oct 2026): flush() raced and dropped queued writes; fixed by re-reading the outbox every step and storing the in-flight promise correctly. Test: `src/test_sync.py` (mock Sheet server in Playwright).

## Repo layout and how to ship a change
- `src/template7.html` is the source of truth for the page; `src/cards.json` holds all 78 cards' EN/VI text; `src/build_site.py` writes `index.html` (run `python3 -I src/build_site.py` from the repo root). **Never edit index.html by hand.**
- Edit the template with Python string replacement or the Edit tool (Read first). Check JS syntax: extract the `<script>` and run `node --check`. Test with Playwright (headless Chromium is installed; set viewport 390x844). Then commit and push to `main`.
- Git in a Claude cloud session: the `gh` token is invalid, so call the `add_repo` tool for minhtranlab/tarot-log with push access, clone once (shallow), commit, push. Commit messages end with the attribution lines the session gives you.
- Do not commit the Apps Script (`apps-script.gs`) or any passcode: the repo is public.

## State at handoff and open items
1. Minh was told to paste an updated `apps-script.gs` (adds a README tab with the setup link) into his Sheet's Apps Script, redeploy (Deploy > Manage deployments > pencil > New version) and run `setupReadme` once. **Not confirmed done.** Ask him.
2. Not yet confirmed: that "Add to Home Screen" on the new site shows the name "Tarot Log" and the star icon (the claude.ai artifact version could not set them).
3. The sandbox cannot reach script.google.com (HTTP 403 from the egress proxy), so the Sheet integration has only been tested against a mock. Real-world checks come from Minh (rows in the Log tab, History "Saved to your Google Sheet").
4. Repo is public by Minh's choice (GitHub Pages needs a paid plan for private repos). Card images are US Games 1971 scans with a © mark: personal use only, he accepted this. His records are safe because they live in his Sheet behind the passcode.
5. Deferred by Minh (do not start unprompted): offline PWA/service worker, personal card meanings from his Sổ Tay Kinh Nghiệm, auto-logging draws into his Notion Tarot Log.
6. If the passcode ever changes: edit TOKEN in the script, redeploy, run setupReadme, reconnect every device with the new link.
