import os
import asyncio
import aiohttp
import time
from collections import defaultdict, deque

# ===============================
# ENV VARIABLES
# ===============================

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
ROBLOSECURITY = os.getenv("ROBLOSECURITY")
GROUP_ID = os.getenv("GROUP_ID")
ALERT_ROLE_ID = os.getenv("ALERT_ROLE_ID")

if not all([DISCORD_WEBHOOK_URL, ROBLOSECURITY, GROUP_ID, ALERT_ROLE_ID]):
    raise Exception("Missing required environment variables.")

HEADERS = {
    "Cookie": f".ROBLOSECURITY={ROBLOSECURITY}",
    "Content-Type": "application/json"
}

# ===============================
# CONFIG
# ===============================

CHECK_INTERVAL = 60  # seconds

THRESHOLDS = [
    (50, 900, "🚨🚨🚨 EXTREME MASS RANKING DETECTED 🚨🚨🚨"),
    (30, 600, "🚨🚨 MAJOR MASS RANKING DETECTED 🚨🚨"),
    (15, 300, "🚨 MASS RANKING DETECTED 🚨")
]

# ===============================
# DATA STORAGE
# ===============================

rank_activity = defaultdict(deque)
processed_log_ids = set()
MAX_PROCESSED_IDS = 1000  # Prevent memory leak

# ===============================
# FUNCTIONS
# ===============================

async def send_discord_alert(message):
    async with aiohttp.ClientSession() as session:
        payload = {
            "content": f"<@&{ALERT_ROLE_ID}> {message}"
        }
        await session.post(DISCORD_WEBHOOK_URL, json=payload)

async def check_audit_logs():
    global processed_log_ids

    url = f"https://groups.roblox.com/v1/groups/{GROUP_ID}/audit-log?limit=100"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            if response.status != 200:
                print("Failed to fetch audit logs:", response.status)
                return

            data = await response.json()

    logs = data.get("data", [])
    current_time = time.time()

    for log in logs:

        log_id = log.get("id")
        action_type = log.get("actionType")

        # Skip malformed logs safely
        if not log_id or not action_type:
            continue

        if log_id in processed_log_ids:
            continue

        processed_log_ids.add(log_id)

        # Prevent memory overflow
        if len(processed_log_ids) > MAX_PROCESSED_IDS:
            processed_log_ids = set(list(processed_log_ids)[-500:])

        # Only track rank actions
        if "Rank" not in action_type:
            continue

        actor_data = log.get("actor", {})
        user_data = actor_data.get("user", {})

        ranker = user_data.get("username")
        if not ranker:
            continue

        # Store timestamp
        rank_activity[ranker].append(current_time)

        # Clean old timestamps beyond 15 minutes
        while rank_activity[ranker] and current_time - rank_activity[ranker][0] > 900:
            rank_activity[ranker].popleft()

        # Check thresholds
        for count, window, alert_text in THRESHOLDS:

            recent_count = sum(
                1 for t in rank_activity[ranker]
                if current_time - t <= window
            )

            if recent_count >= count:

                await send_discord_alert(
                    f"{alert_text}\n\n"
                    f"Ranker: **{ranker}**\n"
                    f"Promotions in last {window//60} minutes: **{recent_count}**"
                )

                # Reset after alert to prevent spam
                rank_activity[ranker].clear()
                break

    print("Audit check complete.")

# ===============================
# MAIN LOOP
# ===============================

async def main():
    print("Mass Rank Detection Bot Running...")

    while True:
        try:
            await check_audit_logs()
        except Exception as e:
            print("Error:", e)

        await asyncio.sleep(CHECK_INTERVAL)

asyncio.run(main())
        await asyncio.sleep(CHECK_INTERVAL)

asyncio.run(main())
