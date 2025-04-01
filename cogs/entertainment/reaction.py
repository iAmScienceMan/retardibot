import disnake
from disnake.ext import commands
from cogs.common.base_cog import BaseCog

class ReactionCog(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        
        # Load configuration
        reaction_config = getattr(self.bot, 'config', {}).get("reaction", {})
        self.trigger_words = reaction_config.get("trigger_words", [])
        self.emoji_id = reaction_config.get("emoji_id")
        self.emoji_fallback = reaction_config.get("emoji_fallback", "😳")
        
        # Log initialization details
        self.logger.info(f"Reaction cog initialized with {len(self.trigger_words)} trigger words")
        self.logger.debug(f"Using emoji ID: {self.emoji_id} with fallback: {self.emoji_fallback}")
        if self.logger.isEnabledFor(10):  # DEBUG level
            self.logger.debug(f"Trigger words: {', '.join(self.trigger_words)}")

    @commands.Cog.listener()
    async def on_message(self, message):
        # Skip bot messages
        if message.author.bot:
            return
        
        # Get message content in lowercase for comparison
        content = message.content.lower()
        
        # Check for trigger words
        triggered_words = [word for word in self.trigger_words if word in content]
        if triggered_words:
            self.logger.debug(f"Message triggered reaction in #{message.channel.name} - Words: {', '.join(triggered_words)}")
            
            try:
                # Try to get custom emoji
                emoji = None
                if self.emoji_id:
                    try:
                        emoji_id = int(self.emoji_id) if isinstance(self.emoji_id, str) else self.emoji_id
                        
                        for guild in self.bot.guilds:
                            found_emoji = disnake.utils.get(guild.emojis, id=emoji_id)
                            if found_emoji:
                                emoji = found_emoji
                                self.logger.debug(f"Found custom emoji: {found_emoji.name}")
                                break
                        
                        if not emoji:
                            self.logger.warning(f"Custom emoji with ID {emoji_id} not found in any accessible guild")
                    except (ValueError, TypeError) as e:
                        self.logger.error(f"Error processing emoji ID: {e}", exc_info=True)
                
                # Add the reaction
                if emoji:
                    await message.add_reaction(emoji)
                    self.logger.debug(f"Added custom emoji reaction to message {message.id}")
                else:
                    await message.add_reaction(self.emoji_fallback)
                    self.logger.debug(f"Added fallback emoji reaction to message {message.id}")
                    
            except disnake.Forbidden:
                self.logger.warning(f"Missing permissions to add reaction in channel {message.channel.id}")
            except disnake.NotFound:
                self.logger.warning(f"Message {message.id} not found when trying to add reaction")
            except disnake.HTTPException as e:
                self.logger.error(f"HTTP error adding reaction: {e}", exc_info=True)
            except Exception as e:
                self.logger.error(f"Unexpected error adding reaction: {e}", exc_info=True)

    @commands.group(name="reaction", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def reaction_group(self, ctx):
        """Manage reaction trigger settings"""
        await ctx.send("Please use a subcommand: `list`, `add`, `remove`, `test`")
        self.logger.debug(f"User {ctx.author} requested reaction command help")

    @reaction_group.command(name="list")
    @commands.has_permissions(manage_guild=True)
    async def list_triggers(self, ctx):
        """List all trigger words"""
        if not self.trigger_words:
            await ctx.send("No trigger words configured.")
            self.logger.debug(f"User {ctx.author} listed triggers (none configured)")
            return
            
        # Create embed for trigger words
        embed = disnake.Embed(
            title="Reaction Trigger Words",
            description=f"The following {len(self.trigger_words)} words will trigger a reaction:",
            color=disnake.Color.blue()
        )
        
        # Split into chunks to avoid field value limit
        chunks = [self.trigger_words[i:i+15] for i in range(0, len(self.trigger_words), 15)]
        
        for i, chunk in enumerate(chunks):
            embed.add_field(
                name=f"Triggers {i+1}-{i+len(chunk)}" if len(chunks) > 1 else "Triggers",
                value="\n".join(f"• {word}" for word in chunk),
                inline=False
            )
            
        await ctx.send(embed=embed)
        self.logger.info(f"User {ctx.author} listed {len(self.trigger_words)} trigger words")

    @reaction_group.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def add_trigger(self, ctx, *, word: str):
        """Add a new trigger word"""
        word = word.lower().strip()
        
        if word in self.trigger_words:
            await ctx.send(f"'{word}' is already a trigger word.")
            self.logger.debug(f"User {ctx.author} attempted to add duplicate trigger word: {word}")
            return
            
        # Update config
        config = getattr(self.bot, 'config', {})
        if "reaction" not in config:
            config["reaction"] = {}
            
        if "trigger_words" not in config["reaction"]:
            config["reaction"]["trigger_words"] = []
            
        config["reaction"]["trigger_words"].append(word)
        self.trigger_words.append(word)
        
        # Save config
        try:
            import json
            with open("config.json", 'w') as f:
                json.dump(config, f, indent=4)
                
            await ctx.send(f"Added '{word}' to trigger words.")
            self.logger.info(f"User {ctx.author} added trigger word: {word}")
        except Exception as e:
            await ctx.send(f"Error saving config: {e}")
            self.logger.error(f"Failed to save config when adding trigger word: {e}", exc_info=True)

    @reaction_group.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def remove_trigger(self, ctx, *, word: str):
        """Remove a trigger word"""
        word = word.lower().strip()
        
        if word not in self.trigger_words:
            await ctx.send(f"'{word}' is not a trigger word.")
            self.logger.debug(f"User {ctx.author} attempted to remove non-existent trigger word: {word}")
            return
            
        # Update config
        config = getattr(self.bot, 'config', {})
        if "reaction" in config and "trigger_words" in config["reaction"]:
            if word in config["reaction"]["trigger_words"]:
                config["reaction"]["trigger_words"].remove(word)
                
        if word in self.trigger_words:
            self.trigger_words.remove(word)
        
        # Save config
        try:
            import json
            with open("config.json", 'w') as f:
                json.dump(config, f, indent=4)
                
            await ctx.send(f"Removed '{word}' from trigger words.")
            self.logger.info(f"User {ctx.author} removed trigger word: {word}")
        except Exception as e:
            await ctx.send(f"Error saving config: {e}")
            self.logger.error(f"Failed to save config when removing trigger word: {e}", exc_info=True)

    @reaction_group.command(name="test")
    @commands.has_permissions(manage_guild=True)
    async def test_reaction(self, ctx):
        """Test the reaction emoji"""
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
                    self.logger.error(f"Error processing emoji ID during test: {e}", exc_info=True)
            
            if emoji:
                await ctx.message.add_reaction(emoji)
                await ctx.send(f"Using custom emoji: {emoji}")
                self.logger.debug(f"Tested custom emoji reaction for {ctx.author}")
            else:
                await ctx.message.add_reaction(self.emoji_fallback)
                await ctx.send(f"Using fallback emoji: {self.emoji_fallback}")
                self.logger.debug(f"Tested fallback emoji reaction for {ctx.author}")
                
        except Exception as e:
            await ctx.send(f"Error testing reaction: {e}")
            self.logger.error(f"Error during reaction test: {e}", exc_info=True)

def setup(bot):
    bot.add_cog(ReactionCog(bot))