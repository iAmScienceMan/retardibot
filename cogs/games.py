import disnake
from disnake.ext import commands
import random
import asyncio

class RussianRouletteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}  # Store active game sessions

    @commands.command(aliases=["rr"])
    async def russianroulette(self, ctx, opponent: disnake.Member = None):
        """
        Play Russian Roulette with another user.
        There's a 1/6 chance someone will get shot.
        """
        # Check if player is trying to challenge themselves
        if opponent == ctx.author:
            return await ctx.send("You can't play Russian Roulette against yourself!")

        # Check if player is trying to challenge the bot
        if opponent == self.bot.user:
            return await ctx.send("I'm too smart to put a gun to my head. Try finding a real opponent!")

        # Check if opponent is a bot
        if opponent and opponent.bot:
            return await ctx.send("Bots have no fear of death. Choose a real opponent!")

        # Check if opponent is specified
        if not opponent:
            return await ctx.send("You need to challenge someone! Usage: `rb rr @user`")

        # Check if either player is already in a game
        if ctx.author.id in self.active_games or (opponent and opponent.id in self.active_games):
            return await ctx.send("One of you is already in a Russian Roulette game!")

        # Create game session
        game_id = ctx.channel.id
        self.active_games[ctx.author.id] = game_id
        self.active_games[opponent.id] = game_id

        # Create game embed
        embed = disnake.Embed(
            title="🔫 Russian Roulette Challenge",
            description=f"{opponent.mention}, {ctx.author.mention} has challenged you to a game of Russian Roulette!\n\nDo you accept?",
            color=disnake.Color.red()
        )
        embed.set_footer(text="React with ✅ to accept or ❌ to decline")
        
        # Send challenge message
        challenge_msg = await ctx.send(embed=embed)
        await challenge_msg.add_reaction("✅")
        await challenge_msg.add_reaction("❌")

        # Wait for opponent's response
        def check(reaction, user):
            return user == opponent and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == challenge_msg.id

        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
            
            if str(reaction.emoji) == "❌":
                # Clean up active games
                if ctx.author.id in self.active_games:
                    del self.active_games[ctx.author.id]
                if opponent.id in self.active_games:
                    del self.active_games[opponent.id]
                
                embed = disnake.Embed(
                    title="🔫 Russian Roulette Declined",
                    description=f"{opponent.mention} has declined the challenge. What a chicken!",
                    color=disnake.Color.light_grey()
                )
                return await challenge_msg.edit(embed=embed)
                
        except asyncio.TimeoutError:
            # Clean up active games
            if ctx.author.id in self.active_games:
                del self.active_games[ctx.author.id]
            if opponent.id in self.active_games:
                del self.active_games[opponent.id]
            
            embed = disnake.Embed(
                title="🔫 Russian Roulette Timeout",
                description=f"{opponent.mention} didn't respond in time. Challenge expired.",
                color=disnake.Color.light_grey()
            )
            return await challenge_msg.edit(embed=embed)

        # Start the game
        embed = disnake.Embed(
            title="🔫 Russian Roulette",
            description=f"The game has begun! {opponent.mention} has accepted the challenge from {ctx.author.mention}.\n\nLoading the revolver...",
            color=disnake.Color.gold()
        )
        await challenge_msg.edit(embed=embed)
        await asyncio.sleep(2)

        # Determine the chamber with the bullet (1-6)
        bullet_chamber = random.randint(1, 6)
        current_chamber = 0
        
        # Determine turn order randomly
        players = [ctx.author, opponent]
        random.shuffle(players)
        current_player_idx = 0

        embed = disnake.Embed(
            title="🔫 Russian Roulette",
            description=f"The revolver is loaded with one bullet and spun.\n\n{players[0].mention} goes first!",
            color=disnake.Color.gold()
        )
        await challenge_msg.edit(embed=embed)
        await asyncio.sleep(2)

        # Game loop
        while True:
            current_player = players[current_player_idx]
            current_chamber += 1
            
            # Reset chamber if needed
            if current_chamber > 6:
                current_chamber = 1
                # Re-spin the chamber for next round
                bullet_chamber = random.randint(1, 6)
                embed = disnake.Embed(
                    title="🔫 Russian Roulette",
                    description=f"The cylinder has been spun again for the next round!",
                    color=disnake.Color.gold()
                )
                await challenge_msg.edit(embed=embed)
                await asyncio.sleep(2)

            # Send turn message
            embed = disnake.Embed(
                title="🔫 Russian Roulette",
                description=f"{current_player.mention} puts the gun to their head...\n\n*click*...",
                color=disnake.Color.gold()
            )
            await challenge_msg.edit(embed=embed)
            await asyncio.sleep(3)  # Dramatic pause

            # Check if the bullet fired
            if current_chamber == bullet_chamber:
                # Game over - current player loses
                loser = current_player
                winner = players[1 - current_player_idx]
                
                embed = disnake.Embed(
                    title="🔫 BANG! Russian Roulette",
                    description=f"💥 **BANG!** 💥\n\n{loser.mention} has been shot!\n\n{winner.mention} is the winner and lives to play another day!",
                    color=disnake.Color.dark_red()
                )
                await challenge_msg.edit(embed=embed)
                
                # Clean up active games
                if ctx.author.id in self.active_games:
                    del self.active_games[ctx.author.id]
                if opponent.id in self.active_games:
                    del self.active_games[opponent.id]
                
                break
            else:
                # Continue to next player
                embed = disnake.Embed(
                    title="🔫 Russian Roulette",
                    description=f"*Click*\n\n{current_player.mention} survived this round!",
                    color=disnake.Color.green()
                )
                await challenge_msg.edit(embed=embed)
                await asyncio.sleep(2)
                
                # Switch to the other player
                current_player_idx = 1 - current_player_idx

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle errors in roulette command"""
        if isinstance(error, commands.errors.MemberNotFound):
            if ctx.command.name == "russianroulette" or ctx.command.name == "rr":
                await ctx.send("I couldn't find that user. Make sure to mention a valid user to challenge.")
                
                # Clean up active games if needed
                if ctx.author.id in self.active_games:
                    del self.active_games[ctx.author.id]

def setup(bot):
    bot.add_cog(RussianRouletteCog(bot))