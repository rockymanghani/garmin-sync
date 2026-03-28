"""
Garmin → Redis sync script
Run this once daily (or manually) from your PC.
It logs into Garmin from your home IP and pushes data to Upstash Redis
so the web app can display it.

Setup:
  pip install garminconnect requests
  Then run: python sync.py
"""

import json
import requests
from datetime import date, timedelta
from garminconnect import Garmin

# ── Config ──────────────────────────────────────────────────────────────
GARMIN_EMAIL    = "rockymanghani@gmail.com"
GARMIN_PASSWORD = "Rakesh2001!!"

# Upstash Redis — copy these from your Vercel env vars
REDIS_URL   = "https://upward-clam-84813.upstash.io"
REDIS_TOKEN = "gQAAAAAAAUtNAAIncDE2ZDA0NTMzNzAwZWM0OTZhODc0OGE3NmVhNzE1Nzc4Y3AxODQ4MTM"
# ────────────────────────────────────────────────────────────────────────

def redis_set(key, value, ex=86400):
    """Store value in Upstash Redis with TTL (default 24h)."""
    payload = [["SET", key, value, "EX", str(ex)]]
    r = requests.post(
        f"{REDIS_URL}/pipeline",
        headers={"Authorization": f"Bearer {REDIS_TOKEN}", "Content-Type": "application/json"},
        json=payload,
        timeout=10
    )
    r.raise_for_status()
    return r.json()

def fetch():
    print("Logging into Garmin Connect...")
    api = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
    api.login()
    print("✅ Logged in")

    today    = date.today()
    today_s  = today.isoformat()
    week_ago = (today - timedelta(days=6)).isoformat()

    data = {"date": today_s}

    # 7-day steps (for chart)
    try:
        data["daily_steps"] = api.get_daily_steps(week_ago, today_s)
        print(f"  Steps 7-day: ok")
    except Exception as e:
        data["daily_steps"] = []
        print(f"  Steps 7-day: {e}")

    # Today's step total
    try:
        steps_data = api.get_steps_data(today_s)
        data["steps_today"] = sum(x.get("steps", 0) for x in steps_data) if steps_data else 0
        print(f"  Steps today: {data['steps_today']}")
    except Exception as e:
        data["steps_today"] = 0
        print(f"  Steps today: {e}")

    # Sleep
    try:
        sleep = api.get_sleep_data(today_s)
        data["sleep_seconds"] = sleep.get("dailySleepDTO", {}).get("sleepTimeSeconds", 0)
        print(f"  Sleep: {data['sleep_seconds']}s")
    except Exception as e:
        data["sleep_seconds"] = 0
        print(f"  Sleep: {e}")

    # Resting HR
    try:
        hr = api.get_heart_rates(today_s)
        data["resting_hr"] = hr.get("restingHeartRate", 0)
        print(f"  HR: {data['resting_hr']} bpm")
    except Exception as e:
        data["resting_hr"] = 0
        print(f"  HR: {e}")

    # Body battery
    try:
        bb = api.get_body_battery(today_s, today_s)
        data["body_battery"] = bb[0].get("charged") if bb else None
        print(f"  Body battery: {data['body_battery']}")
    except Exception as e:
        data["body_battery"] = None
        print(f"  Body battery: {e}")

    return data

def main():
    if not REDIS_URL or not REDIS_TOKEN:
        print("❌ Fill in REDIS_URL and REDIS_TOKEN at the top of this file first.")
        return

    data = fetch()
    body = json.dumps(data)
    redis_set("garmin:data", body, ex=86400)  # 24h TTL
    print(f"\n✅ Pushed to Redis — {len(body)} bytes")

if __name__ == "__main__":
    main()
