import disnake
from disnake.ext import commands
import asyncio
import re
import datetime
from cogs.common.base_cog import BaseCog

class BotLoyaltyCog(BaseCog):
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
        
        # Debug mode - can be toggled with a command
        self.debug_mode = True
        
        # Testing mode - if True, will apply to owner as well (for testing)
        self.test_owner_too = True
        
        self.logger.info(f"Bot Loyalty cog initialized, protecting {len(self.mod_command_keywords)} command types")
        self.logger.info(f"Owner ID: {self.owner_id}, Alert Channel ID: {self.alert_channel_id}")
        self.logger.info(f"Debug mode: {self.debug_mode}, Test owner mode: {self.test_owner_too}")
    
    async def is_message_for_another_bot(self, message):
        """Determine if the message appears to be a command for another bot"""
        # Skip messages with no content
        if not message.content:
            if self.debug_mode:
                self.logger.debug(f"Skipping empty message from {message.author.id}")
            return False
            
        # Skip messages to our bot
        if self.bot.user in message.mentions:
            if self.debug_mode:
                self.logger.debug(f"Skipping message mentioning our bot from {message.author.id}")
            return False
        
        # Check if message starts with a bot prefix and contains a mod command keyword
        for i, pattern in enumerate(self.command_patterns):
            match = pattern.search(message.content)
            if match:
                if self.debug_mode:
                    self.logger.debug(f"Command detected: '{message.content}' from {message.author.id} matched pattern {i+1}: '{match.group(0)}'")
                return True
                
        # If message mentions another bot
        for user in message.mentions:
            if user.bot and user.id != self.bot.user.id:
                # Check if the message has mod command keywords
                for keyword in self.mod_command_keywords:
                    if keyword in message.content.lower():
                        if self.debug_mode:
                            self.logger.debug(f"Bot mention detected: '{message.content}' from {message.author.id} mentioned bot {user.id} with keyword '{keyword}'")
                        return True
                    
        if self.debug_mode:
            self.logger.debug(f"Message '{message.content}' from {message.author.id} does not appear to be a command for another bot")
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
        
        if self.debug_mode:           
            self.logger.debug(f"Extracted potential target IDs from message: {target_user_ids}")
                    
        if not target_user_ids:
            self.logger.debug("No target user IDs found to reverse actions for")
            return False
            
        actions_reversed = False
        
        # Check for ban command
        if any(kw in message.content.lower() for kw in ["ban"]) and not any(kw in message.content.lower() for kw in ["unban"]):
            self.logger.debug(f"Detected potential ban command, attempting to reverse for {len(target_user_ids)} users")
            
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
            self.logger.debug(f"Detected potential timeout/mute command, attempting to reverse for {len(target_user_ids)} users")
            
            for user_id in target_user_ids:
                try:
                    member = guild.get_member(user_id)
                    if member:
                        if member.timed_out_until:
                            self.logger.debug(f"User {user_id} is timed out until {member.timed_out_until}, removing timeout")
                            await member.timeout(None, reason="Reversed timeout from unauthorized bot usage")
                            await message.channel.send(f"Reversed timeout for {member.mention}")
                            self.logger.info(f"Reversed timeout for user {member.id}")
                            actions_reversed = True
                        else:
                            self.logger.debug(f"User {user_id} is not timed out, no action needed")
                    else:
                        self.logger.debug(f"Could not find member with ID {user_id} in guild")
                except Exception as e:
                    self.logger.debug(f"Failed to reverse timeout for {user_id}: {e}")
        
        if self.debug_mode:
            self.logger.debug(f"Reversal attempt complete, actions_reversed={actions_reversed}")
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
        if self.debug_mode:
            self.logger.debug(f"Checking message: '{message.content}' from {message.author.id} in guild {message.guild.id if message.guild else 'DM'}")
        
        # Skip messages from our bot or in DMs
        if message.author.id == self.bot.user.id:
            if self.debug_mode:
                self.logger.debug("Skipping message from our bot")
            return
            
        if not message.guild:
            if self.debug_mode:
                self.logger.debug("Skipping DM message")
            return
            
        # Skip messages from non-mods
        if not self.has_mod_role(message.author):
            if self.debug_mode:
                self.logger.debug(f"Skipping message from non-mod user {message.author.id}")
            return
        
        # Check if the user is the bot owner
        is_owner = await self.bot.is_owner(message.author)
        if self.debug_mode:
            self.logger.debug(f"User {message.author.id} is owner: {is_owner}")
            
        # Skip messages from bot owners unless in test mode
        if is_owner and not self.test_owner_too:
            if self.debug_mode:
                self.logger.debug(f"Skipping message from bot owner {message.author.id}")
            return
            
        # Check if this appears to be a moderation command for another bot
        command_detected = await self.is_message_for_another_bot(message)
        if self.debug_mode:
            self.logger.debug(f"Command for another bot detected: {command_detected}")
            
        if command_detected:
            self.logger.warning(f"Detected moderation command for another bot: {message.author} tried to use '{message.content}'")
            
            try:
                # Track actions we take
                actions_taken = []
                
                # Delete the original message
                await message.delete()
                actions_taken.append("Deleted command message")
                self.logger.debug(f"Deleted command message from {message.author.id}")
                
                # Send warning message
                warning_msg = await message.channel.send(f"Use {self.bot.user.mention}")
                actions_taken.append("Sent warning message")
                self.logger.debug(f"Sent warning message in channel {message.channel.id}")
                
                # Try to reverse any moderation actions
                reversed = await self.try_reverse_mod_action(message, message.guild)
                if reversed:
                    actions_taken.append("Reversed moderation action(s)")
                    self.logger.debug("Successfully reversed one or more moderation actions")
                
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
                    else:
                        self.logger.debug("ModerationCog not found, couldn't add warning to logs")
                except Exception as e:
                    self.logger.error(f"Failed to log warning to moderation logs: {e}")
                
                # Alert the owner
                await self.alert_owner(message, "\n".join(actions_taken))
                
                # Delete our warning message after a short delay
                await asyncio.sleep(10)
                try:
                    await warning_msg.delete()
                    self.logger.debug(f"Deleted warning message in channel {message.channel.id}")
                except Exception as e:
                    self.logger.debug(f"Failed to delete warning message: {e}")
                    
            except disnake.Forbidden:
                self.logger.warning(f"Missing permissions to enforce bot loyalty in guild {message.guild.id}, channel {message.channel.id}")
            except Exception as e:
                self.logger.error(f"Error in bot loyalty enforcement: {e}", exc_info=True)
    
    @commands.group(name="loyalty", invoke_without_command=True)
    @commands.is_owner()
    async def loyalty_group(self, ctx):
        """Manage bot loyalty settings"""
        embed = disnake.Embed(
            title="Bot Loyalty Settings",
            description="Current configuration for the bot loyalty system",
            color=disnake.Color.blue()
        )
        
        embed.add_field(name="Debug Mode", value=f"{'Enabled' if self.debug_mode else 'Disabled'}", inline=True)
        embed.add_field(name="Test Owner Mode", value=f"{'Enabled' if self.test_owner_too else 'Disabled'}", inline=True)
        embed.add_field(name="Alert Channel", value=f"<#{self.alert_channel_id}>" if self.alert_channel_id else "None", inline=True)
        
        await ctx.send(embed=embed)
    
    @loyalty_group.command(name="debug")
    @commands.is_owner()
    async def loyalty_debug(self, ctx, enabled: bool = None):
        """Toggle debug mode for bot loyalty system"""
        if enabled is None:
            # Toggle
            self.debug_mode = not self.debug_mode
        else:
            self.debug_mode = enabled
            
        await ctx.send(f"Debug mode {'enabled' if self.debug_mode else 'disabled'}")
        self.logger.info(f"Debug mode set to {self.debug_mode} by {ctx.author.id}")
    
    @loyalty_group.command(name="testowner")
    @commands.is_owner()
    async def loyalty_test_owner(self, ctx, enabled: bool = None):
        """Toggle whether loyalty checks apply to the owner (for testing)"""
        if enabled is None:
            # Toggle
            self.test_owner_too = not self.test_owner_too
        else:
            self.test_owner_too = enabled
            
        await ctx.send(f"Test owner mode {'enabled' if self.test_owner_too else 'disabled'}")
        self.logger.info(f"Test owner mode set to {self.test_owner_too} by {ctx.author.id}")
    
    @loyalty_group.command(name="test")
    @commands.is_owner()
    async def loyalty_test(self, ctx, *, test_command: str):
        """Test if a command would be detected by the bot loyalty system"""
        if await self.is_message_for_another_bot(ctx.message):
            await ctx.send(f"✅ Command **WOULD** be detected as another bot's command: `{test_command}`")
        else:
            await ctx.send(f"❌ Command would **NOT** be detected as another bot's command: `{test_command}`")

def setup(bot):
    bot.add_cog(BotLoyaltyCog(bot))