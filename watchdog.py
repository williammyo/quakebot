import os
import json
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

STATUS_FILE = "status.json"
DISCORD_WEBHOOK = os.getenv("DISCORD_LOG_WEBHOOK")  # use same webhook
MENTION = "<@squishvocado>"
THRESHOLD_SECONDS = 90  # time since last update

def check_status():
    if not os.path.exists(STATUS_FILE):
        return False, "❌ status.json is missing!"

    with open(STATUS_FILE, "r") as f:
        data = json.load(f)
        last_time = datetime.fromisoformat(data["time"])
        now = datetime.utcnow()
        delta = (now - last_time).total_seconds()

        if delta > THRESHOLD_SECONDS:
            return False, f"⚠️ {MENTION} QuakeBot may be frozen. Last check-in: `{data['time']}` UTC ({int(delta)}s ago)"
        return True, ""

def send_alert(message):
    if not DISCORD_WEBHOOK:
        print("DISCORD_LOG_WEBHOOK is not set.")
        return
    requests.post(DISCORD_WEBHOOK, json={"content": message})

if __name__ == "__main__":
    ok, message = check_status()
    if not ok:
        send_alert(message)
