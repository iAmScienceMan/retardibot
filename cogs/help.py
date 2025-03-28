import disnake
from disnake.ext import commands
import datetime
import asyncio
from typing import Optional, List, Dict, Any, Union

class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.dev_logger
        self.color = disnake.Color.from_rgb(114, 137, 218)  # Discord blurple
        
        # Categories with descriptions and emojis
        self.categories = {
            "Moderation": {
                "emoji": "🛡️",
                "description": "Commands for server moderation and management"
            },
            "Entertainment": {
                "emoji": "🎭",
                "description": "Fun commands to keep the server entertained"
            },
            "Games": {
                "emoji": "🎮",
                "description": "Interactive games to play with other users"
            },
            "Utilities": {
                "emoji": "🔧",
                "description": "Helpful utility commands"
            },
            "Logging": {
                "emoji": "📝",
                "description": "Server logging and activity tracking"
            },
            "Configuration": {
                "emoji": "⚙️",
                "description": "Bot configuration commands"
            },
            "Uncategorized": {
                "emoji": "❓",
                "description": "Miscellaneous commands"
            }
        }
        
        # Map cogs to categories
        self.cog_categories = {
            "ModerationCog": "Moderation",
            "AutoModCog": "Moderation",
            "LoggingCog": "Logging",
            "RussianRouletteCog": "Games",
            "ReactionCog": "Entertainment",
            "DevLogger": "Configuration",
            "HelpCommand": "Utilities"
        }
        
        self.logger.info("Help command cog initialized")

    def get_command_category(self, command: commands.Command) -> str:
        """Get the category for a command based on its cog"""
        if command.cog_name is None:
            return "Uncategorized"
        
        return self.cog_categories.get(command.cog_name, "Uncategorized")
    
    def get_command_signature(self, command: commands.Command) -> str:
        """Get the command signature with parameters"""
        parent = command.full_parent_name
        aliases = '|'.join(command.aliases)
        
        if len(command.aliases) > 0:
            fmt = f'[{command.name}|{aliases}]'
        else:
            fmt = command.name
            
        if parent:
            fmt = f'{parent} {fmt}'
            
        params = command.signature
        return f'{self.bot.command_prefix}{fmt} {params}'.strip()
    
    def format_command_help(self, command: commands.Command) -> Dict[str, Any]:
        """Format help data for a single command"""
        return {
            "name": command.name,
            "signature": self.get_command_signature(command),
            "description": command.help or "No description provided",
            "aliases": command.aliases,
            "category": self.get_command_category(command)
        }
    
    def get_commands_by_category(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all commands organized by category"""
        commands_by_category = {category: [] for category in self.categories}
        
        for command in self.bot.commands:
            # Skip hidden commands
            if command.hidden:
                continue
                
            category = self.get_command_category(command)
            commands_by_category[category].append(self.format_command_help(command))
            
        return commands_by_category
    
    async def create_overview_embeds(self) -> List[disnake.Embed]:
        """Create overview embeds for all commands by category"""
        commands_by_category = self.get_commands_by_category()
        embeds = []
        
        # Create the main embed with bot info
        main_embed = disnake.Embed(
            title="RetardiBot Help",
            description="Welcome to RetardiBot help! Navigate through categories using the buttons below.",
            color=self.color,
            timestamp=datetime.datetime.utcnow()
        )
        
        main_embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        main_embed.add_field(
            name="Prefix",
            value=f"`{self.bot.command_prefix}`",
            inline=True
        )
        main_embed.add_field(
            name="Total Commands",
            value=str(len([cmd for cmd in self.bot.commands if not cmd.hidden])),
            inline=True
        )
        main_embed.add_field(
            name="Categories",
            value=str(len([cat for cat in commands_by_category if commands_by_category[cat]])),
            inline=True
        )
        
        main_embed.add_field(
            name="Usage",
            value=f"• `{self.bot.command_prefix}help` - Show this overview\n"
                  f"• `{self.bot.command_prefix}help [command]` - Show detailed help for a specific command\n"
                  f"• `{self.bot.command_prefix}help [category]` - Show all commands in a category",
            inline=False
        )
        
        embeds.append(main_embed)
        
        # Create category embeds
        for category, commands_list in commands_by_category.items():
            if not commands_list:
                continue
                
            category_info = self.categories.get(category, {"emoji": "❓", "description": "Miscellaneous commands"})
            
            embed = disnake.Embed(
                title=f"{category_info['emoji']} {category} Commands",
                description=category_info['description'],
                color=self.color,
                timestamp=datetime.datetime.utcnow()
            )
            
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            
            # Sort commands alphabetically by name
            commands_list.sort(key=lambda x: x['name'])
            
            # Add commands to the embed
            for cmd_data in commands_list:
                name = cmd_data['name']
                if cmd_data['aliases']:
                    aliases = f" (Aliases: {', '.join(cmd_data['aliases'])})"
                else:
                    aliases = ""
                    
                embed.add_field(
                    name=f"{self.bot.command_prefix}{name}{aliases}",
                    value=cmd_data['description'] or "No description provided",
                    inline=False
                )
            
            embed.set_footer(text=f"Use {self.bot.command_prefix}help [command] for more details on a command")
            embeds.append(embed)
            
        return embeds
    
    def create_command_embed(self, command: commands.Command) -> disnake.Embed:
        """Create detailed help embed for a specific command"""
        cmd_data = self.format_command_help(command)
        category = cmd_data['category']
        category_info = self.categories.get(category, {"emoji": "❓", "description": "Miscellaneous commands"})
        
        embed = disnake.Embed(
            title=f"Command: {cmd_data['name']}",
            description=cmd_data['description'],
            color=self.color,
            timestamp=datetime.datetime.utcnow()
        )
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        # Add command details
        embed.add_field(
            name="Usage",
            value=f"`{cmd_data['signature']}`",
            inline=False
        )
        
        if cmd_data['aliases']:
            embed.add_field(
                name="Aliases",
                value=", ".join([f"`{alias}`" for alias in cmd_data['aliases']]),
                inline=True
            )
            
        embed.add_field(
            name="Category",
            value=f"{category_info['emoji']} {category}",
            inline=True
        )
        
        # Display subcommands if this is a group command
        if isinstance(command, commands.Group) and len(command.commands) > 0:
            subcommands = []
            for subcmd in command.commands:
                if not subcmd.hidden:
                    subcommands.append(f"`{subcmd.name}` - {subcmd.help or 'No description'}")
            
            if subcommands:
                embed.add_field(
                    name="Subcommands",
                    value="\n".join(subcommands),
                    inline=False
                )
        
        embed.set_footer(text=f"Use {self.bot.command_prefix}help for a list of all commands")
        return embed
    
    @commands.command(name="help")
    async def help_command(self, ctx, *, query: Optional[str] = None):
        """
        Shows help information for commands or categories.
        
        Without arguments, this command shows a list of all available commands.
        When a command name is provided, it shows detailed help for that specific command.
        When a category name is provided, it shows all commands in that category.
        """
        # If no query, show overview of all commands
        if query is None:
            embeds = await self.create_overview_embeds()
            
            # If there's only one embed (main overview), just send it
            if len(embeds) == 1:
                return await ctx.send(embed=embeds[0])
            
            # Otherwise, create a paginated view
            current_page = 0
            
            # Create navigation view
            view = disnake.ui.View()
            
            # First page button
            first_button = disnake.ui.Button(style=disnake.ButtonStyle.secondary, emoji="⏮️")
            
            # Previous page button
            prev_button = disnake.ui.Button(style=disnake.ButtonStyle.secondary, emoji="◀️")
            
            # Page indicator
            page_indicator = disnake.ui.Button(
                style=disnake.ButtonStyle.secondary,
                label=f"1/{len(embeds)}",
                disabled=True
            )
            
            # Next page button
            next_button = disnake.ui.Button(style=disnake.ButtonStyle.secondary, emoji="▶️")
            
            # Last page button
            last_button = disnake.ui.Button(style=disnake.ButtonStyle.secondary, emoji="⏭️")
            
            # Define button callbacks
            async def update_page(interaction, new_page):
                nonlocal current_page
                if 0 <= new_page < len(embeds):
                    current_page = new_page
                    
                    # Update page indicator
                    page_indicator.label = f"{current_page + 1}/{len(embeds)}"
                    
                    # Update button states
                    first_button.disabled = current_page == 0
                    prev_button.disabled = current_page == 0
                    next_button.disabled = current_page == len(embeds) - 1
                    last_button.disabled = current_page == len(embeds) - 1
                    
                    await interaction.response.edit_message(
                        embed=embeds[current_page],
                        view=view
                    )
            
            first_button.callback = lambda i: update_page(i, 0)
            prev_button.callback = lambda i: update_page(i, current_page - 1)
            next_button.callback = lambda i: update_page(i, current_page + 1)
            last_button.callback = lambda i: update_page(i, len(embeds) - 1)
            
            # Initial button states
            first_button.disabled = True
            prev_button.disabled = True
            next_button.disabled = False
            last_button.disabled = False
            
            # Add buttons to view
            view.add_item(first_button)
            view.add_item(prev_button)
            view.add_item(page_indicator)
            view.add_item(next_button)
            view.add_item(last_button)
            
            await ctx.send(embed=embeds[0], view=view)
            return
        
        # Check if the query is a command
        command = self.bot.get_command(query.lower())
        if command and not command.hidden:
            embed = self.create_command_embed(command)
            await ctx.send(embed=embed)
            return
        
        # Check if the query is a category
        query_lower = query.lower()
        for category in self.categories:
            if category.lower() == query_lower:
                # Get commands for this category
                commands_by_category = self.get_commands_by_category()
                category_commands = commands_by_category.get(category, [])
                
                if not category_commands:
                    await ctx.send(f"No commands found in the '{category}' category.")
                    return
                
                category_info = self.categories.get(category)
                
                embed = disnake.Embed(
                    title=f"{category_info['emoji']} {category} Commands",
                    description=category_info['description'],
                    color=self.color,
                    timestamp=datetime.datetime.utcnow()
                )
                
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)
                
                # Sort commands alphabetically
                category_commands.sort(key=lambda x: x['name'])
                
                # Add commands to the embed
                for cmd_data in category_commands:
                    name = cmd_data['name']
                    if cmd_data['aliases']:
                        aliases = f" (Aliases: {', '.join(cmd_data['aliases'])})"
                    else:
                        aliases = ""
                        
                    embed.add_field(
                        name=f"{self.bot.command_prefix}{name}{aliases}",
                        value=cmd_data['description'] or "No description provided",
                        inline=False
                    )
                
                embed.set_footer(text=f"Use {self.bot.command_prefix}help [command] for more details on a command")
                await ctx.send(embed=embed)
                return
        
        # If we got here, the query didn't match a command or category
        await ctx.send(f"No command or category found matching '{query}'.")

def setup(bot):
    bot.add_cog(HelpCommand(bot))