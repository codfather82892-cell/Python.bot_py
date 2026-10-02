import asyncio
import os
import uvicorn

import bot
from web_app import app


async def run_web():
    port = int(os.getenv("PORT", "8080"))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    await asyncio.gather(
        bot.main(),      # Existing Telegram bot / admin panel
        run_web(),       # New Telegram Mini App web server
    )


if __name__ == "__main__":
    asyncio.run(main())
