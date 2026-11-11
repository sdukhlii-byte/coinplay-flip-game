import asyncio
import logging
import os
import random
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import Forbidden, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

import db

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("coinflip-bot")

SIDES = {"heads": "🦅 Heads", "tails": "🪙 Tails"}

TZ = ZoneInfo(os.getenv("TIMEZONE", "UTC"))
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "18"))


def today() -> datetime.date:
    return datetime.now(TZ).date()


def pick_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(SIDES["heads"], callback_data="pick:heads"),
                InlineKeyboardButton(SIDES["tails"], callback_data="pick:tails"),
            ],
            [InlineKeyboardButton("📊 My stats", callback_data="stats")],
        ]
    )


def after_game_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔁 Play again", callback_data="again")],
            [InlineKeyboardButton("📊 My stats", callback_data="stats")],
        ]
    )


def stats_text(user: dict) -> str:
    total = user["wins"] + user["losses"]
    rate = (user["wins"] / total * 100) if total else 0
    reminders = "on" if user["reminders_on"] else "off"
    return (
        "📊 Your stats\n\n"
        f"Games played: {total}\n"
        f"Wins: {user['wins']}\n"
        f"Losses: {user['losses']}\n"
        f"Win rate: {rate:.0f}%\n"
        f"Current streak: {user['streak']}\n"
        f"Best streak: {user['best_streak']}\n"
        f"Days in a row: {user['day_streak']} 🔥\n\n"
        f"Daily reminder: {reminders} (change with /reminder)"
    )


def current_user(update: Update) -> dict:
    return db.get_user(update.effective_user.id, update.effective_chat.id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    current_user(update)  # registers the user so the daily reminder can reach them
    name = update.effective_user.first_name or "there"
    await update.message.reply_text(
        f"Hi, {name}! 👋\n\n"
        "Let's flip a coin. Call it in the air — heads or tails?\n\n"
        "Come back every day to keep your streak alive. "
        "I'll send you a friendly reminder (turn it off anytime with /reminder).",
        reply_markup=pick_keyboard(),
    )


async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    current_user(update)
    await update.message.reply_text("Heads or tails?", reply_markup=pick_keyboard())


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        stats_text(current_user(update)), reply_markup=after_game_keyboard()
    )


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    current_user(update)
    db.reset_stats(update.effective_user.id)
    await update.message.reply_text("Your stats have been reset. ✅")


async def reminder_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = current_user(update)
    arg = context.args[0].lower() if context.args else None

    if arg in ("on", "off"):
        db.set_reminders(user["user_id"], arg == "on")
        if arg == "on":
            await update.message.reply_text(
                f"Daily reminder is on. 🔔 I'll nudge you around {REMINDER_HOUR:02d}:00 "
                "if you haven't played yet that day."
            )
        else:
            await update.message.reply_text("Daily reminder is off. 🔕")
        return

    state = "on 🔔" if user["reminders_on"] else "off 🔕"
    await update.message.reply_text(
        f"Daily reminder is currently {state}.\n\n"
        "Use /reminder on or /reminder off to change it."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Commands:\n"
        "/start - start the game\n"
        "/play - flip a coin\n"
        "/stats - show your stats\n"
        "/reminder on|off - daily reminder\n"
        "/reset - reset your stats\n"
        "/help - show this message"
    )


def register_play_day(user: dict) -> str:
    """Update the days-in-a-row counter. Returns a message line on the first play of a day."""
    today_d = today()
    last = user["last_play_date"]

    if last == today_d.isoformat():
        return ""

    yesterday = (today_d - timedelta(days=1)).isoformat()
    user["day_streak"] = user["day_streak"] + 1 if last == yesterday else 1
    user["last_play_date"] = today_d.isoformat()

    n = user["day_streak"]
    if n == 1:
        return "🔥 Day 1 — the streak begins! Come back tomorrow."
    return f"🔥 {n} days in a row!"


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    user = db.get_user(query.from_user.id, query.message.chat.id)

    if data == "again":
        await query.edit_message_text("Heads or tails?", reply_markup=pick_keyboard())
        return

    if data == "stats":
        await query.edit_message_text(
            stats_text(user), reply_markup=after_game_keyboard()
        )
        return

    if data.startswith("pick:"):
        choice = data.split(":", 1)[1]
        result = random.choice(list(SIDES))

        if choice == result:
            user["wins"] += 1
            user["streak"] += 1
            user["best_streak"] = max(user["best_streak"], user["streak"])
            verdict = "🎉 Nice call!"
        else:
            user["losses"] += 1
            user["streak"] = 0
            verdict = "😄 Not this time!"

        day_line = register_play_day(user)
        db.save_game_state(user)

        text = (
            f"You chose: {SIDES[choice]}\n"
            f"The coin landed on: {SIDES[result]}\n\n"
            f"{verdict}\n"
            f"Streak: {user['streak']}"
        )
        if day_line:
            text += f"\n\n{day_line}"

        await query.edit_message_text(text, reply_markup=after_game_keyboard())


async def send_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    today_s = today().isoformat()
    users = db.users_to_remind(today_s)
    logger.info("Sending daily reminders to %d users", len(users))

    for u in users:
        text = "🪙 Your daily flip is ready!\n\nHeads or tails?"
        if u["day_streak"] > 0 and u["last_play_date"] == (
            today() - timedelta(days=1)
        ).isoformat():
            text = (
                f"🪙 Your daily flip is ready!\n\n"
                f"You're on a {u['day_streak']}-day streak 🔥 — keep it going!"
            )
        try:
            await context.bot.send_message(
                chat_id=u["chat_id"], text=text, reply_markup=pick_keyboard()
            )
            db.mark_reminded(u["user_id"], today_s)
        except Forbidden:
            # User blocked the bot — stop reminding them.
            db.set_reminders(u["user_id"], False)
        except TelegramError as e:
            logger.warning("Reminder to %s failed: %s", u["user_id"], e)
        await asyncio.sleep(0.05)  # stay well under Telegram's rate limits


def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("BOT_TOKEN is not set. Copy .env.example to .env and fill it in.")

    db.init_db()

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("reminder", reminder_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(on_button))

    app.job_queue.run_daily(
        send_reminders, time=time(hour=REMINDER_HOUR, minute=0, tzinfo=TZ)
    )

    logger.info("Bot is running (reminders at %02d:00 %s)...", REMINDER_HOUR, TZ.key)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
