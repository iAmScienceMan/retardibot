import disnake
import asyncio
from disnake.ext import commands
from cogs.common.base_cog import BaseCog

class MessageDeleter(BaseCog):
    """Ensures only confessions appear in the confessions channel"""
    
    def __init__(self, bot):
        super().__init__(bot)
        
        # Find the ConfessionsCog
        confession_cog = self.bot.get_cog("ConfessionsCog")
        
        # Get the confession channel ID from the ConfessionsCog or config
        if confession_cog and hasattr(confession_cog, "confession_channel_id"):
            self.channel_id = confession_cog.confession_channel_id
            self.logger.info(f"Using confession channel ID from ConfessionsCog: {self.channel_id}")
        else:
            # Try to get from config as fallback
            config = getattr(self.bot, 'config', {})
            # In TOML, top-level keys are accessed directly
            self.channel_id = config.get("confession_channel_id") or None
            self.logger.warning(f"ConfessionsCog not found or ConfessionsCog.channel_id, reading config.confession_channel_id")
            # Exit the bot if no Confession channel
            if self.channel_id == None:
                self.logger.critical("Could not find config.confession_channel_id, disabling this cog.")
                raise ValueError("Missing required configuration: confession_channel_id")

        # Get moderator role ID for exemption check
        # In TOML, we access nested dictionaries/tables the same way
        automod_config = getattr(self.bot, 'config', {}).get("automod", {})
        self.mod_role_id = automod_config.get("mod_role_id", None)
        if self.mod_role_id == None:
            self.logger.critical("Could not find config.automod.mod_role_id, disabling this cog.")
            raise ValueError("Missing required configuration: automod.mod_role_id")
        
        self.logger.info(f"Message deleter initialized for channel ID: {self.channel_id}")

    def has_mod_role(self, member):
        """Check if a member has the moderator role"""
        if not member or not member.guild:
            return False
            
        mod_role = member.guild.get_role(self.mod_role_id)
        if not mod_role:
            return False
            
        return mod_role in member.roles

    @commands.Cog.listener()
    async def on_message(self, message):
        # Skip messages from any bot
        if message.author.bot:
            return

        # Check if the message is in the monitored channel
        if message.channel.id == self.channel_id:
            # Don't delete messages from moderators
            if self.has_mod_role(message.author):
                return
                
            try:
                # Check if we have permission to delete messages
                if not message.channel.permissions_for(message.guild.me).manage_messages:
                    self.logger.warning(f"Missing manage_messages permission in channel {message.channel.id}")
                    return
                    
                # Delete the message and log it
                await message.delete()
                self.logger.info(
                    f"Deleted unauthorized message from {message.author} ({message.author.id}) in confessions channel"
                )
            except disnake.Forbidden:
                self.logger.error(
                    f"Missing permissions to delete message from {message.author.id} in channel {message.channel.id}"
                )
            except disnake.NotFound:
                self.logger.warning(
                    f"Message {message.id} was already deleted before I could remove it"
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to delete message from {message.author.id}: {str(e)}", 
                    exc_info=True
                )

def setup(bot):
    bot.add_cog(MessageDeleter(bot))