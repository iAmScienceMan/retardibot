import disnake
from disnake.ext import commands
import datetime
import sqlite3
import os
import tomli
import tomli_w
import json
from typing import Optional, Union
from cogs.common.base_cog import BaseCog


class LoggingCog(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.db_path = "logs.db"
        self._create_tables()

        # Load config settings
        self.config = getattr(self.bot, 'config', {}).get("logging", {})
        self.enabled = self.config.get("enabled", True)
        self.log_channel_id = self.config.get("log_channel_id")
        self.ignored_channels = self.config.get("ignored_channels", [])
        self.ignored_users = self.config.get("ignored_users", [])

        # Event types to log
        self.log_events = self.config.get("log_events", {
            "message_delete": True,
            "message_edit": True,
            "member_join": True,
            "member_leave": True,
            "member_update": True,
            "channel_create": True,
            "channel_delete": True,
            "role_create": True,
            "role_delete": True,
            "voice_state_update": True
        })

        self.logger.info(
            f"Discord Logging is {'enabled' if self.enabled else 'disabled'}")

    def _create_tables(self):
        """Create the necessary database tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Message logs table
        c.execute('''
        CREATE TABLE IF NOT EXISTS message_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT,
            attachments TEXT,
            embeds TEXT,
            action_type TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # User logs table (joins, leaves, role changes, etc)
        c.execute('''
        CREATE TABLE IF NOT EXISTS user_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Server logs table (channel/role changes, etc)
        c.execute('''
        CREATE TABLE IF NOT EXISTS server_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            target_id INTEGER,
            details TEXT,
            user_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        conn.commit()
        conn.close()

    async def get_log_channel(self,
                              guild_id: int) -> Optional[disnake.TextChannel]:
        """Get the logging channel for a guild"""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return None

        # Check for guild-specific override in config
        guild_config = self.config.get(
            "guild_settings", {}).get(
            str(guild_id), {})
        channel_id = guild_config.get("log_channel_id", self.log_channel_id)

        if not channel_id:
            return None

        return guild.get_channel(channel_id)

    async def is_logging_enabled(self, guild_id: int, event_type: str) -> bool:
        """Check if logging is enabled for this guild and event type"""
        if not self.enabled:
            return False

        # Check for guild-specific settings
        guild_config = self.config.get(
            "guild_settings", {}).get(
            str(guild_id), {})

        # Check if the entire logging system is disabled for this guild
        if guild_config.get("enabled") is False:
            return False

        # Check if this specific event type is disabled
        guild_events = guild_config.get("log_events", {})
        if event_type in guild_events and not guild_events[event_type]:
            return False

        # Fall back to global settings
        return self.log_events.get(event_type, True)

    def should_ignore(self, channel_id: int = None,
                      user_id: int = None) -> bool:
        """Check if a channel or user should be ignored"""
        if channel_id and channel_id in self.ignored_channels:
            return True

        if user_id and user_id in self.ignored_users:
            return True

        return False

    async def log_to_channel(
            self,
            guild_id: int,
            embed: disnake.Embed) -> bool:
        """Send a log embed to the logging channel"""
        channel = await self.get_log_channel(guild_id)
        if not channel:
            return False

        try:
            await channel.send(embed=embed)
            return True
        except (disnake.Forbidden, disnake.HTTPException):
            return False

    def log_to_db(self, log_type: str, data: dict) -> bool:
        """Save a log entry to the database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        try:
            if log_type == "message":
                c.execute(
                    '''
                INSERT INTO message_logs (guild_id, channel_id, message_id, user_id, content,
                attachments, embeds, action_type, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                    (data.get("guild_id"),
                     data.get("channel_id"),
                        data.get("message_id"),
                        data.get("user_id"),
                        data.get("content"),
                        json.dumps(
                        data.get(
                            "attachments",
                            [])),
                        json.dumps(
                        data.get(
                            "embeds",
                            [])),
                        data.get("action_type"),
                        data.get(
                        "timestamp",
                        datetime.datetime.utcnow().isoformat())))
            elif log_type == "user":
                c.execute(
                    '''
                INSERT INTO user_logs (guild_id, user_id, action_type, details, timestamp)
                VALUES (?, ?, ?, ?, ?)
                ''',
                    (data.get("guild_id"),
                     data.get("user_id"),
                        data.get("action_type"),
                        json.dumps(
                        data.get(
                            "details",
                            {})),
                        data.get(
                        "timestamp",
                        datetime.datetime.utcnow().isoformat())))
            elif log_type == "server":
                c.execute(
                    '''
                INSERT INTO server_logs (guild_id, action_type, target_id, details, user_id, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                    (data.get("guild_id"),
                     data.get("action_type"),
                        data.get("target_id"),
                        json.dumps(
                        data.get(
                            "details",
                            {})),
                        data.get("user_id"),
                        data.get(
                        "timestamp",
                        datetime.datetime.utcnow().isoformat())))

            conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error logging to database: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # Message Events
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or self.should_ignore(
                message.channel.id, message.author.id):
            return

        if not await self.is_logging_enabled(message.guild.id, "message_delete"):
            return

        # Create embed for Discord logging
        embed = disnake.Embed(
            title="Message Deleted",
            description=f"**Author:** {
                message.author.mention} ({
                message.author.id})\n**Channel:** {
                message.channel.mention}",
            color=disnake.Color.red(),
            timestamp=datetime.datetime.utcnow())

        if message.content:
            if len(message.content) > 1024:
                embed.add_field(name="Content (Truncated)",
                                value=message.content[:1021] + "...",
                                inline=False)
            else:
                embed.add_field(
                    name="Content",
                    value=message.content,
                    inline=False)

        if message.attachments:
            attachment_urls = [
                attachment.proxy_url for attachment in message.attachments]
            embed.add_field(name=f"Attachments ({len(message.attachments)})", value="\n".join(
                attachment_urls[:3]) + ("\n..." if len(attachment_urls) > 3 else ""), inline=False)

        embed.set_footer(text=f"Message ID: {message.id}")

        # Log to channel
        await self.log_to_channel(message.guild.id, embed)

        # Log to database
        attachments_data = [{"url": a.proxy_url, "filename": a.filename}
                            for a in message.attachments]
        embeds_data = [e.to_dict()
                       for e in message.embeds] if message.embeds else []

        self.log_to_db("message", {
            "guild_id": message.guild.id,
            "channel_id": message.channel.id,
            "message_id": message.id,
            "user_id": message.author.id,
            "content": message.content,
            "attachments": attachments_data,
            "embeds": embeds_data,
            "action_type": "DELETE"
        })

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or self.should_ignore(
                before.channel.id, before.author.id):
            return

        if not await self.is_logging_enabled(before.guild.id, "message_edit"):
            return

        # Skip if content didn't change (e.g. embed loading)
        if before.content == after.content:
            return

        # Create embed for Discord logging
        embed = disnake.Embed(
            title="Message Edited",
            description=f"**Author:** {
                before.author.mention} ({
                before.author.id})\n**Channel:** {
                before.channel.mention}\n**[Jump to Message]({
                    after.jump_url})**",
            color=disnake.Color.gold(),
            timestamp=datetime.datetime.utcnow())

        if before.content:
            before_content = before.content[:1021] + \
                "..." if len(before.content) > 1024 else before.content
            embed.add_field(
                name="Before",
                value=before_content or "*Empty*",
                inline=False)

        if after.content:
            after_content = after.content[:1021] + \
                "..." if len(after.content) > 1024 else after.content
            embed.add_field(
                name="After",
                value=after_content or "*Empty*",
                inline=False)

        embed.set_footer(text=f"Message ID: {before.id}")

        # Log to channel
        await self.log_to_channel(before.guild.id, embed)

        # Log to database
        self.log_to_db("message", {
            "guild_id": before.guild.id,
            "channel_id": before.channel.id,
            "message_id": before.id,
            "user_id": before.author.id,
            "content": f"BEFORE: {before.content}\nAFTER: {after.content}",
            "attachments": [],
            "embeds": [],
            "action_type": "EDIT"
        })

    # Member Events
    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot or self.should_ignore(user_id=member.id):
            return

        if not await self.is_logging_enabled(member.guild.id, "member_join"):
            return

        # Calculate account age
        created_at = member.created_at
        account_age = datetime.datetime.utcnow() - created_at

        # Create embed for Discord logging
        embed = disnake.Embed(
            title="Member Joined",
            description=f"{member.mention} ({member.id})",
            color=disnake.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )

        embed.add_field(name="Account Created",
                        value=f"<t:{int(created_at.timestamp())}:R>",
                        inline=True)
        embed.add_field(
            name="Account Age",
            value=f"{
                account_age.days} days",
            inline=True)

        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)

        embed.set_footer(text=f"Member Count: {member.guild.member_count}")

        # Log to channel
        await self.log_to_channel(member.guild.id, embed)

        # Log to database
        self.log_to_db("user", {
            "guild_id": member.guild.id,
            "user_id": member.id,
            "action_type": "JOIN",
            "details": {
                "username": str(member),
                "created_at": created_at.isoformat(),
                "joined_at": member.joined_at.isoformat() if member.joined_at else None
            }
        })

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.bot or self.should_ignore(user_id=member.id):
            return

        if not await self.is_logging_enabled(member.guild.id, "member_leave"):
            return

        # Calculate time in server
        joined_at = member.joined_at
        if joined_at:
            time_in_server = datetime.datetime.utcnow() - joined_at
            time_in_server_str = f"{time_in_server.days} days"
        else:
            time_in_server_str = "Unknown"

        # Get roles
        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        roles_str = ", ".join(roles) if roles else "None"

        # Create embed for Discord logging
        embed = disnake.Embed(
            title="Member Left",
            description=f"{member} ({member.id})",
            color=disnake.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )

        if joined_at:
            embed.add_field(name="Joined At",
                            value=f"<t:{int(joined_at.timestamp())}:R>",
                            inline=True)

        embed.add_field(
            name="Time in Server",
            value=time_in_server_str,
            inline=True)

        if roles:
            embed.add_field(name="Roles", value=roles_str[:1024], inline=False)

        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)

        embed.set_footer(text=f"Member Count: {member.guild.member_count}")

        # Log to channel
        await self.log_to_channel(member.guild.id, embed)

        # Log to database
        self.log_to_db("user", {
            "guild_id": member.guild.id,
            "user_id": member.id,
            "action_type": "LEAVE",
            "details": {
                "username": str(member),
                "joined_at": joined_at.isoformat() if joined_at else None,
                "roles": [role.id for role in member.roles if role.name != "@everyone"]
            }
        })

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.bot or self.should_ignore(user_id=before.id):
            return

        if not await self.is_logging_enabled(before.guild.id, "member_update"):
            return

        # Check for nickname change
        if before.nick != after.nick:
            embed = disnake.Embed(
                title="Nickname Changed",
                description=f"**User:** {after.mention} ({after.id})",
                color=disnake.Color.blue(),
                timestamp=datetime.datetime.utcnow()
            )

            embed.add_field(
                name="Before",
                value=before.nick or "*None*",
                inline=True)
            embed.add_field(
                name="After",
                value=after.nick or "*None*",
                inline=True)

            if after.avatar:
                embed.set_thumbnail(url=after.avatar.url)

            # Log to channel
            await self.log_to_channel(before.guild.id, embed)

            # Log to database
            self.log_to_db("user", {
                "guild_id": before.guild.id,
                "user_id": before.id,
                "action_type": "NICKNAME_CHANGE",
                "details": {
                    "before": before.nick,
                    "after": after.nick
                }
            })

        # Check for role changes
        before_roles = set(before.roles)
        after_roles = set(after.roles)

        # Roles added
        added_roles = after_roles - before_roles
        if added_roles:
            role_mentions = [role.mention for role in added_roles]
            role_ids = [role.id for role in added_roles]

            embed = disnake.Embed(
                title="Roles Added",
                description=f"**User:** {after.mention} ({after.id})\n**Roles:** {', '.join(role_mentions)}",
                color=disnake.Color.green(),
                timestamp=datetime.datetime.utcnow()
            )

            if after.avatar:
                embed.set_thumbnail(url=after.avatar.url)

            # Log to channel
            await self.log_to_channel(before.guild.id, embed)

            # Log to database
            self.log_to_db("user", {
                "guild_id": before.guild.id,
                "user_id": before.id,
                "action_type": "ROLE_ADD",
                "details": {
                    "roles": role_ids
                }
            })

        # Roles removed
        removed_roles = before_roles - after_roles
        if removed_roles:
            role_mentions = [role.mention for role in removed_roles]
            role_ids = [role.id for role in removed_roles]

            embed = disnake.Embed(
                title="Roles Removed",
                description=f"**User:** {after.mention} ({after.id})\n**Roles:** {', '.join(role_mentions)}",
                color=disnake.Color.orange(),
                timestamp=datetime.datetime.utcnow()
            )

            if after.avatar:
                embed.set_thumbnail(url=after.avatar.url)

            # Log to channel
            await self.log_to_channel(before.guild.id, embed)

            # Log to database
            self.log_to_db("user", {
                "guild_id": before.guild.id,
                "user_id": before.id,
                "action_type": "ROLE_REMOVE",
                "details": {
                    "roles": role_ids
                }
            })

    # Channel Events
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if self.should_ignore(channel_id=channel.id):
            return

        if not await self.is_logging_enabled(channel.guild.id, "channel_create"):
            return

        # Create embed for Discord logging
        embed = disnake.Embed(
            title=f"{channel.type.name.capitalize()} Channel Created",
            description=f"**Name:** {channel.name}\n**ID:** {channel.id}",
            color=disnake.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )

        # Get the audit log entry to see who created the channel
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=disnake.AuditLogAction.channel_create):
                if entry.target.id == channel.id:
                    embed.add_field(
                        name="Created By", value=f"{
                            entry.user.mention} ({
                            entry.user.id})", inline=False)
                    break
        except (disnake.Forbidden, disnake.HTTPException):
            pass

        # Log to channel
        await self.log_to_channel(channel.guild.id, embed)

        # Log to database
        details = {
            "name": channel.name, "type": str(
                channel.type), "category": channel.category.name if hasattr(
                channel, "category") and channel.category else None}

        self.log_to_db("server", {
            "guild_id": channel.guild.id,
            "action_type": "CHANNEL_CREATE",
            "target_id": channel.id,
            "details": details
        })

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if self.should_ignore(channel_id=channel.id):
            return

        if not await self.is_logging_enabled(channel.guild.id, "channel_delete"):
            return

        # Create embed for Discord logging
        embed = disnake.Embed(
            title=f"{channel.type.name.capitalize()} Channel Deleted",
            description=f"**Name:** {channel.name}\n**ID:** {channel.id}",
            color=disnake.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )

        # Get the audit log entry to see who deleted the channel
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=disnake.AuditLogAction.channel_delete):
                if entry.target.id == channel.id:
                    embed.add_field(
                        name="Deleted By", value=f"{
                            entry.user.mention} ({
                            entry.user.id})", inline=False)
                    break
        except (disnake.Forbidden, disnake.HTTPException):
            pass

        # Log to channel
        await self.log_to_channel(channel.guild.id, embed)

        # Log to database
        details = {
            "name": channel.name, "type": str(
                channel.type), "category": channel.category.name if hasattr(
                channel, "category") and channel.category else None}

        self.log_to_db("server", {
            "guild_id": channel.guild.id,
            "action_type": "CHANNEL_DELETE",
            "target_id": channel.id,
            "details": details
        })

    # Role Events
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        if not await self.is_logging_enabled(role.guild.id, "role_create"):
            return

        # Create embed for Discord logging
        embed = disnake.Embed(
            title="Role Created",
            description=f"**Name:** {role.name}\n**ID:** {role.id}",
            color=role.color,
            timestamp=datetime.datetime.utcnow()
        )

        # Get the audit log entry to see who created the role
        try:
            async for entry in role.guild.audit_logs(limit=1, action=disnake.AuditLogAction.role_create):
                if entry.target.id == role.id:
                    embed.add_field(
                        name="Created By", value=f"{
                            entry.user.mention} ({
                            entry.user.id})", inline=False)
                    break
        except (disnake.Forbidden, disnake.HTTPException):
            pass

        # Log permissions if any
        if role.permissions.value:
            permissions = [
                perm[0].replace(
                    '_',
                    ' ').title() for perm in role.permissions if perm[1]]
            if permissions:
                perm_text = ", ".join(permissions)
                if len(perm_text) > 1024:
                    perm_text = perm_text[:1021] + "..."
                embed.add_field(
                    name="Permissions",
                    value=perm_text,
                    inline=False)

        # Log to channel
        await self.log_to_channel(role.guild.id, embed)

        # Log to database
        details = {
            "name": role.name,
            "color": str(role.color),
            "permissions": role.permissions.value,
            "position": role.position,
            "mentionable": role.mentionable,
            "hoist": role.hoist
        }

        self.log_to_db("server", {
            "guild_id": role.guild.id,
            "action_type": "ROLE_CREATE",
            "target_id": role.id,
            "details": details
        })

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        if not await self.is_logging_enabled(role.guild.id, "role_delete"):
            return

        # Create embed for Discord logging
        embed = disnake.Embed(
            title="Role Deleted",
            description=f"**Name:** {role.name}\n**ID:** {role.id}",
            color=role.color,
            timestamp=datetime.datetime.utcnow()
        )

        # Get the audit log entry to see who deleted the role
        try:
            async for entry in role.guild.audit_logs(limit=1, action=disnake.AuditLogAction.role_delete):
                if entry.target.id == role.id:
                    embed.add_field(
                        name="Deleted By", value=f"{
                            entry.user.mention} ({
                            entry.user.id})", inline=False)
                    break
        except (disnake.Forbidden, disnake.HTTPException):
            pass

        # Log to channel
        await self.log_to_channel(role.guild.id, embed)

        # Log to database
        details = {
            "name": role.name,
            "color": str(role.color),
            "permissions": role.permissions.value,
            "position": role.position,
            "mentionable": role.mentionable,
            "hoist": role.hoist
        }

        self.log_to_db("server", {
            "guild_id": role.guild.id,
            "action_type": "ROLE_DELETE",
            "target_id": role.id,
            "details": details
        })

    # Voice Events
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or self.should_ignore(user_id=member.id):
            return

        if not await self.is_logging_enabled(member.guild.id, "voice_state_update"):
            return

        # Check if the member joined, left, or moved voice channels
        action = None
        description = None

        if before.channel is None and after.channel is not None:
            action = "VOICE_JOIN"
            description = f"**User:** {
                member.mention} ({
                member.id})\n**Channel:** {
                after.channel.mention}"
        elif before.channel is not None and after.channel is None:
            action = "VOICE_LEAVE"
            description = f"**User:** {
                member.mention} ({
                member.id})\n**Channel:** {
                before.channel.mention}"
        elif before.channel != after.channel:
            action = "VOICE_MOVE"
            description = f"**User:** {
                member.mention} ({
                member.id})\n**From:** {
                before.channel.mention}\n**To:** {
                after.channel.mention}"
        else:
            # Check for other voice state changes like mute/deafen
            changes = []

            if before.deaf != after.deaf:
                server_action = "server deafened" if after.deaf else "server undeafened"
                changes.append(f"User was {server_action}")

            if before.mute != after.mute:
                server_action = "server muted" if after.mute else "server unmuted"
                changes.append(f"User was {server_action}")

            if before.self_deaf != after.self_deaf:
                self_action = "deafened themselves" if after.self_deaf else "undeafened themselves"
                changes.append(f"User {self_action}")

            if before.self_mute != after.self_mute:
                self_action = "muted themselves" if after.self_mute else "unmuted themselves"
                changes.append(f"User {self_action}")

            if before.self_stream != after.self_stream:
                stream_action = "started streaming" if after.self_stream else "stopped streaming"
                changes.append(f"User {stream_action}")

            if before.self_video != after.self_video:
                video_action = "turned on camera" if after.self_video else "turned off camera"
                changes.append(f"User {video_action}")

            if changes:
                action = "VOICE_UPDATE"
                description = f"**User:** {
                    member.mention} ({
                    member.id})\n**Channel:** {
                    after.channel.mention if after.channel else before.channel.mention}\n**Changes:**\n- " + "\n- ".join(changes)

        if action:
            # Create embed for Discord logging
            title_map = {
                "VOICE_JOIN": "User Joined Voice Channel",
                "VOICE_LEAVE": "User Left Voice Channel",
                "VOICE_MOVE": "User Moved Voice Channels",
                "VOICE_UPDATE": "Voice State Updated"
            }

            color_map = {
                "VOICE_JOIN": disnake.Color.green(),
                "VOICE_LEAVE": disnake.Color.red(),
                "VOICE_MOVE": disnake.Color.blue(),
                "VOICE_UPDATE": disnake.Color.gold()
            }

            embed = disnake.Embed(
                title=title_map.get(action, "Voice Update"),
                description=description,
                color=color_map.get(action, disnake.Color.blue()),
                timestamp=datetime.datetime.utcnow()
            )

            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)

            # Log to channel
            await self.log_to_channel(member.guild.id, embed)

            # Log to database
            details = {
                "before_channel": before.channel.id if before.channel else None,
                "after_channel": after.channel.id if after.channel else None,
                "before_mute": before.mute,
                "after_mute": after.mute,
                "before_deaf": before.deaf,
                "after_deaf": after.deaf,
                "before_self_mute": before.self_mute,
                "after_self_mute": after.self_mute,
                "before_self_deaf": before.self_deaf,
                "after_self_deaf": after.self_deaf,
                "before_self_stream": before.self_stream,
                "after_self_stream": after.self_stream,
                "before_self_video": before.self_video,
                "after_self_video": after.self_video}

            self.log_to_db("user", {
                "guild_id": member.guild.id,
                "user_id": member.id,
                "action_type": action,
                "details": details
            })

   # Commands for managing logs
    @commands.group(name="logs", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def logs(self, ctx):
        """Manage server logs"""
        await ctx.send("Please use a subcommand: `setup`, `enable`, `disable`, `channel`, `ignore`, `unignore`, `status`")

    @logs.command(name="setup")
    @commands.has_permissions(manage_guild=True)
    async def logs_setup(self, ctx, channel: disnake.TextChannel = None):
        """Setup logging channel for this server"""
        if not channel:
            channel = ctx.channel

        # Update config
        guild_id = str(ctx.guild.id)

        if "guild_settings" not in self.config:
            self.config["guild_settings"] = {}

        if guild_id not in self.config["guild_settings"]:
            self.config["guild_settings"][guild_id] = {}

        self.config["guild_settings"][guild_id]["log_channel_id"] = channel.id
        self.config["guild_settings"][guild_id]["enabled"] = True

        # Save config changes
        self._save_config()

        await ctx.send(f"✅ Logging channel set to {channel.mention}")

    @logs.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    async def logs_enable(self, ctx, event_type: str = None):
        """Enable logging for all or a specific event type"""
        guild_id = str(ctx.guild.id)

        if "guild_settings" not in self.config:
            self.config["guild_settings"] = {}

        if guild_id not in self.config["guild_settings"]:
            self.config["guild_settings"][guild_id] = {}

        if event_type:
            # Enable specific event type
            event_type = event_type.lower()
            valid_events = [
                "message_delete",
                "message_edit",
                "member_join",
                "member_leave",
                "member_update",
                "channel_create",
                "channel_delete",
                "role_create",
                "role_delete",
                "voice_state_update"]

            if event_type not in valid_events:
                return await ctx.send(f"❌ Invalid event type. Valid types: {', '.join(valid_events)}")

            if "log_events" not in self.config["guild_settings"][guild_id]:
                self.config["guild_settings"][guild_id]["log_events"] = {}

            self.config["guild_settings"][guild_id]["log_events"][event_type] = True
            self._save_config()

            await ctx.send(f"✅ Enabled logging for event type: `{event_type}`")
        else:
            # Enable all logging
            self.config["guild_settings"][guild_id]["enabled"] = True
            self._save_config()

            await ctx.send("✅ Enabled logging for all events")

    @logs.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    async def logs_disable(self, ctx, event_type: str = None):
        """Disable logging for all or a specific event type"""
        guild_id = str(ctx.guild.id)

        if "guild_settings" not in self.config:
            self.config["guild_settings"] = {}

        if guild_id not in self.config["guild_settings"]:
            self.config["guild_settings"][guild_id] = {}

        if event_type:
            # Disable specific event type
            event_type = event_type.lower()
            valid_events = [
                "message_delete",
                "message_edit",
                "member_join",
                "member_leave",
                "member_update",
                "channel_create",
                "channel_delete",
                "role_create",
                "role_delete",
                "voice_state_update"]

            if event_type not in valid_events:
                return await ctx.send(f"❌ Invalid event type. Valid types: {', '.join(valid_events)}")

            if "log_events" not in self.config["guild_settings"][guild_id]:
                self.config["guild_settings"][guild_id]["log_events"] = {}

            self.config["guild_settings"][guild_id]["log_events"][event_type] = False
            self._save_config()

            await ctx.send(f"✅ Disabled logging for event type: `{event_type}`")
        else:
            # Disable all logging
            self.config["guild_settings"][guild_id]["enabled"] = False
            self._save_config()

            await ctx.send("✅ Disabled logging for all events")

    @logs.command(name="channel")
    @commands.has_permissions(manage_guild=True)
    async def logs_channel(self, ctx, channel: disnake.TextChannel):
        """Set the logging channel"""
        guild_id = str(ctx.guild.id)

        if "guild_settings" not in self.config:
            self.config["guild_settings"] = {}

        if guild_id not in self.config["guild_settings"]:
            self.config["guild_settings"][guild_id] = {}

        self.config["guild_settings"][guild_id]["log_channel_id"] = channel.id
        self._save_config()

        await ctx.send(f"✅ Logging channel set to {channel.mention}")

    @logs.command(name="ignore")
    @commands.has_permissions(manage_guild=True)
    async def logs_ignore(self,
                          ctx,
                          target: Union[disnake.TextChannel,
                                        disnake.Member,
                                        disnake.User,
                                        int]):
        """Ignore a channel or user from logging"""
        guild_id = str(ctx.guild.id)

        if "guild_settings" not in self.config:
            self.config["guild_settings"] = {}

        if guild_id not in self.config["guild_settings"]:
            self.config["guild_settings"][guild_id] = {}

        # Determine if target is a channel or user
        if isinstance(
            target,
            (disnake.TextChannel,
             disnake.VoiceChannel,
             disnake.CategoryChannel)):
            # Target is a channel
            if "ignored_channels" not in self.config["guild_settings"][guild_id]:
                self.config["guild_settings"][guild_id]["ignored_channels"] = []

            if target.id not in self.config["guild_settings"][guild_id]["ignored_channels"]:
                self.config["guild_settings"][guild_id]["ignored_channels"].append(
                    target.id)
                self._save_config()
                await ctx.send(f"✅ Now ignoring channel: {target.mention}")
            else:
                await ctx.send(f"Channel {target.mention} is already being ignored")
        else:
            # Target is a user or ID
            user_id = target.id if isinstance(
                target, (disnake.Member, disnake.User)) else target

            if "ignored_users" not in self.config["guild_settings"][guild_id]:
                self.config["guild_settings"][guild_id]["ignored_users"] = []

            if user_id not in self.config["guild_settings"][guild_id]["ignored_users"]:
                self.config["guild_settings"][guild_id]["ignored_users"].append(
                    user_id)
                self._save_config()

                user_mention = f"<@{user_id}>" if isinstance(
                    target, int) else target.mention
                await ctx.send(f"✅ Now ignoring user: {user_mention}")
            else:
                user_mention = f"<@{user_id}>" if isinstance(
                    target, int) else target.mention
                await ctx.send(f"User {user_mention} is already being ignored")

    @logs.command(name="unignore")
    @commands.has_permissions(manage_guild=True)
    async def logs_unignore(self,
                            ctx,
                            target: Union[disnake.TextChannel,
                                          disnake.Member,
                                          disnake.User,
                                          int]):
        """Stop ignoring a channel or user from logging"""
        guild_id = str(ctx.guild.id)

        if "guild_settings" not in self.config:
            self.config["guild_settings"] = {}

        if guild_id not in self.config["guild_settings"]:
            self.config["guild_settings"][guild_id] = {}

        # Determine if target is a channel or user
        if isinstance(
            target,
            (disnake.TextChannel,
             disnake.VoiceChannel,
             disnake.CategoryChannel)):
            # Target is a channel
            if "ignored_channels" not in self.config["guild_settings"][guild_id]:
                return await ctx.send(f"Channel {target.mention} is not being ignored")

            if target.id in self.config["guild_settings"][guild_id]["ignored_channels"]:
                self.config["guild_settings"][guild_id]["ignored_channels"].remove(
                    target.id)
                self._save_config()
                await ctx.send(f"✅ Stopped ignoring channel: {target.mention}")
            else:
                await ctx.send(f"Channel {target.mention} is not being ignored")
        else:
            # Target is a user or ID
            user_id = target.id if isinstance(
                target, (disnake.Member, disnake.User)) else target

            if "ignored_users" not in self.config["guild_settings"][guild_id]:
                return await ctx.send(f"User <@{user_id}> is not being ignored")

            if user_id in self.config["guild_settings"][guild_id]["ignored_users"]:
                self.config["guild_settings"][guild_id]["ignored_users"].remove(
                    user_id)
                self._save_config()

                user_mention = f"<@{user_id}>" if isinstance(
                    target, int) else target.mention
                await ctx.send(f"✅ Stopped ignoring user: {user_mention}")
            else:
                user_mention = f"<@{user_id}>" if isinstance(
                    target, int) else target.mention
                await ctx.send(f"User {user_mention} is not being ignored")

    @logs.command(name="status")
    @commands.has_permissions(manage_guild=True)
    async def logs_status(self, ctx):
        """Show current logging status and settings"""
        guild_id = str(ctx.guild.id)
        guild_settings = self.config.get(
            "guild_settings", {}).get(
            guild_id, {})

        # Check if logging is enabled
        enabled = guild_settings.get("enabled", self.enabled)
        log_channel_id = guild_settings.get(
            "log_channel_id", self.log_channel_id)
        log_channel = ctx.guild.get_channel(
            log_channel_id) if log_channel_id else None

        # Get event settings
        guild_events = guild_settings.get("log_events", {})
        event_statuses = []

        for event in [
            "message_delete", "message_edit", "member_join", "member_leave",
            "member_update", "channel_create", "channel_delete", "role_create",
            "role_delete", "voice_state_update"
        ]:
            if event in guild_events:
                status = "✅" if guild_events[event] else "❌"
            else:
                status = "✅" if self.log_events.get(event, True) else "❌"

            event_statuses.append(f"{status} `{event}`")

        # Get ignored channels and users
        ignored_channels = guild_settings.get("ignored_channels", [])
        ignored_users = guild_settings.get("ignored_users", [])

        ignored_channel_mentions = []
        for channel_id in ignored_channels:
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                ignored_channel_mentions.append(channel.mention)
            else:
                ignored_channel_mentions.append(f"<#{channel_id}>")

        ignored_user_mentions = []
        for user_id in ignored_users:
            user = ctx.guild.get_member(user_id)
            if user:
                ignored_user_mentions.append(user.mention)
            else:
                ignored_user_mentions.append(f"<@{user_id}>")

        # Create embed
        embed = disnake.Embed(
            title="Logging Status",
            color=disnake.Color.blue() if enabled else disnake.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )

        embed.add_field(
            name="Status",
            value="✅ Enabled" if enabled else "❌ Disabled",
            inline=False)

        if log_channel:
            embed.add_field(
                name="Log Channel",
                value=log_channel.mention,
                inline=False)
        else:
            embed.add_field(
                name="Log Channel",
                value="❌ Not set",
                inline=False)

        embed.add_field(
            name="Event Settings",
            value="\n".join(event_statuses),
            inline=False)

        if ignored_channel_mentions:
            embed.add_field(
                name="Ignored Channels",
                value=", ".join(ignored_channel_mentions[:10]) +
                      (f" and {len(ignored_channel_mentions) - 10} more" if len(ignored_channel_mentions) > 10 else ""),
                inline=False
            )

        if ignored_user_mentions:
            embed.add_field(
                name="Ignored Users",
                value=", ".join(ignored_user_mentions[:10]) +
                      (f" and {len(ignored_user_mentions) - 10} more" if len(ignored_user_mentions) > 10 else ""),
                inline=False
            )

        await ctx.send(embed=embed)

    def _save_config(self):
        """Save current config to the main bot config"""
        # Get the main config
        main_config = getattr(self.bot, 'config', {})

        # Update the logging section
        main_config["logging"] = self.config

        # Save to file
        try:
            with open("config.toml", "rb") as f:
                toml_config = tomli.load(f)
            
            # Update the config
            for key, value in main_config.items():
                toml_config[key] = value
            
            # Write back to file
            with open("config.toml", "wb") as f:
                tomli_w.dump(toml_config, f)
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")

        # Update the bot's config
        self.bot.config = main_config


def setup(bot):
    bot.add_cog(LoggingCog(bot))
