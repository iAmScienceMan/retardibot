import disnake
from disnake.ext import commands
import datetime
import asyncio

class GuildAuditCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.dev_logger.getChild('guild_audit')
        self.authorized_guilds = [1351605814623866920, 1342693545819115560]
        
    @commands.command(name="auditguilds", aliases=["checkguilds"])
    @commands.is_owner()
    async def audit_guilds(self, ctx):
        """Retrieves information about unauthorized guilds the bot is in"""
        
        # Get list of all guilds the bot is in
        all_guilds = self.bot.guilds
        
        # Filter out authorized guilds
        unauthorized_guilds = [g for g in all_guilds if g.id not in self.authorized_guilds]
        
        if not unauthorized_guilds:
            return await ctx.send("✅ Bot is only in authorized guilds.")
        
        # Create initial message
        embed = disnake.Embed(
            title="Unauthorized Guild Audit",
            description=f"Found **{len(unauthorized_guilds)}** unauthorized guilds. Collecting details...",
            color=disnake.Color.orange(),
            timestamp=datetime.datetime.utcnow()
        )
        message = await ctx.send(embed=embed)
        
        # Create detailed embeds for each unauthorized guild
        embeds = []
        
        for i, guild in enumerate(unauthorized_guilds):
            try:
                # Update status message periodically
                if i % 2 == 0:
                    status_embed = disnake.Embed(
                        title="Unauthorized Guild Audit",
                        description=f"Found **{len(unauthorized_guilds)}** unauthorized guilds.\n"
                                  f"Collecting details... ({i+1}/{len(unauthorized_guilds)})",
                        color=disnake.Color.orange(),
                        timestamp=datetime.datetime.utcnow()
                    )
                    await message.edit(embed=status_embed)
                
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
                            invite = await invite_channel.create_invite(reason="Bot owner audit", max_age=3600)  # 1 hour invite
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
                guild_embed = disnake.Embed(
                    title=f"Guild: {guild.name}",
                    description=f"ID: {guild.id}\nCreated: <t:{int(guild.created_at.timestamp())}:R>",
                    color=disnake.Color.red()
                )
                
                if guild.icon:
                    guild_embed.set_thumbnail(url=guild.icon.url)
                
                guild_embed.add_field(name="Owner", value=owner_info, inline=False)
                guild_embed.add_field(name="Channels", value=f"Text: {text_channels}\nVoice: {voice_channels}", inline=True)
                guild_embed.add_field(name="Members", value=f"Total: {total_members}\nOnline: {online_members}\nHumans: {human_count}\nBots: {bot_count}", inline=True)
                
                if invite:
                    guild_embed.add_field(name="Invite Link", value=str(invite), inline=False)
                else:
                    guild_embed.add_field(name="Invite Link", value="Unable to create or retrieve invite", inline=False)
                
                # Get role info
                roles = len(guild.roles)
                top_roles = ", ".join(r.name for r in sorted(guild.roles, key=lambda r: r.position, reverse=True)[:5])
                
                guild_embed.add_field(name=f"Roles ({roles})", value=f"Top roles: {top_roles}", inline=False)
                
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
                
                guild_embed.add_field(
                    name="Bot Permissions", 
                    value=f"Admin: {'✅' if is_admin else '❌'}\nPermissions: {permissions_str}\nRoles: {bot_roles}", 
                    inline=False
                )
                
                # When bot joined
                joined_at = bot_member.joined_at
                if joined_at:
                    guild_embed.add_field(name="Bot Joined", value=f"<t:{int(joined_at.timestamp())}:R>", inline=True)
                
                # Add command to leave
                guild_embed.set_footer(text=f"Use 'rb leaveguild {guild.id}' to leave this guild")
                
                embeds.append(guild_embed)
                
                # Brief delay to prevent rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error getting details for guild {guild.id}: {e}", exc_info=True)
                
                # Add error embed
                error_embed = disnake.Embed(
                    title=f"Guild: {guild.name}",
                    description=f"ID: {guild.id}\nError retrieving details: {str(e)}",
                    color=disnake.Color.dark_red()
                )
                embeds.append(error_embed)
        
        # Update final status message
        final_embed = disnake.Embed(
            title="Unauthorized Guild Audit Complete",
            description=f"Found **{len(unauthorized_guilds)}** unauthorized guilds.\nDetailed information follows below.",
            color=disnake.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )
        await message.edit(embed=final_embed)
        
        # Send all guild embeds
        for embed in embeds:
            await ctx.send(embed=embed)
            await asyncio.sleep(0.5)  # Brief delay to prevent spam
            
    @commands.command(name="leaveguild")
    @commands.is_owner()
    async def leave_guild(self, ctx, guild_id: int):
        """Makes the bot leave the specified guild"""
        guild = self.bot.get_guild(guild_id)
        
        if not guild:
            return await ctx.send(f"Guild with ID {guild_id} not found.")
        
        # Check if this is an unauthorized guild
        if guild.id in self.authorized_guilds:
            confirm_msg = await ctx.send(f"⚠️ **Warning**: {guild.name} is an authorized guild. Are you sure you want to leave? (yes/no)")
            
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["yes", "no"]
            
            try:
                response = await self.bot.wait_for("message", check=check, timeout=30.0)
                if response.content.lower() != "yes":
                    return await ctx.send("Guild departure cancelled.")
            except asyncio.TimeoutError:
                return await ctx.send("Command timed out.")
        
        # Get guild info for confirmation
        guild_name = guild.name
        member_count = guild.member_count
        
        try:
            await guild.leave()
            await ctx.send(f"✅ Successfully left guild: {guild_name} (ID: {guild_id}) with {member_count} members.")
            self.logger.warning(f"Left guild {guild_id} ({guild_name}) by command from {ctx.author}")
        except Exception as e:
            await ctx.send(f"❌ Error leaving guild: {e}")
            self.logger.error(f"Error leaving guild {guild_id}: {e}")
    
    @commands.command(name="listguilds")
    @commands.is_owner()
    async def list_all_guilds(self, ctx):
        """Lists all guilds the bot is in with basic info"""
        guilds = self.bot.guilds
        
        embed = disnake.Embed(
            title="Guild Listing",
            description=f"Bot is in {len(guilds)} guilds",
            color=disnake.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )
        
        # Group guilds by authorized status
        authorized = []
        unauthorized = []
        
        for guild in guilds:
            if guild.id in self.authorized_guilds:
                authorized.append(guild)
            else:
                unauthorized.append(guild)
                
        # Add field for authorized guilds
        if authorized:
            auth_text = "\n".join(f"• {g.name} ({g.id}) - {g.member_count} members" for g in authorized)
            embed.add_field(name=f"✅ Authorized Guilds ({len(authorized)})", value=auth_text, inline=False)
        else:
            embed.add_field(name="✅ Authorized Guilds (0)", value="Bot is not in any authorized guilds", inline=False)
            
        # Add field for unauthorized guilds
        if unauthorized:
            unauth_text = "\n".join(f"• {g.name} ({g.id}) - {g.member_count} members" for g in unauthorized)
            embed.add_field(name=f"❌ Unauthorized Guilds ({len(unauthorized)})", value=unauth_text, inline=False)
        else:
            embed.add_field(name="❌ Unauthorized Guilds (0)", value="No unauthorized guilds found", inline=False)
            
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(GuildAuditCog(bot))