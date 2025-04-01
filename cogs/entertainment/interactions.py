import disnake
from disnake.ext import commands
import random
from cogs.common.base_cog import BaseCog

class InteractionsCog(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        
        # Define interaction messages for each command
        self.interactions = {
            "hug": [
                "{user} gave {target} a big warm hug!",
                "{user} hugged {target} tightly!",
                "{user} tried to hug {target}, but they slipped away!",
                "{user} hugs {target} so hard they can barely breathe!",
                "{target} was caught off guard by {user}'s surprise hug!"
            ],
            "kiss": [
                "{user} planted a sweet kiss on {target}'s cheek!",
                "{user} tried to kiss {target}, but missed and kissed the air!",
                "{target} dodged {user}'s kiss at the last second!",
                "{user} and {target} shared a romantic kiss!",
                "{user} gave {target} a quick peck on the lips!"
            ],
            "pat": [
                "{user} gently pats {target} on the head!",
                "{user} pats {target} awkwardly!",
                "{target} enjoys {user}'s headpats!",
                "{user} tried to pat {target}, but they ducked!",
                "{user} gives {target} reassuring pats!"
            ],
            "cuddle": [
                "{user} cuddles up with {target} by the fireplace!",
                "{user} and {target} cuddle together like kittens!",
                "{user} tried to cuddle {target}, but they rolled away!",
                "{target} pulls {user} in for a cozy cuddle!",
                "{user} and {target} share a warm blanket and cuddle!"
            ],
            "tickle": [
                "{user} tickles {target} mercilessly!",
                "{target} runs away giggling as {user} tries to tickle them!",
                "{user} found {target}'s ticklish spot!",
                "{target} is rolling on the floor laughing from {user}'s tickles!",
                "{user} tried to tickle {target}, but they're not ticklish!"
            ],
            "smash": [
                "{user} and {target} disappeared into the bedroom for some privacy...",
                "{target} turned {user} down with a firm 'no thanks'!",
                "{user} tried to make a move on {target}, but got friendzoned!",
                "{user} and {target} were caught in a compromising position!",
                "{user} slid into {target}'s DMs, but {target} left them on read!"
            ],
            "kill": [
                "{user} tried to eliminate {target}, but {target} had an Uno reverse card!",
                "{user} defeated {target} in an epic battle! (in a video game)",
                "{user} 'game over'd {target} in Mario Kart!",
                "{user} attempted to defeat {target}, but {target} was too powerful!",
                "{target} narrowly escaped {user}'s evil plot!"
            ]
        }
        
        # Define colors for each interaction
        self.colors = {
            "hug": disnake.Color.green(),
            "kiss": disnake.Color.red(),
            "pat": disnake.Color.blue(),
            "cuddle": disnake.Color.purple(),
            "tickle": disnake.Color.gold(),
            "smash": disnake.Color.dark_purple(),
            "kill": disnake.Color.dark_red()
        }
        
        # Define emoji for each interaction
        self.emojis = {
            "hug": "🤗",
            "kiss": "😘",
            "pat": "👋",
            "cuddle": "🥰",
            "tickle": "😂",
            "smash": "😭",
            "kill": "☠️"
        }

    def create_interaction_embed(self, interaction_type, user, target, message):
        """Creates an embed for an interaction"""
        color = self.colors.get(interaction_type, disnake.Color.default())
        emoji = self.emojis.get(interaction_type, "")
        
        embed = disnake.Embed(
            title=f"{emoji} {interaction_type.capitalize()} {emoji}",
            description=message,
            color=color
        )
        
        embed.set_footer(text=f"Requested by {user}")
        
        return embed
    
    async def handle_interaction(self, ctx, interaction_type, target):
        """Handles an interaction command"""
        # Check if user is targeting themselves
        if target.id == ctx.author.id:
            if interaction_type == "smash":
                return await ctx.send("That's something you should do in private...")
            else:
                return await ctx.send(f"You can't {interaction_type} yourself, silly!")
        
        # Check if user is targeting the bot
        if target.id == self.bot.user.id:
            special_responses = {
                "hug": "Thanks for the hug! *hugs back*",
                "kiss": "I'm flattered, but I'm just a bot!",
                "pat": "Thanks for the pat! *happy beep boop*",
                "cuddle": "I appreciate the sentiment, but I'm just a bot!",
                "tickle": "Haha! Bots aren't ticklish, but nice try!",
                "smash": "I'm flattered, but I'm just lines of code!",
                "kill": "I'm immortal! Mwahahaha!"
            }
            
            return await ctx.send(special_responses.get(interaction_type, f"I don't know how to respond to that {interaction_type}!"))
        
        # Get random message for this interaction
        messages = self.interactions.get(interaction_type, [f"{{user}} {interaction_type}s {{target}}!"])
        message = random.choice(messages).format(user=ctx.author.mention, target=target.mention)
        
        # Create and send embed
        embed = self.create_interaction_embed(interaction_type, ctx.author, target, message)
        await ctx.send(embed=embed)
        
        self.logger.debug(f"Interaction: {ctx.author} {interaction_type} {target}")
    
    @commands.command()
    async def hug(self, ctx, *, member: disnake.Member):
        """Give someone a hug"""
        await self.handle_interaction(ctx, "hug", member)
    
    @commands.command()
    async def kiss(self, ctx, *, member: disnake.Member):
        """Kiss someone"""
        await self.handle_interaction(ctx, "kiss", member)
    
    @commands.command()
    async def pat(self, ctx, *, member: disnake.Member):
        """Pat someone on the head"""
        await self.handle_interaction(ctx, "pat", member)
    
    @commands.command()
    async def cuddle(self, ctx, *, member: disnake.Member):
        """Cuddle with someone"""
        await self.handle_interaction(ctx, "cuddle", member)
    
    @commands.command()
    async def tickle(self, ctx, *, member: disnake.Member):
        """Tickle someone"""
        await self.handle_interaction(ctx, "tickle", member)
    
    @commands.command()
    async def smash(self, ctx, *, member: disnake.Member):
        """Suggest intimate activities with someone"""
        await self.handle_interaction(ctx, "smash", member)
    
    @commands.command()
    async def kill(self, ctx, *, member: disnake.Member):
        """Defeat someone (in a game)"""
        await self.handle_interaction(ctx, "kill", member)
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle errors for interaction commands"""
        if ctx.command and ctx.command.name in self.interactions.keys():
            if isinstance(error, commands.MemberNotFound):
                await ctx.send("I couldn't find that user. Make sure to mention a valid user!")
            elif isinstance(error, commands.MissingRequiredArgument):
                await ctx.send(f"You need to specify someone to {ctx.command.name}!")

def setup(bot):
    bot.add_cog(InteractionsCog(bot))