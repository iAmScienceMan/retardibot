import disnake
from disnake.ext import commands

class BaseCog(commands.Cog):
    """Base class for all cogs with common functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.dev_logger.getChild(self.__class__.__name__)
        
    async def send_error(self, ctx, title, description):
        """Send an error message embed"""
        embed = disnake.Embed(
            title=title,
            description=description,
            color=disnake.Color.red()
        )
        return await ctx.send(embed=embed)
        
    async def send_success(self, ctx, title, description):
        """Send a success message embed"""
        embed = disnake.Embed(
            title=title,
            description=description,
            color=disnake.Color.green()
        )
        return await ctx.send(embed=embed)
        
    def has_mod_role(self, member):
        """Check if a member has the moderator role"""
        if not member or not member.guild:
            return False
            
        config = getattr(self.bot, 'config', {}).get("automod", {})
        mod_role_id = config.get("mod_role_id")
        
        if not mod_role_id:
            return False
            
        mod_role = member.guild.get_role(mod_role_id)
        if not mod_role:
            return False
            
        return mod_role in member.roles