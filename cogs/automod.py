import os
import disnake
from disnake.ext import commands
from openai import OpenAI
from dotenv import load_dotenv
import datetime

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """Check the given message for rule violations and assign a code based on your findings.

- 1: Notify moderators without pinging them for further review of the message.
- 2: Notify moderators with ping for more serious violations.
- 3: No rule violations detected.

# Steps

1. Analyze the content of the message.
2. Determine if there are any rule violations.
3. Assign the appropriate code (1, 2, or 3) based on the findings.

# Output Format

Single integer (1, 2, or 3) indicating the action to be taken based on rule evaluation followed by the reason in quotation marks. No reason is required when code 3.

# Notes

- Reason is what the user & moderation sees when code 1 or 2. Do not state that you're notifying moderators in the reason.
- Use as less tokens as possible.
- Consider edge cases where messages are ambiguous and err on the side of caution.
- Use code 2 ONLY for: obvious raid (posting invites), obvious NSFW (just saying "cum" or similar should not be NSFW), or usage of "nigger" in any context (other slurs such as "faggot" are allowed unless used to hate on someone)."""

class AIAutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mod_role_id = 1354483445769830550
        self.mod_channel_id = 1354484518903484457
    
    async def check_message(self, message: disnake.Message):
        if message.author.bot:
            return
        
        # Skip messages from moderators to prevent false positives
        if isinstance(message.author, disnake.Member):
            mod_role = disnake.utils.get(message.author.roles, id=self.mod_role_id)
            if mod_role:
                return
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": message.content}
                ]
            )
            
            verdict = response.choices[0].message.content.strip()
            
            # Parse the response
            if verdict.startswith("1") or verdict.startswith("2"):
                # Extract the reason if provided
                parts = verdict.split(" ", 1)
                code = parts[0].strip()
                reason = parts[1].strip(' "\'') if len(parts) > 1 else "No reason provided"
                
                # Get the moderator channel
                mod_channel = message.guild.get_channel(self.mod_channel_id)
                if not mod_channel:
                    return
                
                # Create an embed for the notification
                embed = disnake.Embed(
                    title=f"AutoMod Alert - Code {code}",
                    description=f"**Reason:** {reason}",
                    color=disnake.Color.red() if code == "2" else disnake.Color.orange()
                )
                
                embed.add_field(name="User", value=f"{message.author.mention} ({message.author.id})", inline=True)
                embed.add_field(name="Channel", value=f"{message.channel.mention}", inline=True)
                embed.add_field(name="Message", value=f"{message.content[:1024]}", inline=False)
                embed.add_field(name="Link", value=f"[Jump to Message]({message.jump_url})", inline=False)
                
                embed.set_footer(text=f"Message ID: {message.id}")
                embed.timestamp = datetime.datetime.utcnow()
                
                if message.author.avatar:
                    embed.set_thumbnail(url=message.author.avatar.url)
                
                # Code 1: Just send a message without ping
                if code == "1":
                    await mod_channel.send(embed=embed)
                
                # Code 2: Ping mods but don't timeout
                elif code == "2":
                    await mod_channel.send(
                        content=f"<@&{self.mod_role_id}> Auto-moderation alert",
                        embed=embed
                    )
            
            # Code 3: No action needed
                
        except Exception as e:
            pass
    
    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        try:
            # Skip DMs
            if not isinstance(message.channel, disnake.TextChannel):
                return
                
            await self.check_message(message)
        except Exception:
            pass
    
    @commands.Cog.listener()
    async def on_ready(self):
        print("AIAutoMod cog is ready!")
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def automod_test(self, ctx, *, message: str):
        """Test the automod system with a message (admin only)"""
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": message}
                ]
            )
            
            verdict = response.choices[0].message.content.strip()
            
            # Create test embed
            embed = disnake.Embed(
                title="AutoMod Test Result",
                description=f"**Input:** {message}\n\n**Raw Response:** {verdict}",
                color=disnake.Color.blue()
            )
            
            if verdict.startswith("1"):
                embed.add_field(name="Result", value="Code 1: Will notify moderators without ping", inline=False)
                parts = verdict.split(" ", 1)
                reason = parts[1].strip(' "\'') if len(parts) > 1 else "No reason provided"
                embed.add_field(name="Reason", value=reason, inline=False)
                
            elif verdict.startswith("2"):
                embed.add_field(name="Result", value="Code 2: Will ping moderators but not timeout", inline=False)
                parts = verdict.split(" ", 1)
                reason = parts[1].strip(' "\'') if len(parts) > 1 else "No reason provided"
                embed.add_field(name="Reason", value=reason, inline=False)
                
            elif verdict.startswith("3"):
                embed.add_field(name="Result", value="Code 3: No action needed", inline=False)
                
            else:
                embed.add_field(name="Result", value="Unexpected response format", inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def automod_debug(self, ctx):
        """Show debugging information about the automod configuration"""
        embed = disnake.Embed(
            title="AutoMod Debug Information",
            color=disnake.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )
        
        # Check OpenAI API
        api_key_status = "✅ Configured" if os.getenv("OPENAI_API_KEY") else "❌ Missing"
        embed.add_field(name="OpenAI API Key", value=api_key_status, inline=False)
        
        # Check mod role
        mod_role = ctx.guild.get_role(self.mod_role_id)
        role_status = f"✅ Found: {mod_role.name}" if mod_role else f"❌ Not found: ID {self.mod_role_id}"
        embed.add_field(name="Moderator Role", value=role_status, inline=False)
        
        # Check mod channel
        mod_channel = ctx.guild.get_channel(self.mod_channel_id)
        channel_status = f"✅ Found: {mod_channel.mention}" if mod_channel else f"❌ Not found: ID {self.mod_channel_id}"
        embed.add_field(name="Moderator Channel", value=channel_status, inline=False)
        
        # Check bot permissions
        bot_member = ctx.guild.get_member(self.bot.user.id)
        if bot_member:
            perms = []
            
            if bot_member.guild_permissions.moderate_members:
                perms.append("✅ Timeout Members")
            else:
                perms.append("❌ Timeout Members")
                
            if bot_member.guild_permissions.send_messages:
                perms.append("✅ Send Messages")
            else:
                perms.append("❌ Send Messages")
                
            if bot_member.guild_permissions.embed_links:
                perms.append("✅ Embed Links")
            else:
                perms.append("❌ Embed Links")
            
            embed.add_field(name="Bot Permissions", value="\n".join(perms), inline=False)
        else:
            embed.add_field(name="Bot Permissions", value="❌ Could not find bot member", inline=False)
        
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(AIAutoMod(bot))