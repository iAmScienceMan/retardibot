import disnake
from disnake.ext import commands
import sqlite3
import datetime

class ConfessionsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.dev_logger
        config = getattr(self.bot, 'config', {})
        self.confession_channel_id = config.get("confession_channel_id")
        self.db_path = "confessions.db"
        self._create_tables()
        
    def _create_tables(self):
        """Create the necessary database tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Table for storing confessions
        c.execute('''
        CREATE TABLE IF NOT EXISTS confessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        )
        ''')
        
        # Table for banned users
        c.execute('''
        CREATE TABLE IF NOT EXISTS confession_bans (
            user_id INTEGER PRIMARY KEY,
            banned_by INTEGER NOT NULL,
            reason TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
        self.logger.info("Confession database initialized")
    
    def _is_user_banned(self, user_id):
        """Check if a user is banned from using confessions"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('SELECT user_id FROM confession_bans WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        
        conn.close()
        return result is not None
    
    def _ban_user(self, user_id, mod_id, reason=None):
        """Ban a user from using confessions"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
        INSERT OR REPLACE INTO confession_bans (user_id, banned_by, reason, timestamp)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, mod_id, reason))
        
        conn.commit()
        conn.close()
    
    def _save_confession(self, user_id, content):
        """Save a confession to the database and return its ID"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
        INSERT INTO confessions (user_id, content, timestamp)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, content))
        
        confession_id = c.lastrowid
        
        conn.commit()
        conn.close()
        
        return confession_id
    
    def _update_message_id(self, confession_id, message_id):
        """Update the message ID for a confession"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
        UPDATE confessions SET message_id = ? WHERE id = ?
        ''', (message_id, confession_id))
        
        conn.commit()
        conn.close()
    
    def _mark_deleted(self, message_id):
        """Mark a confession as deleted"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''
        UPDATE confessions SET is_deleted = 1 WHERE message_id = ?
        ''', (message_id,))
        
        conn.commit()
        conn.close()
    
    def _get_user_id_from_message(self, message_id):
        """Get the user ID associated with a confession message"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('SELECT user_id FROM confessions WHERE message_id = ?', (message_id,))
        result = c.fetchone()
        
        conn.close()
        return result[0] if result else None
    
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
                    return await interaction.response.send_message("Critical error encountered.", ephemeral=True); self.bot.dev_logger.critical("MOD ROLE ID NOT SPECIFIED"); exit(1)
                
                mod_role = interaction.guild.get_role(mod_role_id)
                if not mod_role or mod_role not in interaction.user.roles:
                    return await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
                
                # Update the embed
                embed = interaction.message.embeds[0]
                embed.description = "[DELETED]"
                embed.color = disnake.Color.dark_gray()
                
                # Mark as deleted in database
                self.cog._mark_deleted(interaction.message.id)

                self.logger.info(f"Deleted confession #{confession_id} sent by user {inter.author.id} - '{message}'")
                
                await interaction.response.edit_message(embed=embed)
                await interaction.followup.send("Confession deleted.", ephemeral=True)
            
            @disnake.ui.button(label="Ban User", style=disnake.ButtonStyle.danger, emoji="🚫")
            async def ban_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
                # Check if user has mod role
                mod_role_id = getattr(self.cog.bot, 'config', {}).get("automod", {}).get("mod_role_id")
                if not mod_role_id:
                    return await interaction.response.send_message("Critical error encountered.", ephemeral=True); self.bot.dev_logger.critical("MOD ROLE ID NOT SPECIFIED"); exit(1)
                
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

                self.logger.info(f"Banned user {inter.author.id} - '{message}', removed confession #{confession_id}")
                
                await interaction.response.edit_message(embed=embed)
                await interaction.followup.send(f"User (ID: {user_id}) has been banned from sending confessions.", ephemeral=True)
        
        # Send the confession message with buttons
        view = ConfessionButtons(self)
        confession_message = await confession_channel.send(embed=embed, view=view)
        
        # Update the message ID in the database
        self._update_message_id(confession_id, confession_message.id)
        
        self.logger.info(f"Confession #{confession_id} sent by user {inter.author.id} - '{message}'")

def setup(bot):
    bot.add_cog(ConfessionsCog(bot))