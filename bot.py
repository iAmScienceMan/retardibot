import disnake
from disnake.ext import commands
import json
import os
from dotenv import load_dotenv
import logging


"""
retardibot - A Long-Term Support Discord bot
Copyright (C) 2025 iAmScienceMan
Licensed under AGPLv3 - see LICENSE file for details.
Unauthorized removal of this notice violates licensing terms.
"""


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
    owner_id=config.get('owner_id', 0),
    help_command=None
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
    activity = disnake.Activity(
        type=disnake.ActivityType.watching,
        name="you"
    )
    await bot.change_presence(activity=activity)

    bot.dev_logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    bot.dev_logger.info(f"Connected to {len(bot.guilds)} guilds")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    
    error_msg = str(error)
    
    if isinstance(error, commands.MissingRequiredArgument):
        bot.dev_logger.warning(f"Missing argument: {error.param.name} in command {ctx.command} by {ctx.author}")
    elif isinstance(error, commands.BadArgument):
        bot.dev_logger.warning(f"Bad argument in {ctx.command} by {ctx.author}: {error_msg}")
    elif isinstance(error, commands.CommandOnCooldown):
        bot.dev_logger.debug(f"Command {ctx.command} on cooldown for {ctx.author}: {error.retry_after:.2f}s")
    elif isinstance(error, commands.CheckFailure):
        bot.dev_logger.info(f"Permission check failed for {ctx.author} on command {ctx.command}")
    else:
        bot.dev_logger.error(f"Command error in {ctx.command} by {ctx.author}: {error_msg}", exc_info=error)

@bot.check
async def blacklist_check(ctx):
    """Global check - prevents blacklisted users from using commands"""
    # Skip check for the bot owner
    if await bot.is_owner(ctx.author):
        return True
        
    # Get the blacklist from config
    blacklist = getattr(bot, 'config', {}).get("blacklist", {})
    
    # Check if user is blacklisted
    if str(ctx.author.id) in blacklist:
        # Optionally log the attempt
        bot.dev_logger.info(f"Blocked command from blacklisted user {ctx.author} ({ctx.author.id})")
        
        # Silently fail - don't let them know they're blacklisted
        return False
        
    # User not blacklisted, allow command
    return True

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