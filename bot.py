import os
import asyncio
from datetime import datetime, time
from telegram import Bot
from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
import random

# --- Config ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("Set BOT_TOKEN and CHAT_ID in Render environment variables!")

bot = Bot(token=BOT_TOKEN)

# --- Eye Rest Reminder Settings ---
REMINDER_INTERVAL = 20 * 60  # 20 minutes in seconds
WORKDAYS = range(5)          # 0–4 = Monday to Friday
START_HOUR = 9               # 9:00 AM
END_HOUR = 18                # 6:00 PM (18:00)
MESSAGES = [
    "20-20-20! Look far, rest easy!",
    "Eyes tired? 20 feet, 20 seconds — go!",
    "Blink break! Look out the window!",
    "Save your eyes — 20-20-20 now!",
]


# --- Async Reminder Loop ---
async def send_eye_reminders():
    print("Eye rest reminder task started...")
    while True:
        now = datetime.now()
        current_time = now.time()
        is_workday = now.weekday() in WORKDAYS
        is_work_hours = time(START_HOUR) <= current_time <= time(END_HOUR)

        if is_workday and is_work_hours:
            try:
                await bot.send_message(
                    chat_id=CHAT_ID,
                    text = random.choice(MESSAGES),
                    parse_mode="Markdown"
                )
                print(f"[{now.strftime('%H:%M')}] Eye rest reminder sent!")
            except Exception as e:
                print(f"Error sending reminder: {e}")

        # Wait until next 20-minute mark
        await asyncio.sleep(REMINDER_INTERVAL)

# --- FastAPI with Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start reminder task
    task = asyncio.create_task(send_eye_reminders())
    print("Bot is running. Eye reminders every 20 mins during work hours.")
    yield
    # Cleanup on shutdown
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

@app.get("/")
def health():
    return {
        "status": "alive",
        "reminders": "Every 20 min (Mon–Fri, 9AM–6PM)",
        "next": "Check Telegram!"
    }

@app.head("/")
async def head_health():
    return {"status": "ok"}

# --- Run ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

