# cogs/reaction_cog.py
import disnake
from disnake.ext import commands

class ReactionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        reaction_config = getattr(self.bot, 'config', {}).get("reaction", {})
        self.trigger_words = reaction_config.get("trigger_words", [])
        self.emoji_id = reaction_config.get("emoji_id")
        self.emoji_fallback = reaction_config.get("emoji_fallback", "😳")
        
        print(f"Reaction Cog loaded with {len(self.trigger_words)} trigger words")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        content = message.content.lower()
        
        if any(word in content for word in self.trigger_words):
            try:
                emoji = None
                if self.emoji_id:
                    try:
                        emoji_id = int(self.emoji_id) if isinstance(self.emoji_id, str) else self.emoji_id
                        
                        for guild in self.bot.guilds:
                            found_emoji = disnake.utils.get(guild.emojis, id=emoji_id)
                            if found_emoji:
                                emoji = found_emoji
                                break
                    except (ValueError, TypeError) as e:
                        print(f"Error processing emoji ID: {e}")
                
                if emoji:
                    await message.add_reaction(emoji)
                else:
                    await message.add_reaction(self.emoji_fallback)
                    
            except Exception as e:
                print(f"Failed to add reaction: {e}")

def setup(bot):
    bot.add_cog(ReactionCog(bot))