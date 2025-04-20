import asyncio
import subprocess

async def start_script(script_name):
    process = await asyncio.create_subprocess_exec(
        "python", script_name
    )
    await process.wait()

async def main():
    await asyncio.gather(
        start_script("quake_bot.py"),
        start_script("discord_commands.py")
    )

asyncio.run(main())
