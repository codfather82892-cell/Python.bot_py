# Vortexa Smart Hosting Bot — starter

Telegram hosting-panel style starter: upload `.py`, syntax-check, start/stop/restart, list bots, and view saved error output.

## Deploy to Railway
1. Create a new GitHub repository and upload these files.
2. In Railway, deploy the repository as a Python service.
3. Add Variables: `BOT_TOKEN`, `ADMIN_ID`, optionally `MAX_FILE_MB=2`, `MAX_RUNTIME_SECONDS=3600`.
4. Add a persistent volume mounted at `/app/data` and set `DATA_DIR=/app/data` so SQLite and uploaded files persist.
5. Start command: `python bot.py` (or use the included Procfile).
6. Check Railway Deploy Logs after deployment.

## Important limitations / security
- This is a starter, not a production multi-tenant hosting service.
- It currently accepts `.py` files only; ZIP, arbitrary binaries, automatic dependency installation, and full live log streaming are not implemented.
- Uploaded code runs as the same OS account as the host process. **Do not expose this to public users or run untrusted uploads in production.** A production version must launch each user project in a separate locked-down Docker/container sandbox with CPU/RAM/PID/disk/network limits, no host secrets, and a strict timeout.
- Syntax checking and auto-restart cannot fix arbitrary code. The 2–5 second target is best-effort for small scripts and cannot be guaranteed.
- Subscription plans are display-only. Payments, quota enforcement, admin controls, and AI repair are not implemented.
- Railway ephemeral storage is lost on redeploy unless a persistent volume is mounted.
