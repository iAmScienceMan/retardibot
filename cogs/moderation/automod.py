import disnake
from disnake.ext import commands
import os
from openai import AsyncOpenAI
import asyncio
import json
from dotenv import load_dotenv
from cogs.common.base_cog import BaseCog

class AutoModCog(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        load_dotenv()
        self.openai_key = os.getenv("OPENAI_KEY")
        
        # Initialize OpenAI client
        self.aclient = AsyncOpenAI(api_key=self.openai_key)

        # Get config
        automod_config = getattr(self.bot, 'config', {}).get("automod", {})

        # Set default values if not in config
        self.mod_role_id = automod_config.get("mod_role_id", 1356315914290856050)
        self.alert_channel_id = automod_config.get("alert_channel_id", 1342693547698294903)
        
        # Thresholds for moderation categories
        self.thresholds = automod_config.get("thresholds", {
            "harassment": 0.80,
            "harassment/threatening": 0.70,
            "hate": 0.80,
            "hate/threatening": 0.70,
            "self-harm": 0.80,
            "self-harm/intent": 0.75,
            "self-harm/instructions": 0.75,
            "sexual": 0.85,
            "sexual/minors": 0.50,  # Lower threshold for this serious category
            "violence": 0.85,
            "violence/graphic": 0.80,
            "illicit": 0.85,
            "illicit/violent": 0.80
        })
        
        # Configure which categories require immediate moderator attention (pings)
        self.high_priority_categories = automod_config.get("high_priority_categories", [
            "sexual/minors",
            "hate/threatening",
            "self-harm/intent",
            "self-harm/instructions",
            "violence/graphic",
            "illicit/violent"
        ])

        self.logger.debug(f"Set channel: notification channel {self.alert_channel_id} for automod")
        self.logger.info(f"AutoMod initialized with OpenAI moderation API")

    async def moderate_content(self, content):
        """Send content to OpenAI Moderation API for analysis"""
        try:
            response = await self.aclient.moderations.create(
                model="omni-moderation-latest",
                input=content
            )
            return response
        except Exception as e:
            self.logger.error(f"Error querying OpenAI Moderation API: {e}")
            return None

    def has_mod_role(self, member):
        """Check if a member has the mod role"""
        if not member or not member.guild:
            return False
            
        mod_role = member.guild.get_role(self.mod_role_id)
        if not mod_role:
            return False
            
        return mod_role in member.roles

    def should_flag_content(self, moderation_result):
        """Determine if content should be flagged based on moderation scores and thresholds"""
        if not moderation_result or not moderation_result.results:
            return False, [], False
            
        result = moderation_result.results[0]
        
        # If OpenAI already flagged it, respect that decision
        if result.flagged:
            flagged_categories = []
            high_priority = False
            
            for category, score in result.category_scores.items():
                threshold = self.thresholds.get(category, 0.8)  # Default threshold
                
                if score >= threshold:
                    flagged_categories.append({
                        "name": category,
                        "score": score,
                        "high_priority": category in self.high_priority_categories
                    })
                    
                    if category in self.high_priority_categories:
                        high_priority = True
            
            return True, flagged_categories, high_priority
        
        # Check if any category exceeds our custom thresholds
        flagged_categories = []
        high_priority = False
        
        for category, score in result.category_scores.items():
            threshold = self.thresholds.get(category, 0.8)  # Default threshold
            
            if score >= threshold:
                flagged_categories.append({
                    "name": category,
                    "score": score,
                    "high_priority": category in self.high_priority_categories
                })
                
                if category in self.high_priority_categories:
                    high_priority = True
        
        return len(flagged_categories) > 0, flagged_categories, high_priority

    @commands.Cog.listener()
    async def on_message(self, message):
        # Skip bot messages and DMs
        if message.author.bot or not message.guild:
            return
            
        # Skip messages from users with the mod role
        if self.has_mod_role(message.author):
            return

        # Get the message content
        content = message.content

        # Skip empty messages
        if not content:
            return

        # Send to OpenAI for moderation
        moderation_response = await self.moderate_content(content)
        
        # Check if content should be flagged
        should_flag, flagged_categories, high_priority = self.should_flag_content(moderation_response)
        
        # Handle flagged content
        if should_flag:
            await self.send_mod_notification(message, flagged_categories, high_priority)

    async def send_mod_notification(self, message, flagged_categories, high_priority):
        """Send notification to moderators"""
        try:
            alert_channel = self.bot.get_channel(self.alert_channel_id)
            if not alert_channel:
                self.logger.error(f"Alert channel {self.alert_channel_id} not found")
                return

            # Create embed
            embed = disnake.Embed(
                title="AutoMod Alert",
                description=f"**Message content:**\n{message.content}",
                color=disnake.Color.red() if high_priority else disnake.Color.orange(),
                timestamp=message.created_at
            )

            # Format categories in the embed
            categories_text = ""
            for category in flagged_categories:
                priority_tag = "⚠️ HIGH PRIORITY" if category["high_priority"] else ""
                categories_text += f"• **{category['name']}**: {category['score']:.2f} {priority_tag}\n"
            
            embed.add_field(name="Flagged Categories", value=categories_text, inline=False)
            embed.add_field(name="Channel", value=message.channel.mention, inline=True)
            embed.add_field(name="Author", value=f"{message.author.mention} ({message.author.id})", inline=True)
            embed.add_field(name="Jump to Message", value=f"[Click here]({message.jump_url})", inline=False)

            embed.set_footer(text=f"Severity: {'HIGH' if high_priority else 'MEDIUM'}")

            if message.author.avatar:
                embed.set_thumbnail(url=message.author.avatar.url)

            # Add action buttons
            class ModActionButtons(disnake.ui.View):
                def __init__(self, cog, message_to_delete):
                    super().__init__(timeout=None)
                    self.cog = cog
                    self.message_to_delete = message_to_delete
                
                @disnake.ui.button(label="Delete Message", style=disnake.ButtonStyle.danger)
                async def delete_button(self, button, interaction):
                    if not self.cog.has_mod_role(interaction.user):
                        return await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
                    
                    try:
                        await self.message_to_delete.delete()
                        await interaction.response.send_message("Message deleted successfully.", ephemeral=True)
                        self.cog.logger.info(f"Moderator {interaction.user} deleted flagged message from {self.message_to_delete.author}")
                    except Exception as e:
                        await interaction.response.send_message(f"Failed to delete message: {e}", ephemeral=True)
                
                @disnake.ui.button(label="Warn User", style=disnake.ButtonStyle.secondary)
                async def warn_button(self, button, interaction):
                    if not self.cog.has_mod_role(interaction.user):
                        return await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
                    
                    # Check if ModerationCog is loaded to handle the warning
                    moderation_cog = self.cog.bot.get_cog("ModerationCog")
                    if not moderation_cog:
                        return await interaction.response.send_message("ModerationCog is not loaded. Can't issue warning.", ephemeral=True)
                    
                    try:
                        # Create a mock context to call the warn command
                        ctx = await self.cog.bot.get_context(interaction.message)
                        ctx.author = interaction.user
                        
                        # Call the warn method directly
                        await moderation_cog._add_mod_action(
                            self.message_to_delete.guild.id, 
                            self.message_to_delete.author.id,
                            interaction.user.id,
                            "WARN",
                            "AutoMod flagged message"
                        )
                        
                        try:
                            await self.message_to_delete.author.send(f"You have been warned in {self.message_to_delete.guild.name} for a message that violated server rules.")
                        except:
                            pass  # Can't DM the user
                            
                        await interaction.response.send_message(f"Warning issued to {self.message_to_delete.author.mention}", ephemeral=True)
                        self.cog.logger.info(f"Moderator {interaction.user} warned user {self.message_to_delete.author} for flagged message")
                    except Exception as e:
                        await interaction.response.send_message(f"Failed to warn user: {e}", ephemeral=True)
                        self.cog.logger.error(f"Error issuing warning: {e}")

            view = ModActionButtons(self, message)

            # Send embed with or without ping
            if high_priority:
                mod_role = message.guild.get_role(self.mod_role_id)
                if mod_role:
                    await alert_channel.send(f"{mod_role.mention} Moderation required!", embed=embed, view=view)
                else:
                    self.logger.error(f"Notification role {self.mod_role_id} not found")
                    await alert_channel.send(embed=embed, view=view)
            else:
                await alert_channel.send(embed=embed, view=view)

        except Exception as e:
            self.logger.error(f"Error sending notification: {e}", exc_info=True)

    @commands.group(name="automod", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def automod_group(self, ctx):
        """Manage automod settings"""
        await ctx.send("Please use a subcommand: `status`, `threshold`, `priority`")

    @automod_group.command(name="status")
    @commands.has_permissions(manage_guild=True)
    async def automod_status(self, ctx):
        """Show current automod configuration"""
        embed = disnake.Embed(
            title="AutoMod Configuration",
            description="Current settings for the automatic moderation system",
            color=disnake.Color.blue()
        )
        
        # Add general settings
        mod_role = ctx.guild.get_role(self.mod_role_id)
        alert_channel = ctx.guild.get_channel(self.alert_channel_id)
        
        embed.add_field(
            name="General Settings",
            value=f"**Mod Role:** {mod_role.mention if mod_role else 'Not found'}\n"
                  f"**Alert Channel:** {alert_channel.mention if alert_channel else 'Not found'}",
            inline=False
        )
        
        # Add threshold settings
        thresholds_text = ""
        for category, threshold in self.thresholds.items():
            priority = "⚠️ " if category in self.high_priority_categories else ""
            thresholds_text += f"{priority}**{category}**: {threshold}\n"
        
        embed.add_field(
            name="Category Thresholds",
            value=thresholds_text or "No thresholds configured",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @automod_group.command(name="threshold")
    @commands.has_permissions(manage_guild=True)
    async def set_threshold(self, ctx, category: str, threshold: float):
        """Set threshold for a moderation category (between 0 and 1)"""
        if threshold < 0 or threshold > 1:
            return await ctx.send("Threshold must be between 0 and 1")
        
        valid_categories = [
            "harassment", "harassment/threatening", 
            "hate", "hate/threatening", 
            "self-harm", "self-harm/intent", "self-harm/instructions",
            "sexual", "sexual/minors", 
            "violence", "violence/graphic",
            "illicit", "illicit/violent"
        ]
        
        if category not in valid_categories:
            return await ctx.send(f"Invalid category. Valid categories are: {', '.join(valid_categories)}")
        
        # Update threshold
        self.thresholds[category] = threshold
        
        # Save to config
        config = getattr(self.bot, 'config', {})
        if "automod" not in config:
            config["automod"] = {}
        
        if "thresholds" not in config["automod"]:
            config["automod"]["thresholds"] = {}
        
        config["automod"]["thresholds"][category] = threshold
        
        try:
            with open("config.json", 'w') as f:
                json.dump(config, f, indent=4)
            
            await ctx.send(f"✅ Set threshold for `{category}` to `{threshold}`")
            self.logger.info(f"Updated automod threshold for {category} to {threshold}")
        except Exception as e:
            await ctx.send(f"Error saving config: {e}")
            self.logger.error(f"Failed to save config when updating threshold: {e}", exc_info=True)

    @automod_group.command(name="priority")
    @commands.has_permissions(manage_guild=True)
    async def set_priority(self, ctx, category: str, is_high_priority: bool):
        """Set whether a category should be high priority (requires mod ping)"""
        valid_categories = [
            "harassment", "harassment/threatening", 
            "hate", "hate/threatening", 
            "self-harm", "self-harm/intent", "self-harm/instructions",
            "sexual", "sexual/minors", 
            "violence", "violence/graphic",
            "illicit", "illicit/violent"
        ]
        
        if category not in valid_categories:
            return await ctx.send(f"Invalid category. Valid categories are: {', '.join(valid_categories)}")
        
        # Update priority
        if is_high_priority and category not in self.high_priority_categories:
            self.high_priority_categories.append(category)
        elif not is_high_priority and category in self.high_priority_categories:
            self.high_priority_categories.remove(category)
        
        # Save to config
        config = getattr(self.bot, 'config', {})
        if "automod" not in config:
            config["automod"] = {}
        
        config["automod"]["high_priority_categories"] = self.high_priority_categories
        
        try:
            with open("config.json", 'w') as f:
                json.dump(config, f, indent=4)
            
            priority_status = "high priority" if is_high_priority else "normal priority"
            await ctx.send(f"✅ Set `{category}` to {priority_status}")
            self.logger.info(f"Updated priority status for {category} to {priority_status}")
        except Exception as e:
            await ctx.send(f"Error saving config: {e}")
            self.logger.error(f"Failed to save config when updating priority: {e}", exc_info=True)

def setup(bot):
    bot.add_cog(AutoModCog(bot))