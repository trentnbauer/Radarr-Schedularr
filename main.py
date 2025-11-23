import requests
import sys
import os
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# --- CONFIGURATION ---
RADARR_URL = os.environ.get("RADARR_URL")
API_KEY = os.environ.get("RADARR_API_KEY")
LIST_NAME = os.environ.get("LIST_NAME")
START_DATE = os.environ.get("START_DATE") 
END_DATE = os.environ.get("END_DATE")

if not all([RADARR_URL, API_KEY, LIST_NAME, START_DATE, END_DATE]):
    print("Error: Missing config.")
    sys.exit(1)

def run_heartbeat():
    with open("/tmp/healthy", "w") as f:
        f.write(str(time.time()))

def get_list_id(url, headers):
    try:
        res = requests.get(f"{url}/api/v3/importlist", headers=headers)
        res.raise_for_status()
        target = next((i for i in res.json() if i['name'].lower() == LIST_NAME.lower()), None)
        if not target:
            print(f"❌ Error: List '{LIST_NAME}' not found.")
            return None
        return target
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None

def set_list_state(enable_state):
    action = "ENABLING" if enable_state else "DISABLING"
    url = RADARR_URL.rstrip("/")
    headers = {"X-Api-Key": API_KEY}
    
    target = get_list_id(url, headers)
    if not target: return

    if target['enabled'] == enable_state:
        # Only print if we are actually changing something to keep logs clean
        # or print a debug message
        # print(f"ℹ️ Verified: List is correctly {action}.")
        return

    print(f"⚙️ State Mismatch detected! Fixing... {action} list '{LIST_NAME}'...")
    target['enabled'] = enable_state
    try:
        put_url = f"{url}/api/v3/importlist/{target['id']}"
        requests.put(put_url, json=target, headers=headers).raise_for_status()
        print(f"✅ Success! List is now {action}.")
    except Exception as e:
        print(f"❌ Update Failed: {e}")

def check_season_status():
    now = datetime.now()
    current_year = now.year
    d_start = datetime.strptime(f"{current_year}-{START_DATE}", "%Y-%m-%d")
    d_end = datetime.strptime(f"{current_year}-{END_DATE}", "%Y-%m-%d")

    if d_start > d_end: # Over New Year
        if now < d_start and now > d_end: return False
        return True
    else: # Standard Year
        return d_start <= now <= d_end

# Wrapper for the scheduler to run the check
def daily_enforcement():
    print("☀️ Daily Check: Verifying list state matches the date...")
    should_be_active = check_season_status()
    set_list_state(should_be_active)

if __name__ == "__main__":
    print("🚀 Container Starting...")
    
    # 1. IMMEDIATE CHECK
    daily_enforcement()

    # 2. SCHEDULE
    scheduler = BlockingScheduler()
    scheduler.add_job(run_heartbeat, 'interval', minutes=1)

    # 3. DAILY ENFORCEMENT (Run every day at 08:00 AM)
    # This replaces the specific date triggers with a daily loop
    scheduler.add_job(daily_enforcement, CronTrigger(hour=8, minute=0))
    print(f"⏰ Scheduled: Daily verification at 08:00 AM.")
    
    try:
        run_heartbeat()
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
