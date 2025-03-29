import disnake
from disnake.ext import commands

class MessageDeleter(commands.Cog):
    """Ensures only confessions appear in the confessions channel"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.dev_logger.getChild('message_deleter')
        
        # Get the confession channel ID from config if available
        config = getattr(self.bot, 'config', {})
        confession_config = getattr(self.bot.cogs.get('ConfessionsCog'), 'confession_channel_id', None)
        
        # Use the confession channel ID from ConfessionsCog if available, otherwise use hardcoded value
        self.channel_id = confession_config or 1355495965615849535
        
        self.logger.info(f"Message deleter initialized for channel ID: {self.channel_id}")

    @commands.Cog.listener()
    async def on_message(self, message):
        # Skip messages from any bot
        if message.author.bot:
            return

        # Check if the message is in the monitored channel
        if message.channel.id == self.channel_id:
            try:
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
