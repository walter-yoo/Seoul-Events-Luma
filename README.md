Luma  Telegram notifier

This small service polls https://luma.com/seoul and notifies new AI/crypto events to a Telegram chat.

What it does
- Fetches the Seoul events page
- Extracts events (tries JSON-LD first, falls back to scraping)
- Filters for AI/crypto-related keywords and Seoul/Korea location
- Dedupe using seen_events.json
- Sends messages to Telegram using your bot

Quick start (Option B: deploy to Render - recommended)
1) Create a Render free account (https://render.com) and create a new "Web Service" or "Cron Job". For persistent polling, use a Cron Job (recommended) or a Web Service with a scheduler.

2) Repository
- Upload these files to a git repo (or I can push for you if you give access): notify_luma.py, README.md

3) Environment variables (set these in Render's dashboard)
- TELEGRAM_BOT_TOKEN = your bot token (e.g., 12345:ABC...)
- TELEGRAM_CHAT_ID = your chat id (numeric). If you gave a username, replace with numeric ID.
- (optional) LUMA_URL = https://luma.com/seoul
- (optional) KEYWORDS = comma-separated keywords

4) Schedule
- If using Render Cron Job, schedule to run every 10 minutes or every 30 minutes depending on how chatty you want it to be.

Local testing
- To run locally:
  TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python3 notify_luma.py

Notes
- Keep your bot token secret
- I can deploy this for you on Render if you give me access (or you can add the repo and set env vars yourself)

If you want, I can:
- Deploy this to Render for you (I'll need access to your Render account or you can invite me) OR
- Deploy it to a small DigitalOcean droplet I create (cost ~ $5/mo; I'll need your approval)
- Improve parsing to use Luma's API if they provide one
- Add pre-event reminders (1 day, 1 hour)

Tell me which hosting provider you prefer and whether you want me to deploy. If Render, provide a Git repo (or I can create one here and deploy if you provide Render access).
