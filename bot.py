import disnake
from disnake.ext import commands
import tomli
import tomli_w
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

# Load TOML configuration
try:
    with open("config.toml", "rb") as f:
        config = tomli.load(f)
except FileNotFoundError:
    print("Config file config.toml not found, using default values")
    config = {'main': {'prefix': 'rb ', 'owner_id': 587208453018091538}}

# After loading config and before creating the bot
our_owner_id = config.get('main', {}).get('owner_id', 587208453018091538)
print(f"Setting owner ID to: {our_owner_id}")~

# Setup Discord bot
intents = disnake.Intents.all()
bot = commands.Bot(
    command_prefix=config.get('main', {}).get('prefix', 'rb '),
    intents=intents,
    owner_id=our_owner_id,
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
    bot.dev_logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    bot.dev_logger.info(f"Connected to {len(bot.guilds)} guilds")
    
    # Set bot status from config
    if hasattr(bot, 'config') and 'bot_settings' in bot.config:
        bot_settings = bot.config['bot_settings']
        status_type = bot_settings.get('status_type', 'watching')
        status_text = bot_settings.get('status_text', 'you')
        status_state = bot_settings.get('status_state', 'online')
        
        activity = None
        if status_text:
            if status_type.lower() == "playing":
                activity = disnake.Game(name=status_text)
            elif status_type.lower() == "watching":
                activity = disnake.Activity(type=disnake.ActivityType.watching, name=status_text)
            elif status_type.lower() == "listening":
                activity = disnake.Activity(type=disnake.ActivityType.listening, name=status_text)
            elif status_type.lower() == "streaming":
                activity = disnake.Streaming(name=status_text, url="https://www.twitch.tv/directory")
            elif status_type.lower() == "competing":
                activity = disnake.Activity(type=disnake.ActivityType.competing, name=status_text)
        
        presence = disnake.Status.online
        if status_state.lower() == "idle":
            presence = disnake.Status.idle
        elif status_state.lower() == "dnd":
            presence = disnake.Status.dnd
        elif status_state.lower() == "invisible":
            presence = disnake.Status.invisible
            
        await bot.change_presence(activity=activity, status=presence)
        bot.dev_logger.info(f"Set bot status to {status_type}: {status_text} ({status_state})")

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

# Load all cogs from the new organized structure
def load_cogs():
    """Load all cogs from the organized cogs directory structure"""
    cogs_loaded = 0
    cogs_failed = 0
    
    # Create cogs directory if it doesn't exist
    os.makedirs("cogs", exist_ok=True)
    
    # Load DevLogger first to set up proper logging
    try:
        # First try from the new location
        try:
            bot.load_extension("cogs.utilities.devlogger")
            bot.dev_logger.info("Loaded DevLogger cog from new location")
        except (ImportError, ModuleNotFoundError):
            # Fall back to old location if not migrated yet
            bot.load_extension("cogs.devlogger")
            bot.dev_logger.info("Loaded DevLogger cog from original location")
        cogs_loaded += 1
    except Exception as e:
        bot.dev_logger.error(f"Failed to load DevLogger cog: {e}", exc_info=True)
        cogs_failed += 1
    
    # Function to recursively load cogs from directories
    def load_from_dir(directory):
        nonlocal cogs_loaded, cogs_failed
        
        # Check if directory exists
        if not os.path.exists(directory):
            return
        
        for filename in os.listdir(directory):
            path = os.path.join(directory, filename)
            
            # Skip __pycache__ and other special directories
            if filename.startswith("__"):
                continue
                
            # If it's a directory, recurse into it
            if os.path.isdir(path):
                load_from_dir(path)
                continue
                
            # Only load .py files as cogs
            if not filename.endswith('.py'):
                continue
            
            # Skip devlogger as we already loaded it
            if (filename == "devlogger.py"):
                continue

            # Skip base_cog as it is an abstract class
            if (filename == "base_cog.py"):
                continue
            
            # Commented bcs using new free system now
            #if (filename == "automod.py"):
            #    continue

            # Convert file path to module path
            module_path = os.path.relpath(path, os.path.dirname(__file__)).replace(os.sep, '.')[:-3]  # Remove .py
                
            try:
                bot.load_extension(module_path)
                bot.dev_logger.info(f"Loaded cog: {module_path}")
                cogs_loaded += 1
            except Exception as e:
                bot.dev_logger.error(f"Failed to load cog {module_path}: {e}", exc_info=True)
                cogs_failed += 1
    
    # Load all cogs
    load_from_dir("cogs")
    
    bot.dev_logger.info(f"Cog loading complete. Success: {cogs_loaded}, Failed: {cogs_failed}")

# Load cogs and run the bot
if __name__ == "__main__":
    load_cogs()
    
    try:
        bot.dev_logger.info("Connecting to Discord...")
        bot.run(TOKEN)
    except Exception as e:
        bot.dev_logger.critical(f"Failed to start bot: {e}", exc_info=True)