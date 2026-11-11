# CoinPlay — Coin Flip Telegram Bot

A quick heads-or-tails game with a daily streak and a friendly daily reminder. The bot speaks English.

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in `BOT_TOKEN` (and, if you like, `REMINDER_HOUR` / `TIMEZONE`).
4. Run:
   ```
   python bot.py
   ```

## Commands

- `/start` - start the game
- `/play` - flip a coin
- `/stats` - show your stats
- `/reminder on|off` - turn the daily reminder on or off
- `/reset` - reset your stats
- `/help` - list commands

## How the daily reminder works

- Every user who pressed `/start` gets one reminder per day at `REMINDER_HOUR` (in `TIMEZONE`), but only if they haven't played that day.
- Users can switch it off with `/reminder off`. If a user blocks the bot, reminders to them are switched off automatically.
- "Days in a row" counts consecutive days with at least one flip.

## Storage

Stats and settings are stored in SQLite (`DB_PATH`).

## Deploy (Railway)

- Add the variables from `.env.example` in the service settings.
- The `Procfile` runs the bot as a worker.
- Railway's filesystem is wiped on every deploy. To keep stats between deploys, add a Volume, mount it (e.g. at `/data`) and set `DB_PATH=/data/coinflip.db`.
