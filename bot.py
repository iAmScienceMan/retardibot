import disnake
from disnake.ext import commands
import json
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Load JSON configuration
try:
    with open("config.json") as f:
        config = json.load(f)
except FileNotFoundError:
    print("Config file config.json not found, using default values")
    config = {'prefix': 'rb ', 'owner_id': 0}

# Setup Discord bot
intents = disnake.Intents.all()
bot = commands.Bot(
    command_prefix=config.get('prefix', 'rb '),
    intents=intents,
    owner_id=config.get('owner_id', 0)
)

# Create a basic logger until the DevLogger cog initializes a better one
basic_logger = logging.getLogger('retardibot')
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(levelname)s | %(name)s | %(message)s'))
basic_logger.addHandler(handler)
basic_logger.setLevel(logging.INFO)
bot.dev_logger = basic_logger  # Will be replaced by the DevLogger cog

# Store config in the bot instance for access by cogs
bot.config = config

@bot.event
async def on_ready():
    bot.dev_logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    bot.dev_logger.info(f"Connected to {len(bot.guilds)} guilds")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    
    error_msg = str(error)
    
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing required argument: {error.param.name}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"Bad argument: {error_msg}")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Command on cooldown. Try again in {error.retry_after:.2f}s")
    else:
        bot.dev_logger.error(f"Command error: {error_msg}", exc_info=error)
        await ctx.send(f"An error occurred: {error_msg}")

# Load all cogs
def load_cogs():
    cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
    bot.dev_logger.info(f"Loading cogs from {cogs_dir}")
    
    # Create the cogs directory if it doesn't exist
    os.makedirs(cogs_dir, exist_ok=True)
    
    success_count = 0
    fail_count = 0
    
    # Load the DevLogger cog first to set up the logging system
    try:
        bot.load_extension("cogs.devlogger")
        bot.dev_logger.info("Loaded DevLogger cog")
        success_count += 1
    except Exception as e:
        bot.dev_logger.error(f"Failed to load DevLogger cog: {e}", exc_info=True)
        fail_count += 1
    
    # Then load other cogs
    for filename in os.listdir(cogs_dir):
        if filename.endswith(".py") and filename != "devlogger.py":  # Skip devlogger as we already loaded it
            cog_name = f"cogs.{filename[:-3]}"
            try:
                bot.load_extension(cog_name)
                bot.dev_logger.info(f"Loaded cog: {cog_name}")
                success_count += 1
            except Exception as e:
                bot.dev_logger.error(f"Failed to load cog {cog_name}: {e}", exc_info=True)
                fail_count += 1
    
    bot.dev_logger.info(f"Cog loading complete. Success: {success_count}, Failed: {fail_count}")

# Load cogs and run the bot
if __name__ == "__main__":
    load_cogs()
    
    try:
        bot.dev_logger.info("Connecting to Discord...")
        bot.run(TOKEN)
    except Exception as e:
        bot.dev_logger.critical(f"Failed to start bot: {e}", exc_info=True)