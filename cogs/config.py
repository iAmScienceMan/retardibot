import disnake
from disnake.ext import commands
import json

class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Set bot prefix")
    async def set_prefix(self, inter, prefix: str):
        with open("config.json", "r+") as f:
            data = json.load(f)
            data["prefix"] = prefix
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
        self.bot.command_prefix = prefix
        await inter.send(f"Prefix changed to `{prefix}`!", ephemeral=True)

def setup(bot):
    bot.add_cog(Config(bot))
