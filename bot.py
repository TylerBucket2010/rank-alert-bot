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

        # Safe extraction
        log_id = log.get("id")
        action_type = log.get("actionType", "")

        if not log_id:
            continue

        if log_id in processed_log_ids:
            continue

        processed_log_ids.add(log_id)

        # Catch any rank-related action
        if "Rank" not in action_type:
            continue

        actor = log.get("actor", {})
        user_data = actor.get("user", {})
        ranker = user_data.get("username", "Unknown")

        print(f"Detected rank action by {ranker}")

        # Store timestamp
        rank_activity[ranker].append(current_time)

        # Clean timestamps older than 15 minutes (max window)
        while rank_activity[ranker] and current_time - rank_activity[ranker][0] > 900:
            rank_activity[ranker].popleft()

        # Check thresholds
        for count, window, alert_text in THRESHOLDS:
            recent = [t for t in rank_activity[ranker] if current_time - t <= window]

            if len(recent) >= count:
                await send_discord_alert(
                    f"{alert_text}\n\n"
                    f"Ranker: **{ranker}**\n"
                    f"Promotions in last {window//60} minutes: **{len(recent)}**"
                )

                print(f"ALERT triggered for {ranker}")

                # Clear to prevent repeat spam
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


if __name__ == "__main__":
    asyncio.run(main())
