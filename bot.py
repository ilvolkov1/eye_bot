# bot.py
import asyncio
import itertools
import os
import random
from contextlib import asynccontextmanager
from datetime import datetime, time

import pytz
from fastapi import FastAPI
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

import db

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
MIN_REMINDER_INTERVAL = 20 * 60  # 20 min
MAX_REMINDER_INTERVAL = 30 * 60  # 30 min
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
skip_counts: dict[int, int] = {}  # user_id -> remaining skips


# ----------------------------------------------------------------------
# 4. BOT COMMANDS
# ----------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    subscribers.add(user.id)
    await db.add_or_activate_user(user.id)

    await update.message.reply_text(
        "Eye-rest reminders ON!\n"
        "Every 20–30 min (Mon-Fri 09:00-18:00, Cyprus time)\n\n"
        "Send /stop to unsubscribe.",
        reply_markup=ReplyKeyboardMarkup([["/stop"]], resize_keyboard=True),
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    subscribers.discard(user.id)
    skip_counts.pop(user.id, None)
    await db.deactivate_user(user.id)

    await update.message.reply_text(
        "Reminders stopped.\nSend /start to turn them back on.",
        reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True),
    )


async def skip_next_three(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    uid = query.from_user.id
    skip_counts[uid] = skip_counts.get(uid, 0) + 3

    await query.answer("OK — I will skip your next 3 reminders.")
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass


# ----------------------------------------------------------------------
# 5. REMINDER LOOP
# ----------------------------------------------------------------------
async def reminder_loop(bot: Bot):
    while True:
        now = datetime.now(TZ)
        in_active_window = (
            now.weekday() in WORKDAYS
            and time(START_HOUR) <= now.time() <= time(END_HOUR)
            and not (time(13, 0) <= now.time() < time(14, 0))
        )

        if in_active_window:
            text = next(msg_cycle)
            for uid in list(subscribers):  # copy to avoid mutation
                try:
                    remaining = skip_counts.get(uid, 0)
                    if remaining > 0:
                        remaining -= 1
                        if remaining <= 0:
                            skip_counts.pop(uid, None)
                        else:
                            skip_counts[uid] = remaining
                        continue

                    await bot.send_message(
                        chat_id=uid,
                        text=text,
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton("Skip next 3 reminders", callback_data="skip:3")]]
                        ),
                    )
                except Exception as e:  # blocked / deleted user
                    print(f"Failed to send to {uid}: {e}")
                    await db.deactivate_user(uid)
                    subscribers.discard(uid)
                    skip_counts.pop(uid, None)

            await asyncio.sleep(random.randint(MIN_REMINDER_INTERVAL, MAX_REMINDER_INTERVAL))
        else:
            await asyncio.sleep(60)


# ----------------------------------------------------------------------
# 6. FASTAPI + LIFESPAN
# ----------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- bot polling -------------------------------------------------
    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("stop", stop))
    tg_app.add_handler(CallbackQueryHandler(skip_next_three, pattern=r"^skip:3$"))
    await db.init_db()
    existing = await db.fetch_active_users()
    subscribers.update(existing)

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )

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
    # Get all users from database
    try:
        users_data = await db.get_all_users()
    except Exception as e:
        users_data = f"Database error: {e}"

    return {
        "status": "alive",
        "subscribers": len(subscribers),
        "next_reminder": "20–30 min (Mon-Fri 09:00-18:00)",
        "users_in_db": users_data,
    }
