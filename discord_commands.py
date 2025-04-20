import os
import subprocess
import discord
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
LAST_EVENT_FILE = "last_quake_text.txt"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Discord command bot connected as {bot.user}")

@bot.command(name="status")
async def status(ctx):
    try:
        with open("status.json", "r") as f:
            data = json.load(f)
            await ctx.send(f"✅ QuakeBot is running. Last check-in: `{data['time']}` UTC.")
    except Exception:
        await ctx.send("❌ Cannot communicate with QuakeBot.")

@bot.command(name="restart")
async def restart(ctx):
    try:
        subprocess.run(["sudo", "systemctl", "restart", "quakebot"], check=True)
        await ctx.send("QuakeBot has been restarted.")
    except subprocess.CalledProcessError as e:
        await ctx.send(f"❌ Failed to restart QuakeBot: {e}")

@bot.command(name="uptime")
async def uptime(ctx):
    try:
        result = subprocess.run(["uptime", "-p"], stdout=subprocess.PIPE)
        uptime_str = result.stdout.decode().strip()
        await ctx.send(f"EC2 Instance Uptime: {uptime_str}")
    except Exception as e:
        await ctx.send(f"❌ Failed to fetch uptime: {e}")

@bot.command(name="lastquake")
async def lastquake(ctx):
    try:
        if os.path.exists(LAST_EVENT_FILE):
            with open(LAST_EVENT_FILE, 'r', encoding='utf-8') as f:
                last_event = f.read().strip()
            await ctx.send(f"Last quake event ID:`{last_event}`")
        else:
            await ctx.send("ℹ️ No quake history found yet.")
    except Exception as e:
        await ctx.send(f"❌ Error reading last quake info: {e}")

@bot.command(name="log")
async def log(ctx):
    try:
        with open("latest_error.log", "r", encoding="utf-8") as f:
            lines = f.readlines()[-20:]  # last 20 lines
        log_output = "".join(lines)
        if not log_output:
            log_output = "(log is empty)"
        await ctx.send(f"Recent Error Log Snippet:\n```{log_output}```")
    except Exception as e:
        await ctx.send(f"❌ Could not read logs: {e}")

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
