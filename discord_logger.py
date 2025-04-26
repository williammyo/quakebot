import logging
import os
import aiohttp
import asyncio
from dotenv import load_dotenv

load_dotenv()
WEBHOOK_URL = os.getenv("DISCORD_LOG_WEBHOOK")

class DiscordLogHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)

         # Skip repetitive low-value logs
        if (
            "No earthquake detected" in log_entry,
            "Skipping alerts."in log_entry
        ):
            return
        
        if record.levelno >= logging.ERROR:
            log_entry = f"<@squishvocado>\n**[ERROR]**\n{log_entry}"
        else:
            log_entry = f"[LOG] {log_entry}"
        asyncio.create_task(self.send(log_entry))

    async def send(self, message):
        async with aiohttp.ClientSession() as session:
            await session.post(WEBHOOK_URL, json={"content": message})
