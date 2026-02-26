#!/usr/bin/env python3
"""
Polls https://luma.com/seoul once and notifies new AI/crypto events to Telegram.
Designed to run once and exit (use cron / Render cron / scheduler to run periodically).

Config via environment variables:
- TELEGRAM_BOT_TOKEN (required)
- TELEGRAM_CHAT_ID (required) -- numeric chat id is recommended
- KEYWORDS (optional) comma-separated override (default includes ai,crypto,blockchain,web3,ml)

Outputs a seen_events.json file in the working directory to avoid duplicate notifications.
"""

import os
import sys
import json
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime

LUMA_URL = os.environ.get("LUMA_URL", "https://luma.com/seoul")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SEEN_FILE = os.environ.get("SEEN_FILE", "seen_events.json")

DEFAULT_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "ml",
    "crypto", "cryptocurrency", "blockchain", "web3", "defi"
]
KEYWORDS = [k.strip().lower() for k in os.environ.get("KEYWORDS", ",".join(DEFAULT_KEYWORDS)).split(",") if k.strip()]

if not BOT_TOKEN or not CHAT_ID:
    print("ERROR: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables must be set.")
    sys.exit(1)


def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            data = json.load(f)
            return set(data)
    except FileNotFoundError:
        return set()
    except Exception:
        return set()


def save_seen(s):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(s), f)


def send_telegram(text, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }
    r = requests.post(url, data=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_page(url):
    headers = {"User-Agent": "luma-notifier/1.0 (+https://github.com)"}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.text


def parse_events(html, base_url=LUMA_URL):
    soup = BeautifulSoup(html, "html.parser")
    events = []

    # 1) Try structured JSON-LD (Event objects)
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string)
        except Exception:
            continue
        # JSON-LD may be a list or dict
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get("@type", "").lower() == "event":
                title = item.get("name")
                url = item.get("url") or item.get("sameAs")
                start = item.get("startDate")
                location = ""
                loc = item.get("location")
                if isinstance(loc, dict):
                    location = loc.get("name") or loc.get("address", {}).get("addressLocality", "")
                events.append({"id": url or title + (start or ""), "title": title, "url": url, "date": start, "location": location, "raw": item})
    if events:
        return events

    # 2) Fallback: find event links/cards. Heuristic: <a href="/e/.."> or links containing '/events/' or '/e/'
    anchors = soup.find_all("a", href=True)
    seen_urls = set()
    for a in anchors:
        href = a["href"]
        if "/events/" in href or "/e/" in href or href.startswith("/events") or href.startswith("/e/"):
            full = urljoin(base_url, href)
            if full in seen_urls:
                continue
            seen_urls.add(full)
            # try to get title from anchor text or nearby heading
            title = a.get_text(strip=True)
            if not title:
                # look for an image alt or parent heading
                parent = a.find_parent()
                if parent:
                    h = parent.find(["h1", "h2", "h3", "h4", "h5"])
                    if h:
                        title = h.get_text(strip=True)
            # location/date: try to find siblings
            location = ""
            date = ""
            # search within the parent for small/date/location
            if parent:
                loc_el = parent.find(class_=lambda c: c and ("location" in c or "place" in c or "venue" in c))
                if loc_el:
                    location = loc_el.get_text(strip=True)
                date_el = parent.find(class_=lambda c: c and ("date" in c or "time" in c))
                if date_el:
                    date = date_el.get_text(strip=True)
            events.append({"id": full, "title": title, "url": full, "date": date, "location": location})

    # 3) If still empty, try headings that look like event titles (site often uses h3/h4 as list)
    if not events:
        for h in soup.find_all(["h2", "h3", "h4"]):
            txt = h.get_text(strip=True)
            if len(txt) < 5:
                continue
            # sibling link
            a = h.find("a") or h.find_parent().find("a") if h.find_parent() else None
            url = None
            if a and a.get("href"):
                url = urljoin(base_url, a.get("href"))
            events.append({"id": (url or txt), "title": txt, "url": url, "date": "", "location": ""})

    return events


def is_relevant(e):
    combined = " ".join([str(e.get("title", "")), str(e.get("location", "")), str(e.get("date", "")), json.dumps(e.get("raw", {})) if e.get("raw") else ""]).lower()
    # location filter: prefer events that include 'seoul' or 'korea' or korean script
    if not any(tok in combined for tok in ["seoul", "korea", "대한민국", "서울"]):
        return False
    return any(k in combined for k in KEYWORDS)


def format_message(e):
    title = e.get("title") or "(no title)"
    url = e.get("url") or LUMA_URL
    date = e.get("date") or ""
    location = e.get("location") or ""
    lines = [f"<b>{title}</b>"]
    if date:
        lines.append(date)
    if location:
        lines.append(location)
    lines.append(url)
    return "\n".join(lines)


def main():
    html = fetch_page(LUMA_URL)
    events = parse_events(html)
    seen = load_seen()
    new_ids = set(seen)
    to_notify = []

    for e in events:
        eid = str(e.get("id") or (e.get("url") or e.get("title")))
        if not eid:
            continue
        if eid in seen:
            continue
        if is_relevant(e):
            to_notify.append(e)
            new_ids.add(eid)

    if not to_notify:
        print("No new relevant events found.")
        save_seen(new_ids)
        return

    print(f"Found {len(to_notify)} new events; sending to Telegram...")
    for e in to_notify:
        msg = format_message(e)
        try:
            send_telegram(msg)
            time.sleep(0.5)
        except Exception as exc:
            print("Failed to send message for", e.get("title"), exc)

    save_seen(new_ids)


if __name__ == "__main__":
    main()
