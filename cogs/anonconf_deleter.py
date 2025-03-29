import disnake
from disnake.ext import commands
# This cog deletes all messages that are NOT confessions from the #anon-confessions channel.

class MessageDeleter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.dev_logger
        self.channel_id = 1355495965615849535  # The ID of the channel to monitor
        self.bot_id = 1351602723283275807  # The bot's ID

    @commands.Cog.listener()
    async def on_message(self, message):
        # Skip messages from the bot itself
        if message.author.id == self.bot_id:
            return

        # Check if the message is in the specified channel
        if message.channel.id == self.channel_id:
            # Delete the message if it's not from the bot
            try:
                await message.delete()
                self.bot.dev_logger.info(f"Deleted message from {message.author} in channel {message.channel.name}")
            except Exception as e:
                self.bot.dev_logger.error(f"Failed to delete message: {e}")

def setup(bot):
    bot.add_cog(MessageDeleter(bot))
