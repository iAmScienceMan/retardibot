import disnake
from disnake.ext import commands
import datetime
import asyncio
import json
from cogs.common.base_cog import BaseCog
from cogs.common.db_manager import DBManager

class ModerationCog(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.db = DBManager()
        # No need to create tables as DBManager handles this

    def _add_mod_action(self, guild_id, user_id, moderator_id, action_type, reason=None, duration=None):
        """Add a moderation action to the database"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                INSERT INTO mod_actions (guild_id, user_id, moderator_id, action_type, reason, duration)
                VALUES (%s, %s, %s, %s, %s, %s)
                ''', (guild_id, user_id, moderator_id, action_type, reason, duration))
                
                conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Database error in _add_mod_action: {e}")
        finally:
            self.db.release_connection(conn)

    def _get_user_history(self, guild_id, user_id, action_type=None):
        """Get a user's moderation history, optionally filtered by action type"""
        conn = self.db.get_connection()
        results = []
        
        try:
            with conn.cursor() as cursor:
                if action_type:
                    cursor.execute('''
                    SELECT * FROM mod_actions 
                    WHERE guild_id = %s AND user_id = %s AND action_type = %s
                    ORDER BY timestamp DESC
                    ''', (guild_id, user_id, action_type))
                else:
                    cursor.execute('''
                    SELECT * FROM mod_actions 
                    WHERE guild_id = %s AND user_id = %s
                    ORDER BY timestamp DESC
                    ''', (guild_id, user_id))
                    
                # Convert to dictionary format for compatibility
                columns = [desc[0] for desc in cursor.description]
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))
                    
        except Exception as e:
            self.logger.error(f"Database error in _get_user_history: {e}")
        finally:
            self.db.release_connection(conn)
            
        return results

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: disnake.Member, *, reason=None):
        """Kick a member from the server"""
        if ctx.author.top_role <= member.top_role:
            return await ctx.send("You cannot kick this user due to role hierarchy.")
        
        try:
            await member.send(f"You have been kicked from {ctx.guild.name} | Reason: {reason or 'No reason provided'}")
        except:
            pass  # Can't DM the user
            
        await member.kick(reason=reason)
        
        # Record the kick in the database
        self._add_mod_action(ctx.guild.id, member.id, ctx.author.id, "KICK", reason)
        
        await ctx.send(f"👢 **{member}** has been kicked | Reason: {reason or 'No reason provided'}")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: disnake.Member, *, reason=None):
        """Ban a member from the server"""
        if ctx.author.top_role <= member.top_role:
            return await ctx.send("You cannot ban this user due to role hierarchy.")
        
        try:
            await member.send(f"You have been banned from {ctx.guild.name} | Reason: {reason or 'No reason provided'}")
        except:
            pass  # Can't DM the user
            
        await member.ban(reason=reason)
        
        # Record the ban in the database
        self._add_mod_action(ctx.guild.id, member.id, ctx.author.id, "BAN", reason)
        
        await ctx.send(f"🔨 **{member}** has been banned | Reason: {reason or 'No reason provided'}")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, *, user_id_or_name):
        """Unban a user from the server"""
        bans = await ctx.guild.bans()
        
        unbanned_user = None
        
        if user_id_or_name.isdigit():
            # Search by ID
            user_id = int(user_id_or_name)
            for ban_entry in bans:
                if ban_entry.user.id == user_id:
                    await ctx.guild.unban(ban_entry.user)
                    unbanned_user = ban_entry.user
                    break
        else:
            # Search by name
            for ban_entry in bans:
                if user_id_or_name.lower() in str(ban_entry.user).lower():
                    await ctx.guild.unban(ban_entry.user)
                    unbanned_user = ban_entry.user
                    break
                    
        if unbanned_user:
            # Record the unban in the database
            self._add_mod_action(ctx.guild.id, unbanned_user.id, ctx.author.id, "UNBAN")
            await ctx.send(f"✅ **{unbanned_user}** has been unbanned")
        else:
            await ctx.send("User not found in ban list.")

    @commands.command(aliases=["mute"])
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: disnake.Member, duration: str, *, reason=None):
        """Timeout a member for a specified duration
        Duration format: 1d, 2h, 30m, 45s or combinations like 1d2h30m"""
        if ctx.author.top_role <= member.top_role:
            return await ctx.send("You cannot timeout this user due to role hierarchy.")
                
        # Parse duration
        total_seconds = 0
        current_num = ""
        for char in duration:
            if char.isdigit():
                current_num += char
            elif char == 'd' and current_num:
                total_seconds += int(current_num) * 86400  # days to seconds
                current_num = ""
            elif char == 'h' and current_num:
                total_seconds += int(current_num) * 3600  # hours to seconds
                current_num = ""
            elif char == 'm' and current_num:
                total_seconds += int(current_num) * 60  # minutes to seconds
                current_num = ""
            elif char == 's' and current_num:
                total_seconds += int(current_num)  # seconds
                current_num = ""
        
        if total_seconds == 0:
            return await ctx.send("Invalid duration format. Use combinations like: 1d, 2h, 30m, 45s")
                
        # Max timeout duration is 28 days
        if total_seconds > 2419200:
            total_seconds = 2419200
            
        try:
            # Use timedelta for the duration
            duration_timedelta = datetime.timedelta(seconds=total_seconds)
            
            # Apply the timeout using the correct method
            await member.timeout(duration=duration_timedelta, reason=reason)
            
            # Record the timeout in the database
            self._add_mod_action(ctx.guild.id, member.id, ctx.author.id, "TIMEOUT", reason, total_seconds)
            
            # Format duration for display
            days, remainder = divmod(total_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            duration_str = ""
            if days > 0:
                duration_str += f"{days}d "
            if hours > 0:
                duration_str += f"{hours}h "
            if minutes > 0:
                duration_str += f"{minutes}m "
            if seconds > 0:
                duration_str += f"{seconds}s"
                
            await ctx.send(f"⏱️ **{member}** has been timed out for {duration_str.strip()} | Reason: {reason or 'No reason provided'}")
        except disnake.Forbidden:
            await ctx.send("❌ I lack the necessary permissions to timeout this user.")
        except disnake.HTTPException as e:
            await ctx.send(f"❌ Failed to timeout user due to an API error: {e}")
        except Exception as e:
            await ctx.send(f"❌ An unexpected error occurred: {e}")

    @commands.command(aliases=["unmute"])
    @commands.has_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: disnake.Member, *, reason=None):
        """Remove timeout from a member"""
        try:
            # Use the correct method to remove timeout
            await member.timeout(duration=None, reason=reason)
            
            # Record the untimeout in the database
            self._add_mod_action(ctx.guild.id, member.id, ctx.author.id, "UNTIMEOUT", reason)
            
            await ctx.send(f"✅ Timeout removed from **{member}**" + (f" | Reason: {reason}" if reason else ""))
        except disnake.Forbidden:
            await ctx.send("❌ I lack the necessary permissions to remove this user's timeout.")
        except disnake.HTTPException as e:
            await ctx.send(f"❌ Failed to remove timeout due to an API error: {e}")
        except Exception as e:
            await ctx.send(f"❌ An unexpected error occurred: {e}")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: disnake.Member, *, reason=None):
        """Warn a member"""
        if ctx.author.top_role <= member.top_role:
            return await ctx.send("You cannot warn this user due to role hierarchy.")
            
        # Record the warning in the database
        self._add_mod_action(ctx.guild.id, member.id, ctx.author.id, "WARN", reason)
        
        try:
            await member.send(f"You have been warned in {ctx.guild.name} | Reason: {reason or 'No reason provided'}")
        except:
            pass  # Can't DM the user
            
        await ctx.send(f"⚠️ **{member}** has been warned | Reason: {reason or 'No reason provided'}")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clearwarns(self, ctx, member: disnake.Member):
        """Clear all warnings for a member"""
        conn = self.db.get_connection()
        deleted_rows = 0
        
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                DELETE FROM mod_actions
                WHERE guild_id = %s AND user_id = %s AND action_type = 'WARN'
                ''', (ctx.guild.id, member.id))
                
                deleted_rows = cursor.rowcount
                conn.commit()
                
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Database error in clearwarns: {e}")
            await ctx.send(f"❌ An error occurred: {e}")
            return
        finally:
            self.db.release_connection(conn)
        
        if deleted_rows > 0:
            await ctx.send(f"✅ Cleared {deleted_rows} warnings from **{member}**")
        else:
            await ctx.send(f"**{member}** has no warnings to clear.")

    @commands.command(aliases=["warns"])
    @commands.has_permissions(manage_messages=True)
    async def history(self, ctx, member: disnake.Member, page: int = 1):
        """View moderation history for a member with pagination"""
        history = self._get_user_history(ctx.guild.id, member.id)
        
        if not history:
            return await ctx.send(f"**{member}** has no moderation history.")
        
        # Define how many actions to show per page
        items_per_page = 5
        total_pages = (len(history) + items_per_page - 1) // items_per_page
        
        # Ensure page is within valid range
        page = max(1, min(page, total_pages))
        
        # Create embed for this page
        embed = self._create_history_embed(ctx, member, history, page, items_per_page, total_pages)
        
        # If only one page, just send the embed without buttons
        if total_pages <= 1:
            return await ctx.send(embed=embed)
        
        # Create view with navigation buttons
        view = disnake.ui.View()
        
        # First page button
        first_button = disnake.ui.Button(style=disnake.ButtonStyle.secondary, emoji="⏮️", disabled=(page == 1))
        first_button.callback = lambda interaction: self._update_history_page(interaction, ctx, member, history, 1, items_per_page, total_pages)
        view.add_item(first_button)
        
        # Previous page button
        prev_button = disnake.ui.Button(style=disnake.ButtonStyle.secondary, emoji="◀️", disabled=(page == 1))
        prev_button.callback = lambda interaction: self._update_history_page(interaction, ctx, member, history, page - 1, items_per_page, total_pages)
        view.add_item(prev_button)
        
        # Page indicator (not clickable)
        page_indicator = disnake.ui.Button(style=disnake.ButtonStyle.secondary, label=f"{page}/{total_pages}", disabled=True)
        view.add_item(page_indicator)
        
        # Next page button
        next_button = disnake.ui.Button(style=disnake.ButtonStyle.secondary, emoji="▶️", disabled=(page == total_pages))
        next_button.callback = lambda interaction: self._update_history_page(interaction, ctx, member, history, page + 1, items_per_page, total_pages)
        view.add_item(next_button)
        
        # Last page button
        last_button = disnake.ui.Button(style=disnake.ButtonStyle.secondary, emoji="⏭️", disabled=(page == total_pages))
        last_button.callback = lambda interaction: self._update_history_page(interaction, ctx, member, history, total_pages, items_per_page, total_pages)
        view.add_item(last_button)
        
        await ctx.send(embed=embed, view=view)

    def _create_history_embed(self, ctx, member, history, page, items_per_page, total_pages):
        """Helper method to create history embed for a specific page"""
        start_idx = (page - 1) * items_per_page
        end_idx = min(start_idx + items_per_page, len(history))
        current_page_items = history[start_idx:end_idx]
        
        embed = disnake.Embed(
            title=f"Moderation History for {member}", 
            color=disnake.Color.blue(),
            description=f"Total actions: {len(history)} | Page {page}/{total_pages}"
        )
        
        # Group by action type for summary display
        action_counts = {}
        for action in history:
            action_type = action['action_type']
            if action_type not in action_counts:
                action_counts[action_type] = 0
            action_counts[action_type] += 1
        
        # Add summary field
        summary = "\n".join([f"{action}: {count}" for action, count in action_counts.items()])
        embed.add_field(name="Summary", value=summary, inline=False)
        
        # Add the items for the current page
        if current_page_items:
            embed.add_field(name=f"Actions (Page {page})", value="", inline=False)
            
            for i, action in enumerate(current_page_items, start_idx + 1):
                moderator = ctx.guild.get_member(action['moderator_id']) or f"<@{action['moderator_id']}>"
                
                duration_str = ""
                if action['duration']:
                    days, remainder = divmod(action['duration'], 86400)
                    hours, remainder = divmod(remainder, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    if days > 0:
                        duration_str += f"{days}d "
                    if hours > 0:
                        duration_str += f"{hours}h "
                    if minutes > 0:
                        duration_str += f"{minutes}m "
                    if seconds > 0:
                        duration_str += f"{seconds}s"
                    
                    duration_str = f" for {duration_str.strip()}"
                
                # Format timestamp - PostgreSQL returns datetime objects
                timestamp = action['timestamp']
                if hasattr(timestamp, 'strftime'):
                    timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    timestamp_str = str(timestamp)
                
                embed.add_field(
                    name=f"{i}. {action['action_type']}{duration_str}",
                    value=f"**Reason:** {action['reason'] or 'No reason provided'}\n" + 
                        f"**By:** {moderator}\n" +
                        f"**Date:** {timestamp_str}",
                    inline=False
                )
        
        return embed

    async def _update_history_page(self, interaction, ctx, member, history, page, items_per_page, total_pages):
        """Callback method for updating history page when a button is clicked"""
        # Ensure page is within valid range
        page = max(1, min(page, total_pages))
        
        # Create updated embed
        embed = self._create_history_embed(ctx, member, history, page, items_per_page, total_pages)
        
        # Create updated view with navigation buttons
        view = disnake.ui.View()
        
        # First page button
        first_button = disnake.ui.Button(style=disnake.ButtonStyle.secondary, emoji="⏮️", disabled=(page == 1))
        first_button.callback = lambda i: self._update_history_page(i, ctx, member, history, 1, items_per_page, total_pages)
        view.add_item(first_button)
        
        # Previous page button
        prev_button = disnake.ui.Button(style=disnake.ButtonStyle.secondary, emoji="◀️", disabled=(page == 1))
        prev_button.callback = lambda i: self._update_history_page(i, ctx, member, history, page - 1, items_per_page, total_pages)
        view.add_item(prev_button)
        
        # Page indicator (not clickable)
        page_indicator = disnake.ui.Button(style=disnake.ButtonStyle.secondary, label=f"{page}/{total_pages}", disabled=True)
        view.add_item(page_indicator)
        
        # Next page button
        next_button = disnake.ui.Button(style=disnake.ButtonStyle.secondary, emoji="▶️", disabled=(page == total_pages))
        next_button.callback = lambda i: self._update_history_page(i, ctx, member, history, page + 1, items_per_page, total_pages)
        view.add_item(next_button)
        
        # Last page button
        last_button = disnake.ui.Button(style=disnake.ButtonStyle.secondary, emoji="⏭️", disabled=(page == total_pages))
        last_button.callback = lambda i: self._update_history_page(i, ctx, member, history, total_pages, items_per_page, total_pages)
        view.add_item(last_button)
        
        await interaction.response.edit_message(embed=embed, view=view)

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: disnake.TextChannel = None):
        """Lock a channel"""
        channel = channel or ctx.channel
        
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        
        # Record the channel lock in the database
        self._add_mod_action(ctx.guild.id, 0, ctx.author.id, "LOCK", f"Channel: {channel.name} ({channel.id})")
        
        await ctx.send(f"🔒 {channel.mention} has been locked")

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: disnake.TextChannel = None):
        """Unlock a channel"""
        channel = channel or ctx.channel
        
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        
        # Record the channel unlock in the database
        self._add_mod_action(ctx.guild.id, 0, ctx.author.id, "UNLOCK", f"Channel: {channel.name} ({channel.id})")
        
        await ctx.send(f"🔓 {channel.mention} has been unlocked")

    @commands.command(aliases=["clear"])
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        """Delete a specified number of messages"""
        if amount < 1 or amount > 100:
            return await ctx.send("You can only delete between 1 and 100 messages at once.")
            
        deleted = await ctx.channel.purge(limit=amount + 1)  # +1 to include the command message
        
        # Record the purge in the database
        self._add_mod_action(ctx.guild.id, 0, ctx.author.id, "PURGE", f"Channel: {ctx.channel.name}, Amount: {len(deleted) - 1}")
        
        confirmation = await ctx.send(f"✅ Deleted {len(deleted) - 1} messages")
        await asyncio.sleep(3)
        try:
            await confirmation.delete()
        except:
            pass

def setup(bot):
    bot.add_cog(ModerationCog(bot))