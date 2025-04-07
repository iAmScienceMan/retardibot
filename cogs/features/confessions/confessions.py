import disnake
from disnake.ext import commands
from cogs.common.base_cog import BaseCog
from cogs.common.db_manager import DBManager
import datetime
import json

class ConfessionsCog(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        config = getattr(self.bot, 'config', {})
        self.confession_channel_id = config.get("confession_channel_id")
        self.db = DBManager()
        self.logger.info("Confession system initialized with PostgreSQL")
    
    def _is_user_banned(self, user_id):
        """Check if a user is banned from using confessions"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT user_id FROM confession_bans WHERE user_id = %s', (user_id,))
                result = cursor.fetchone()
                return result is not None
        finally:
            self.db.release_connection(conn)
    
    def _ban_user(self, user_id, mod_id, reason=None):
        """Ban a user from using confessions"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                INSERT INTO confession_bans (user_id, banned_by, reason, timestamp)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE SET
                    banned_by = EXCLUDED.banned_by,
                    reason = EXCLUDED.reason,
                    timestamp = CURRENT_TIMESTAMP
                ''', (user_id, mod_id, reason))
                conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Error banning user: {e}")
        finally:
            self.db.release_connection(conn)
    
    def _save_confession(self, user_id, content):
        """Save a confession to the database and return its ID"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                INSERT INTO confessions (user_id, content, timestamp)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                RETURNING id
                ''', (user_id, content))
                confession_id = cursor.fetchone()[0]
                conn.commit()
                return confession_id
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Error saving confession: {e}")
            return None
        finally:
            self.db.release_connection(conn)
    
    def _update_message_id(self, confession_id, message_id):
        """Update the message ID for a confession"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                UPDATE confessions SET message_id = %s WHERE id = %s
                ''', (message_id, confession_id))
                conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Error updating message ID: {e}")
        finally:
            self.db.release_connection(conn)
    
    def _mark_deleted(self, message_id):
        """Mark a confession as deleted"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                UPDATE confessions SET is_deleted = TRUE WHERE message_id = %s
                ''', (message_id,))
                conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Error marking confession as deleted: {e}")
        finally:
            self.db.release_connection(conn)
    
    def _get_user_id_from_message(self, message_id):
        """Get the user ID associated with a confession message"""
        conn = self.db.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT user_id FROM confessions WHERE message_id = %s', (message_id,))
                result = cursor.fetchone()
                return result[0] if result else None
        finally:
            self.db.release_connection(conn)
    
    @commands.slash_command(
        name="confess",
        description="Send an anonymous confession"
    )
    async def confess(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        message: str = commands.Param(description="Your anonymous confession")
    ):
        # Check if user is banned
        if self._is_user_banned(inter.author.id):
            return await inter.response.send_message(
                "You have been banned from using the confession system.", 
                ephemeral=True
            )
        
        # Tell the user their confession was sent
        await inter.response.send_message(
            "Your confession has been sent anonymously!", 
            ephemeral=True
        )
        
        # Get the confession channel
        confession_channel = self.bot.get_channel(self.confession_channel_id)
        if not confession_channel:
            self.logger.error(f"Could not find confession channel with ID {self.confession_channel_id}")
            return
        
        # Save confession to database
        confession_id = self._save_confession(inter.author.id, message)
        if confession_id is None:
            self.logger.error(f"Failed to save confession for user {inter.author.id}")
            return
        
        # Create the confession embed
        embed = disnake.Embed(
            title="Anonymous Confession",
            description=message,
            color=disnake.Color.blurple(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_footer(text=f"Confession #{confession_id}")
        
        # Create moderation buttons
        class ConfessionButtons(disnake.ui.View):
            def __init__(self, cog):
                super().__init__(timeout=None)
                self.cog = cog
                self.logger = self.cog.bot.dev_logger
                
            @disnake.ui.button(label="Delete Confession", style=disnake.ButtonStyle.danger, emoji="🗑️")
            async def delete_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
                # Check if user has mod role
                mod_role_id = getattr(self.cog.bot, 'config', {}).get("automod", {}).get("mod_role_id")
                if not mod_role_id:
                    return await interaction.response.send_message("Critical error encountered.", ephemeral=True)
                
                mod_role = interaction.guild.get_role(mod_role_id)
                if not mod_role or mod_role not in interaction.user.roles:
                    return await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
                
                # Update the embed
                embed = interaction.message.embeds[0]
                embed.description = "[DELETED]"
                embed.color = disnake.Color.dark_gray()
                
                # Mark as deleted in database
                self.cog._mark_deleted(interaction.message.id)

                self.logger.info(f"Deleted confession #{confession_id} sent by user {inter.author.id}")
                
                await interaction.response.edit_message(embed=embed)
                await interaction.followup.send("Confession deleted.", ephemeral=True)
            
            @disnake.ui.button(label="Ban User", style=disnake.ButtonStyle.danger, emoji="🚫")
            async def ban_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
                # Check if user has mod role
                mod_role_id = getattr(self.cog.bot, 'config', {}).get("automod", {}).get("mod_role_id")
                if not mod_role_id:
                    return await interaction.response.send_message("Critical error encountered.", ephemeral=True)
                
                mod_role = interaction.guild.get_role(mod_role_id)
                if not mod_role or mod_role not in interaction.user.roles:
                    return await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
                
                # Get user ID from message ID
                user_id = self.cog._get_user_id_from_message(interaction.message.id)
                if not user_id:
                    return await interaction.response.send_message("Could not find the user for this confession.", ephemeral=True)
                
                # Ban user
                self.cog._ban_user(user_id, interaction.user.id, "Banned by moderator")
                
                # Update the embed
                embed = interaction.message.embeds[0]
                if embed.description != "[DELETED]":
                    embed.description = "[DELETED]"
                    embed.color = disnake.Color.dark_gray()
                    self.cog._mark_deleted(interaction.message.id)

                self.logger.info(f"Banned user {inter.author.id}, removed confession #{confession_id}")
                
                await interaction.response.edit_message(embed=embed)
                await interaction.followup.send(f"User (ID: {user_id}) has been banned from sending confessions.", ephemeral=True)
        
        # Send the confession message with buttons
        view = ConfessionButtons(self)
        confession_message = await confession_channel.send(embed=embed, view=view)
        
        # Update the message ID in the database
        self._update_message_id(confession_id, confession_message.id)
        
        self.logger.info(f"Confession #{confession_id} sent by user {inter.author.id}")

def setup(bot):
    bot.add_cog(ConfessionsCog(bot))