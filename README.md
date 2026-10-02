# NIKAN EARN — Telegram Bot + Mini App

This project keeps the existing Telegram bot/admin-panel code and adds a separate Telegram Mini App layer.

## Files
- `bot.py` — original bot logic, with only environment-driven token/database path.
- `web_app.py` — authenticated Mini App backend.
- `static/index.html` — animated Telegram Mini App UI.
- `run.py` — starts both the Telegram bot and web server.
- `requirements.txt` — Python dependencies.

## Railway variables
Set:
- `BOT_TOKEN` = your BotFather token
- `DB_DIR` = `/data` when using a Railway Volume
- `WEBAPP_URL` = your Railway public HTTPS domain (for example `https://your-service.up.railway.app`)

Do not put the real bot token in GitHub.

## Start command
`python run.py`

## Mini App URL
After deployment, generate a Railway public domain and use that HTTPS URL as the Telegram Mini App URL. Telegram Mini Apps use `window.Telegram.WebApp.initData`; the backend validates it before accessing user data.

## Important
The existing Telegram admin panel remains in Telegram. The Mini App is the user-facing web layer and uses the same SQLite database.
