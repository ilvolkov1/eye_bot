# bot.py
import asyncio
import itertools
import os
from contextlib import asynccontextmanager
from datetime import datetime, time

import pytz
import uvicorn
from fastapi import FastAPI
from telegram import Bot, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ----------------------------------------------------------------------
# 1. CONFIG
# ----------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set in Render env")

# ----------------------------------------------------------------------
# 2. REMINDER SETTINGS
# ----------------------------------------------------------------------
TZ = pytz.timezone("Asia/Nicosia")
REMINDER_INTERVAL = 20 * 60  # 20 min
WORKDAYS = range(5)  # Mon-Fri
START_HOUR, END_HOUR = 9, 18

MESSAGES = [
    "20-20-20 rule! Look 20 ft for 20 sec 👀⏱️",
    "Blink now and relax your eyes 😊",
    "Time to look away from the screen 🖥️➡️🌳",
    "Roll your shoulders and rest your eyes 💆‍♂️",
    "Focus far, give your eyes a mini-vacation 🏖️",
    "Close eyes for 10 seconds, breathe deeply 😌",
    "Adjust posture and let your eyes refocus 🪑👀",
    "Look at something green to reduce strain 🌿",
    "Remember to blink more and relax 😴👁️",
    "Hydrate and rest your eyes 💧👁️",
]
msg_cycle = itertools.cycle(MESSAGES)

# ----------------------------------------------------------------------
# 3. IN-MEMORY SUBSCRIBERS
# ----------------------------------------------------------------------
subscribers: set[int] = set()  # user_id → int


# ----------------------------------------------------------------------
# 4. BOT COMMANDS
# ----------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    subscribers.add(user.id)

    await update.message.reply_text(
        "Eye-rest reminders ON!\n"
        "Every 20 min (Mon-Fri 09:00-18:00, Cyprus time)\n\n"
        "Send /stop to unsubscribe.",
        reply_markup=ReplyKeyboardMarkup([["/stop"]], resize_keyboard=True),
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    subscribers.discard(user.id)

    await update.message.reply_text(
        "Reminders stopped.\nSend /start to turn them back on.",
        reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True),
    )


# ----------------------------------------------------------------------
# 5. REMINDER LOOP
# ----------------------------------------------------------------------
async def reminder_loop(bot: Bot):
    while True:
        now = datetime.now(TZ)
        if (
            now.weekday() in WORKDAYS
            and time(START_HOUR) <= now.time() <= time(END_HOUR)
            and not (time(13, 0) <= now.time() < time(14, 0))
        ):
            text = next(msg_cycle)
            for uid in list(subscribers):  # copy to avoid mutation
                try:
                    await bot.send_message(chat_id=uid, text=text)
                except Exception as e:  # blocked / deleted user
                    print(f"Failed to send to {uid}: {e}")
                    subscribers.discard(uid)

        await asyncio.sleep(REMINDER_INTERVAL)


# ----------------------------------------------------------------------
# 6. FASTAPI + LIFESPAN
# ----------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- bot polling -------------------------------------------------
    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("stop", stop))

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()

    # ---- reminder task -----------------------------------------------
    asyncio.create_task(reminder_loop(tg_app.bot))

    print("Bot + reminders running")
    yield

    # ---- shutdown ----------------------------------------------------
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()


app = FastAPI(lifespan=lifespan)


@app.get("/")
@app.head("/")
async def health():
    return {
        "status": "alive",
        "subscribers": len(subscribers),
        "next_reminder": "≤20 min (Mon-Fri 09:00-18:00)",
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("stop", stop))

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(
        drop_pending_updates=True,  # ← Skip old messages
    )

    # Reminder task
    asyncio.create_task(reminder_loop(tg_app.bot))

    print("Bot started - polling active")
    yield

    # Shutdown
    print("Shutting down bot...")
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()
