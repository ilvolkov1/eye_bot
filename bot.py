import os
import asyncio
from datetime import datetime, time
from telegram import Bot
from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn

# --- Telegram setup ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("BOT_TOKEN and CHAT_ID must be set in environment variables")

bot = Bot(token=BOT_TOKEN)

# --- Reminder settings ---
START_HOUR = 0
END_HOUR = 23
WORKDAYS = range(0, 7)
REMINDER_INTERVAL = 60  # seconds

# --- Async reminder task ---
async def send_reminders():
    while True:
        now = datetime.now()
        if now.weekday() in WORKDAYS and time(START_HOUR) <= now.time() <= time(END_HOUR):
            try:
                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=f"Test reminder at {now.strftime('%H:%M:%S')}"
                )
                print(f"[{now}] Reminder sent successfully.")
            except Exception as e:
                print(f"[{now}] Error sending message: {e}")
        await asyncio.sleep(REMINDER_INTERVAL)

# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting reminder task...")
    task = asyncio.create_task(send_reminders())
    yield
    print("Shutting down...")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

@app.get("/")
def healthcheck():
    return {"status": "running"}

# --- Entrypoint ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
