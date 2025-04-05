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
        
        # Create a proper regex pattern that escapes the dash to avoid "bad character range" error
        bot_prefixes_pattern = ''.join([re.escape(p) for p in self.common_bot_prefixes])
        mod_keywords_pattern = '|'.join(self.mod_command_keywords)
        
        # Regex patterns for detecting bot commands
        self.command_patterns = [
            re.compile(fr"^[{bot_prefixes_pattern}](?:{mod_keywords_pattern})\b", re.IGNORECASE),  # Prefix commands like !ban
            re.compile(fr"^/(?:{mod_keywords_pattern})\b", re.IGNORECASE)  # Slash commands like /ban
        ]
        
        # Get owner_id from config, properly handling TOML structure
        config = getattr(self.bot, 'config', {})
        self.owner_id = config.get('main', {}).get('owner_id', 0)
        
        # Get alert channel from automod config, properly handling TOML structure
        automod_config = config.get("automod", {})
        self.alert_channel_id = automod_config.get("alert_channel_id")
        
        # Staff role ID (specifically mentioned in your message)
        self.staff_role_id = 1342693546511040559
        
        # Detainee role ID used by other bots for muting
        self.detainee_role_id = 1342693546511040555
        
        # Role checking wait settings
        self.role_check_attempts = 10  # Number of attempts to check for the role
        self.role_check_delay = 2.0    # Delay in seconds between checks
        
        # Debug mode - can be toggled with a command
        self.debug_mode = True
        
        # Testing mode - if True, will apply to owner as well (for testing)
        self.test_owner_too = True
        
        self.logger.info(f"Bot Loyalty cog initialized, protecting {len(self.mod_command_keywords)} command types")
        self.logger.info(f"Owner ID: {self.owner_id}, Alert Channel ID: {self.alert_channel_id}")
        self.logger.info(f"Staff Role ID: {self.staff_role_id}, Detainee Role ID: {self.detainee_role_id}")
        self.logger.info(f"Debug mode: {self.debug_mode}, Test owner mode: {self.test_owner_too}")
    
    def has_staff_permissions(self, member):
        """Check if a member has staff permissions based on roles or admin permissions"""
        # Safety check - if this is a User not a Member, we don't have guild permissions
        if not isinstance(member, disnake.Member):
            return False
            
        # Check for admin permissions
        if member.guild_permissions.administrator:
            if self.debug_mode:
                self.logger.debug(f"User {member.id} has administrator permissions")
            return True
            
        # Check for the specific staff role
        staff_role = member.guild.get_role(self.staff_role_id)
        if staff_role and staff_role in member.roles:
            if self.debug_mode:
                self.logger.debug(f"User {member.id} has the staff role")
            return True
            
        # Check for mod role using the BaseCog method
        if self.has_mod_role(member):
            if self.debug_mode:
                self.logger.debug(f"User {member.id} has the mod role")
            return True
            
        return False
    
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
    
    async def wait_for_role_and_remove(self, member, role, channel, guild):
        """Wait for a role to be applied and then remove it"""
        self.logger.debug(f"Starting role wait-and-remove process for user {member.id}")
        
        # Get updated member object
        try:
            member = await guild.fetch_member(member.id)
        except Exception as e:
            self.logger.error(f"Error fetching updated member data: {e}")
            return False
        
        # If the member already has the role, remove it immediately
        if role in member.roles:
            self.logger.debug(f"User {member.id} already has the role, removing immediately")
            await member.remove_roles(role, reason="Reversed mute from unauthorized bot usage")
            await channel.send(f"Reversed mute for {member.mention} (detainee role removed)")
            return True
            
        # Otherwise, wait and check for the role
        self.logger.debug(f"User {member.id} doesn't have the role yet, starting wait loop")
        
        for attempt in range(1, self.role_check_attempts + 1):
            self.logger.debug(f"Role check attempt {attempt}/{self.role_check_attempts} for user {member.id}")
            
            # Wait for a short time
            await asyncio.sleep(self.role_check_delay)
            
            # Refresh member data to get current roles
            try:
                # We need to fetch the member again to get updated role info
                updated_member = await guild.fetch_member(member.id)
                
                self.logger.debug(f"User {member.id} has roles: {[r.id for r in updated_member.roles]}")
                self.logger.debug(f"Looking for role {role.id} ({role.name})")
                
                if role in updated_member.roles:
                    self.logger.debug(f"Role found on attempt {attempt} for user {member.id}, removing it")
                    try:
                        await updated_member.remove_roles(role, reason="Reversed mute from unauthorized bot usage")
                        await channel.send(f"Reversed mute for {member.mention} (detainee role removed after {attempt} attempt{'s' if attempt > 1 else ''})")
                        return True
                    except Exception as e:
                        self.logger.error(f"Error removing role: {e}")
                        await channel.send(f"Failed to remove role from {member.mention}: {e}")
                        return False
            except Exception as e:
                self.logger.error(f"Error checking/removing role on attempt {attempt}: {e}")
        
        self.logger.debug(f"Role not found after {self.role_check_attempts} attempts for user {member.id}")
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
            
            # Get the detainee role
            detainee_role = guild.get_role(self.detainee_role_id)
            if not detainee_role:
                self.logger.warning(f"Could not find detainee role with ID {self.detainee_role_id}")
                self.logger.debug(f"Available roles in guild: {[r.id for r in guild.roles]}")
            else:
                self.logger.debug(f"Found detainee role: {detainee_role.name} ({detainee_role.id})")
            
            for user_id in target_user_ids:
                try:
                    member = guild.get_member(user_id)
                    if member:
                        timeout_removed = False
                        
                        # Check and remove timeout if present
                        if member.timed_out_until:
                            self.logger.debug(f"User {user_id} is timed out until {member.timed_out_until}, removing timeout")
                            await member.timeout(None, reason="Reversed timeout from unauthorized bot usage")
                            await message.channel.send(f"Reversed timeout for {member.mention}")
                            self.logger.info(f"Reversed timeout for user {member.id}")
                            timeout_removed = True
                            actions_reversed = True
                            
                        # Start a task to wait for and remove the detainee role
                        if detainee_role:
                            self.logger.debug(f"Starting background task to wait for and remove detainee role for {member.id}")
                            # Create a separate task that we don't await - it will run in the background
                            task = asyncio.create_task(
                                self.wait_for_role_and_remove(member, detainee_role, message.channel, guild)
                            )
                            # Add a name to the task to make debugging easier
                            task.set_name(f"remove_role_{member.id}")
                            actions_reversed = True
                            
                        if not timeout_removed and not detainee_role:
                            self.logger.debug(f"User {user_id} is not muted or timed out, and no detainee role exists")
                    else:
                        self.logger.debug(f"Could not find member with ID {user_id} in guild")
                except Exception as e:
                    self.logger.debug(f"Failed to reverse mute actions for {user_id}: {e}")
        
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
        # Skip if not in a guild
        if not hasattr(message, 'guild') or not message.guild:
            return
        
        if self.debug_mode:
            self.logger.debug(f"Checking message: '{message.content}' from {message.author.id} in guild {message.guild.id}")
        
        # Skip messages from our bot
        if message.author.id == self.bot.user.id:
            if self.debug_mode:
                self.logger.debug("Skipping message from our bot")
            return
        
        # Make sure we're dealing with a Member object
        if not isinstance(message.author, disnake.Member):
            if self.debug_mode:
                self.logger.debug(f"Author is not a Member object, skipping: {message.author}")
            return
            
        # Skip messages from non-staff
        if not self.has_staff_permissions(message.author):
            if self.debug_mode:
                self.logger.debug(f"Skipping message from non-staff user {message.author.id}")
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
                    actions_taken.append("Initiated reversal of moderation action(s)")
                    self.logger.debug("Initiated reversal of moderation actions")
                
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
        embed.add_field(name="Staff Role", value=f"<@&{self.staff_role_id}>", inline=True)
        embed.add_field(name="Detainee Role", value=f"<@&{self.detainee_role_id}>", inline=True)
        embed.add_field(name="Role Check Settings", value=f"{self.role_check_attempts} attempts, {self.role_check_delay}s delay", inline=True)
        
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
    
    @loyalty_group.command(name="rolecheck")
    @commands.is_owner()
    async def loyalty_role_check(self, ctx, attempts: int = None, delay: float = None):
        """Set role check attempts and delay (in seconds)"""
        if attempts is not None:
            self.role_check_attempts = max(1, min(attempts, 20))  # Between 1 and 20
            
        if delay is not None:
            self.role_check_delay = max(0.5, min(delay, 5.0))  # Between 0.5 and 5 seconds
            
        await ctx.send(f"Role check settings updated: {self.role_check_attempts} attempts with {self.role_check_delay}s delay")
        self.logger.info(f"Role check settings updated: {self.role_check_attempts} attempts, {self.role_check_delay}s delay")
    
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