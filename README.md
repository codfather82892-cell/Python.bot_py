# Vortexa Smart Hosting Bot (updated starter)

## Features
- Telegram `.py` upload flow with optional `requirements.txt` upload.
- Skip button scans Python imports and creates a best-effort `requirements.txt`.
- Per-upload Python virtual environment, dependency install timeout, runtime and install logs.
- My Bots: Start/Stop/Restart/View Logs/Delete with owner checks.
- SQLite database and uploaded projects stored under `DATA_DIR`.

## Railway Variables
- `BOT_TOKEN`: token from BotFather
- `ADMIN_ID`: your numeric Telegram user ID (currently used for future admin features)
- `DATA_DIR`: `/app/data`
- `MAX_FILE_MB`: `2`
- `MAX_RUNTIME_SECONDS`: `3600`
- `INSTALL_TIMEOUT_SECONDS`: `60`

## Railway Persistent Volume
Attach a volume to this service with mount path `/app/data`. Set `DATA_DIR=/app/data`. The database and uploads are stored in this directory. If you previously deployed without a volume, old records/files may have been lost with ephemeral storage; uploading again may be necessary.

## Deploy
Use the repository root containing `bot.py`, `requirements.txt`, `runtime.txt`, and `Procfile`. Ensure the Procfile contains `worker: python bot.py`.

## Important limitations and security
- Automatic dependency detection is a best-effort AST import scan, not real AI and not guaranteed to identify every package or correct PyPI package name. Some packages need system libraries, special setup, or exact versions.
- Dependency installation can take more than 60 seconds or fail; timeout is configurable.
- This is a prototype, not production-grade multi-tenant hosting. Uploaded code executes with the same OS account and can access the service environment/files. Never accept untrusted uploads on a public service. Production must use isolated containers/sandboxing, resource limits, network restrictions, and secret isolation.
- Arbitrary uploaded Telegram bots may conflict if they use the same Telegram token, or may require web services/system packages that this prototype does not provide.
- Process state does not survive Railway redeploy/restart. The bot record/files/logs survive only when the persistent volume is configured correctly.
