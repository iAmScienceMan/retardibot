import disnake
from disnake.ext import commands
import datetime
import asyncio
from cogs.common.base_cog import BaseCog

class AutoGuildCheckerCog(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.authorized_guilds = [1351605814623866920, 1342693545819115560]
        self.owner_id = getattr(self.bot, 'owner_id', None)
        self.logger.info(f"AutoGuildChecker initialized with {len(self.authorized_guilds)} authorized guilds")
    
    async def get_guild_info_embed(self, guild):
        """Creates a detailed embed with guild information"""
        try:
            # Get invite for this guild
            invite = None
            try:
                invite_list = await guild.invites()
                invite = next((invite for invite in invite_list), None)
            except disnake.Forbidden:
                self.logger.warning(f"Missing permissions to get invites for guild {guild.id} ({guild.name})")
            
            # If no existing invite found, try to create one from the system channel
            if not invite:
                try:
                    invite_channel = guild.system_channel or next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).create_instant_invite), None)
                    if invite_channel:
                        invite = await invite_channel.create_invite(reason="Bot security audit", max_age=3600)  # 1 hour invite
                except disnake.Forbidden:
                    self.logger.warning(f"Missing permissions to create invite for guild {guild.id} ({guild.name})")
                except Exception as e:
                    self.logger.error(f"Error creating invite for guild {guild.id}: {e}")
            
            # Get basic guild stats
            text_channels = len(guild.text_channels)
            voice_channels = len(guild.voice_channels)
            total_members = guild.member_count
            online_members = sum(1 for m in guild.members if m.status != disnake.Status.offline) if guild.chunked else "Unknown"
            bot_count = sum(1 for m in guild.members if m.bot) if guild.chunked else "Unknown"
            human_count = sum(1 for m in guild.members if not m.bot) if guild.chunked else "Unknown"
            
            # Get owner info
            owner = guild.owner
            owner_info = f"{owner} ({owner.id})" if owner else "Unknown"
            
            # Create embed for this guild
            embed = disnake.Embed(
                title=f"⚠️ Unauthorized Guild Joined: {guild.name}",
                description=f"ID: {guild.id}\nCreated: <t:{int(guild.created_at.timestamp())}:R>",
                color=disnake.Color.red(),
                timestamp=datetime.datetime.utcnow()
            )
            
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            embed.add_field(name="Owner", value=owner_info, inline=False)
            embed.add_field(name="Channels", value=f"Text: {text_channels}\nVoice: {voice_channels}", inline=True)
            embed.add_field(name="Members", value=f"Total: {total_members}\nOnline: {online_members}\nHumans: {human_count}\nBots: {bot_count}", inline=True)
            
            if invite:
                embed.add_field(name="Invite Link", value=str(invite), inline=False)
            else:
                embed.add_field(name="Invite Link", value="Unable to create or retrieve invite", inline=False)
            
            # Get role info
            roles = len(guild.roles)
            top_roles = ", ".join(r.name for r in sorted(guild.roles, key=lambda r: r.position, reverse=True)[:5])
            
            embed.add_field(name=f"Roles ({roles})", value=f"Top roles: {top_roles}", inline=False)
            
            # Bot role and permissions
            bot_member = guild.me
            bot_roles = ", ".join(r.name for r in bot_member.roles[1:]) or "None"
            is_admin = bot_member.guild_permissions.administrator
            
            important_perms = []
            if bot_member.guild_permissions.ban_members:
                important_perms.append("Ban Members")
            if bot_member.guild_permissions.kick_members:
                important_perms.append("Kick Members")
            if bot_member.guild_permissions.manage_messages:
                important_perms.append("Manage Messages")
            if bot_member.guild_permissions.mention_everyone:
                important_perms.append("Mention Everyone")
            
            permissions_str = ", ".join(important_perms) if important_perms else "None significant"
            
            embed.add_field(
                name="Bot Permissions", 
                value=f"Admin: {'✅' if is_admin else '❌'}\nPermissions: {permissions_str}\nRoles: {bot_roles}", 
                inline=False
            )
            
            # When bot joined
            joined_at = bot_member.joined_at
            if joined_at:
                embed.add_field(name="Bot Joined", value=f"<t:{int(joined_at.timestamp())}:R>", inline=True)
            
            embed.set_footer(text="Bot will automatically leave this guild")
            
            return embed
            
        except Exception as e:
            self.logger.error(f"Error creating info embed for guild {guild.id}: {e}", exc_info=True)
            
            # Simple error embed
            error_embed = disnake.Embed(
                title=f"⚠️ Unauthorized Guild Joined: {guild.name}",
                description=f"ID: {guild.id}\nError retrieving details: {str(e)}",
                color=disnake.Color.dark_red(),
                timestamp=datetime.datetime.utcnow()
            )
            error_embed.set_footer(text="Bot will automatically leave this guild")
            
            return error_embed
    
    async def notify_owner(self, guild):
        """Sends a notification to the bot owner about an unauthorized guild"""
        if not self.owner_id:
            self.logger.error("Cannot notify owner: owner_id not set")
            return False
            
        try:
            # Get the owner user object
            owner = await self.bot.fetch_user(self.owner_id)
            if not owner:
                self.logger.error(f"Cannot notify owner: User with ID {self.owner_id} not found")
                return False
                
            # Create the guild info embed
            embed = await self.get_guild_info_embed(guild)
            
            # Send DM to owner
            await owner.send(embed=embed)
            self.logger.info(f"Notified owner about unauthorized guild: {guild.id} ({guild.name})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to notify owner about guild {guild.id}: {e}", exc_info=True)
            return False
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Triggered when the bot joins a new guild"""
        self.logger.info(f"Bot joined guild: {guild.id} ({guild.name}) - Members: {guild.member_count}")
        
        # Check if this is an authorized guild
        if guild.id in self.authorized_guilds:
            self.logger.info(f"Guild {guild.id} ({guild.name}) is authorized, staying")
            return
            
        # Guild is not authorized - notify owner and leave
        self.logger.warning(f"Guild {guild.id} ({guild.name}) is not authorized, preparing to leave")
        
        # Notify owner first
        await self.notify_owner(guild)
        
        # Wait a brief period to ensure the owner gets the notification
        # and to avoid looking like the bot instantly left
        await asyncio.sleep(5)
        
        # Leave the guild
        try:
            await guild.leave()
            self.logger.warning(f"Left unauthorized guild: {guild.id} ({guild.name})")
        except Exception as e:
            self.logger.error(f"Failed to leave unauthorized guild {guild.id}: {e}", exc_info=True)
    
    @commands.command(name="checkallguilds")
    @commands.is_owner()
    async def check_all_guilds(self, ctx):
        """Checks all current guilds and leaves unauthorized ones"""
        # Get all guilds the bot is in
        all_guilds = self.bot.guilds
        
        # Filter unauthorized guilds
        unauthorized_guilds = [g for g in all_guilds if g.id not in self.authorized_guilds]
        
        if not unauthorized_guilds:
            return await ctx.send("✅ Bot is only in authorized guilds.")
        
        # Initial status message
        status_msg = await ctx.send(f"Found **{len(unauthorized_guilds)}** unauthorized guilds. Processing...")
        
        # Process each unauthorized guild
        for i, guild in enumerate(unauthorized_guilds):
            # Update status periodically
            if i % 2 == 0:
                await status_msg.edit(content=f"Found **{len(unauthorized_guilds)}** unauthorized guilds. Processing... ({i+1}/{len(unauthorized_guilds)})")
            
            # Notify owner about the guild
            await self.notify_owner(guild)
            
            # Leave the guild
            try:
                await guild.leave()
                self.logger.warning(f"Left unauthorized guild: {guild.id} ({guild.name})")
            except Exception as e:
                self.logger.error(f"Failed to leave unauthorized guild {guild.id}: {e}", exc_info=True)
            
            # Brief delay to prevent rate limiting
            await asyncio.sleep(2)
        
        # Final update
        await status_msg.edit(content=f"✅ Processed all **{len(unauthorized_guilds)}** unauthorized guilds. Bot has left them.")

    @commands.Cog.listener()
    async def on_ready(self):
        """Check all guilds when the bot starts up"""
        self.logger.info("Performing startup guild audit...")
        
        # Get all guilds the bot is in
        all_guilds = self.bot.guilds
        
        # Filter unauthorized guilds
        unauthorized_guilds = [g for g in all_guilds if g.id not in self.authorized_guilds]
        
        if not unauthorized_guilds:
            self.logger.info("Startup audit: Bot is only in authorized guilds.")
            return
        
        self.logger.warning(f"Startup audit: Found {len(unauthorized_guilds)} unauthorized guilds, will notify owner and leave")
        
        # Process each unauthorized guild
        for guild in unauthorized_guilds:
            # Notify owner about the guild
            await self.notify_owner(guild)
            
            # Leave the guild
            try:
                await guild.leave()
                self.logger.warning(f"Left unauthorized guild: {guild.id} ({guild.name})")
            except Exception as e:
                self.logger.error(f"Failed to leave unauthorized guild {guild.id}: {e}", exc_info=True)
            
            # Brief delay to prevent rate limiting
            await asyncio.sleep(2)
            
        self.logger.info(f"Startup audit complete: Left {len(unauthorized_guilds)} unauthorized guilds")

def setup(bot):
    bot.add_cog(AutoGuildCheckerCog(bot))