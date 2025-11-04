import os
import asyncio
from datetime import datetime, time
from telegram import Bot
from fastapi import FastAPI
import uvicorn

# --- Telegram setup ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
bot = Bot(token=BOT_TOKEN)

# --- Reminder settings ---
START_HOUR = 0    # For testing, allow all hours
END_HOUR = 23
WORKDAYS = range(0, 7)  # All days for testing
REMINDER_INTERVAL = 60  # 1 minute

# --- FastAPI setup ---
app = FastAPI()

@app.get("/")
def healthcheck():
    return {"status": "running"}

# --- Async reminder task ---
async def send_reminders():
    while True:
        now = datetime.now()
        if now.weekday() in WORKDAYS and time(START_HOUR) <= now.time() <= time(END_HOUR):
            try:
                # Properly wrap synchronous send_message
                await asyncio.to_thread(
                    bot.send_message,
                    chat_id=CHAT_ID,
                    text=f"👀 Test reminder at {now.strftime('%H:%M:%S')}"
                )
                print(f"[{now}] Reminder sent successfully.")
            except Exception as e:
                print(f"[{now}] Error sending message: {e}")
        await asyncio.sleep(REMINDER_INTERVAL)

# --- Start reminder task on FastAPI startup ---
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(send_reminders())

# --- Entrypoint ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
