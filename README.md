# NIKAN EARN — Telegram Bot + Mini App

The original Telegram bot/admin-panel code is kept as the base. The Mini App is an additional web layer that uses the same SQLite database.

## What was kept
- Existing Telegram commands and handlers
- Existing Telegram reply keyboard
- Existing Telegram inline buttons and admin panel
- Existing database tables and business logic
- Existing deposit/withdraw/payment-session records
- Existing plans, earnings, bonus, referral and history data

The only runtime changes in `bot.py` are:
1. `BOT_TOKEN` is read from the `BOT_TOKEN` environment variable.
2. `DB_DIR` can point to a persistent Railway Volume; default remains the current directory.

## Railway
1. Create a Railway service from this GitHub repository.
2. Add a Railway Volume and mount it at `/data`.
3. Add Variables:
   - `BOT_TOKEN` = your real BotFather token
   - `DB_DIR` = `/data`
4. Start Command:
   `python run.py`
5. Generate a public HTTPS domain.
6. Set that domain as the Telegram Mini App URL/menu button in your bot configuration.

Do not commit your real token to GitHub.

## Mini App authentication
The browser sends Telegram's `initData` to the backend. The backend validates it with the bot token before reading or changing the user's database records.

## Local
Install:
`pip install -r requirements.txt`

Run:
`BOT_TOKEN="..." python run.py`

The web server uses Railway's `PORT` variable and listens on `0.0.0.0`.

## Important database note
For an existing database, copy your current `nikan.db` into the persistent `/data` volume before first production run if you need the existing user data there. Do not delete or replace the database casually.
