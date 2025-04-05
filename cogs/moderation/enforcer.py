import disnake
from disnake.ext import commands
import asyncio
import re
import datetime
from cogs.common.base_cog import BaseCog

class EnforcerCog(BaseCog):
    """Makes sure moderators only use RetardiBot for moderation actions"""
    
    def __init__(self, bot):
        super().__init__(bot)
        
        # Common moderation command keywords to look for
        self.mod_command_keywords = [
            "ban", "kick", "mute", "timeout", "warn", "unban", "unmute", 
            "untimeout", "clear", "purge", "delete", "lock", "unlock"
        ]
        
        # Common bot prefixes to watch for
        self.common_bot_prefixes = ["!", "?", ".", "-", "$", "~", ";", ">", "<", "|", "+"]
        
        # Regex patterns for detecting bot commands
        self.command_patterns = [
            re.compile(fr"^[{''.join(self.common_bot_prefixes)}](?:{('|').join(self.mod_command_keywords)})\b", re.IGNORECASE),  # Prefix commands like !ban
            re.compile(fr"^/(?:{('|').join(self.mod_command_keywords)})\b", re.IGNORECASE)  # Slash commands like /ban
        ]
        
        # Get owner_id from config
        self.owner_id = getattr(self.bot, 'config', {}).get('owner_id', 0)
        
        # Get alert channel from automod config
        automod_config = getattr(self.bot, 'config', {}).get("automod", {})
        self.alert_channel_id = automod_config.get("alert_channel_id")
        
        self.logger.info(f"Bot Loyalty cog initialized, protecting {len(self.mod_command_keywords)} command types")
    
    async def is_message_for_another_bot(self, message):
        """Determine if the message appears to be a command for another bot"""
        # Skip messages with no content
        if not message.content:
            return False
            
        # Skip messages to our bot
        if self.bot.user in message.mentions:
            return False
        
        # If message starts with a bot prefix and contains a mod command keyword
        for pattern in self.command_patterns:
            if pattern.search(message.content):
                return True
                
        # If message mentions another bot
        for user in message.mentions:
            if user.bot and user.id != self.bot.user.id:
                # Check if the message has mod command keywords
                if any(keyword in message.content.lower() for keyword in self.mod_command_keywords):
                    return True
                    
        return False
    
    async def try_reverse_mod_action(self, message, guild):
        """Attempt to reverse any moderation action that might have been performed"""
        # Extract potential user IDs from the message
        user_matches = re.findall(r'<@!?(\d+)>|(\d{17,20})', message.content)
        target_user_ids = []
        
        for match in user_matches:
            user_id = next((m for m in match if m), None)
            if user_id:
                try:
                    target_user_ids.append(int(user_id))
                except ValueError:
                    pass
                    
        if not target_user_ids:
            return False
            
        actions_reversed = False
        
        # Check for ban command
        if any(kw in message.content.lower() for kw in ["ban"]) and not any(kw in message.content.lower() for kw in ["unban"]):
            for user_id in target_user_ids:
                try:
                    # Try to unban the user
                    await guild.unban(disnake.Object(id=user_id))
                    await message.channel.send(f"Reversed ban action on user ID: {user_id}")
                    self.logger.info(f"Reversed ban for user ID {user_id}")
                    actions_reversed = True
                except (disnake.NotFound, disnake.HTTPException) as e:
                    self.logger.debug(f"Failed to reverse ban for {user_id}: {e}")
            
        # Check for timeout/mute command
        if any(kw in message.content.lower() for kw in ["timeout", "mute"]) and not any(kw in message.content.lower() for kw in ["untimeout", "unmute"]):
            for user_id in target_user_ids:
                try:
                    member = guild.get_member(user_id)
                    if member and member.timed_out_until:
                        await member.timeout(None, reason="Reversed timeout from unauthorized bot usage")
                        await message.channel.send(f"Reversed timeout for {member.mention}")
                        self.logger.info(f"Reversed timeout for user {member.id}")
                        actions_reversed = True
                except Exception as e:
                    self.logger.debug(f"Failed to reverse timeout for {user_id}: {e}")
            
        return actions_reversed
    
    async def alert_owner(self, message, action_type):
        """Send an alert to the owner via the log channel"""
        if not self.alert_channel_id:
            self.logger.warning("No alert channel configured for bot loyalty alerts")
            return
            
        alert_channel = self.bot.get_channel(self.alert_channel_id)
        if not alert_channel:
            self.logger.warning(f"Could not find alert channel with ID {self.alert_channel_id}")
            return
            
        # Get the owner mention
        owner_mention = f"<@{self.owner_id}>"
        
        # Create an embed with all the details
        embed = disnake.Embed(
            title="⚠️ Bot Loyalty Violation ⚠️",
            description=f"A moderator attempted to use another bot for moderation!",
            color=disnake.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )
        
        embed.add_field(name="Moderator", value=f"{message.author.mention} ({message.author.name}, ID: {message.author.id})", inline=False)
        embed.add_field(name="Server", value=f"{message.guild.name} (ID: {message.guild.id})", inline=True)
        embed.add_field(name="Channel", value=f"{message.channel.mention} (#{message.channel.name})", inline=True)
        embed.add_field(name="Command Used", value=f"```{message.content}```", inline=False)
        embed.add_field(name="Action Taken", value=action_type, inline=False)
        
        if message.author.avatar:
            embed.set_thumbnail(url=message.author.avatar.url)
            
        try:
            # Send ping and embed
            await alert_channel.send(f"{owner_mention} - Bot Loyalty Alert!", embed=embed)
            self.logger.info(f"Sent bot loyalty alert to channel {self.alert_channel_id}")
        except Exception as e:
            self.logger.error(f"Failed to send alert to owner: {e}", exc_info=True)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        # Skip messages from our bot or in DMs
        if message.author.id == self.bot.user.id or not message.guild:
            return
            
        # Skip messages from non-mods
        if not self.has_mod_role(message.author):
            return
        
        # Skip messages from bot owners
        if await self.bot.is_owner(message.author):
            return
            
        # Check if this appears to be a moderation command for another bot
        if await self.is_message_for_another_bot(message):
            self.logger.warning(f"Detected moderation command for another bot: {message.author} tried to use '{message.content}'")
            
            try:
                # Track actions we take
                actions_taken = []
                
                # Delete the original message
                await message.delete()
                actions_taken.append("Deleted command message")
                
                # Send warning message
                warning_msg = await message.channel.send(f"Use {self.bot.user.mention}")
                actions_taken.append("Sent warning message")
                
                # Try to reverse any moderation actions
                reversed = await self.try_reverse_mod_action(message, message.guild)
                if reversed:
                    actions_taken.append("Reversed moderation action(s)")
                
                # Log the warning using moderation cog if available
                try:
                    mod_cog = self.bot.get_cog("ModerationCog")
                    if mod_cog:
                        mod_cog._add_mod_action(
                            message.guild.id, 
                            message.author.id, 
                            self.bot.user.id,
                            "WARN", 
                            f"Attempted to use another bot for moderation: '{message.content}'"
                        )
                        actions_taken.append("Added warning to moderation logs")
                        self.logger.info(f"Added warning for {message.author.id} in the moderation logs")
                except Exception as e:
                    self.logger.error(f"Failed to log warning to moderation logs: {e}")
                
                # Alert the owner
                await self.alert_owner(message, "\n".join(actions_taken))
                
                # Delete our warning message after a short delay
                await asyncio.sleep(10)
                try:
                    await warning_msg.delete()
                except:
                    pass
                    
            except disnake.Forbidden:
                self.logger.warning(f"Missing permissions to enforce bot loyalty in {message.guild.id}")
            except Exception as e:
                self.logger.error(f"Error in bot loyalty enforcement: {e}", exc_info=True)

def setup(bot):
    bot.add_cog(EnforcerCog(bot))