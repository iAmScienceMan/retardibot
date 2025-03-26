import disnake
from disnake.ext import commands
import json
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

# Load configuration once
with open("config.json") as f:
    config = json.load(f)

intents = disnake.Intents.all()
bot = commands.Bot(command_prefix=config["prefix"], intents=intents, owner_id=config["owner_id"])

# Store config in the bot instance for access by cogs
bot.config = config

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

for filename in os.listdir("./cogs"):
    if filename.endswith(".py"):
        bot.load_extension(f"cogs.{filename[:-3]}")

bot.run(TOKEN)