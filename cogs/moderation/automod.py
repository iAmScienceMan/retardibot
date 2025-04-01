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
        self.mod_role_id = automod_config.get("mod_role_id", 1354483445769830550)
        self.alert_channel_id = automod_config.get("alert_channel_id", 1354484518903484457)
        self.system_prompt = automod_config.get("system_prompt", """Check the given message for rule violations and assign a code based on your findings.

- 1: Notify moderators for further review of the message.
- 2: Ping the moderators for further review of the message.
- 3: No rule violations detected.

# Steps

1. Analyze the content of the message.
2. Determine if there are any rule violations.
3. Assign the appropriate code (1, 2, or 3) based on the findings.

# Output Format

Single integer (1, 2, or 3) indicating the action to be taken based on rule evaluation followed by the reason in quotation marks. No reason is required when code 3.

# Notes

- Reason is what the moderation sees when code 1 or 2. Do not state that you're notifying moderators in the reason.
- Use as less tokens as possible.
- Consider edge cases where messages are ambiguous and err on the side of caution.
- Use code 2 ONLY for: obvious raid (posting invites), obvious NSFW (just saying "cum" or similar should not be NSFW), or usage of slurs to hate on someone (just saying a slur shouldn't be bad at all). Using code 2 for any other cases will be considered as violation from your side and you WILL be shut down.""")

        self.logger.debug(f"Set chanel: notification channel {self.alert_channel_id} for automod")

    async def send_to_openai(self, system_prompt, user_message):
        """Send message to OpenAI GPT-4o-mini for analysis"""
        try:
            response = await self.aclient.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=100,
                temperature=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error(f"Error querying OpenAI: {e}")
            return "3 Error processing message."

    async def parse_openai_response(self, response):
        """Parse the OpenAI response to get the score and reason"""
        try:
            # The expected format is "N Reason." where N is 1, 2, or 3
            first_char = response[0]

            if first_char not in ['1', '2', '3']:
                self.logger.error(f"Invalid response format: {response}")
                return 3, "Error parsing response"

            score = int(first_char)
            reason = response[1:].strip()

            return score, reason
        except Exception as e:
            self.logger.error(f"Error parsing OpenAI response: {e}")
            return 3, "Error parsing response"

    def has_mod_role(self, member):
        """Check if a member has the mod role"""
        if not member or not member.guild:
            return False
            
        mod_role = member.guild.get_role(self.mod_role_id)
        if not mod_role:
            return False
            
        return mod_role in member.roles

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

        # Send to OpenAI for analysis
        openai_response = await self.send_to_openai(self.system_prompt, content)

        # Parse the response
        score, reason = await self.parse_openai_response(openai_response)

        # Handle the score
        if score == 1:
            # Low severity - notify mods without ping
            await self.send_mod_notification(message, reason, False)
        elif score == 2:
            # High severity - notify mods with ping
            await self.send_mod_notification(message, reason, True)
        # If score is 3, do nothing

    async def send_mod_notification(self, message, reason, ping_mods):
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
                color=disnake.Color.red() if ping_mods else disnake.Color.orange(),
                timestamp=message.created_at
            )

            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Channel", value=message.channel.mention, inline=True)
            embed.add_field(name="Author", value=f"{message.author.mention} ({message.author.id})", inline=True)
            embed.add_field(name="Jump to Message", value=f"[Click here]({message.jump_url})", inline=False)

            embed.set_footer(text=f"Severity: {'HIGH' if ping_mods else 'LOW'}")

            if message.author.avatar:
                embed.set_thumbnail(url=message.author.avatar.url)

            # Send embed with or without ping
            if ping_mods:
                mod_role = message.guild.get_role(self.mod_role_id)
                if mod_role:
                    await alert_channel.send(f"{mod_role.mention} Moderation required!", embed=embed)
                else:
                    self.logger.error(f"Notification role {self.mod_role_id} not found")
                    await alert_channel.send(embed=embed)
            else:
                await alert_channel.send(embed=embed)

        except Exception as e:
            self.logger.error(f"Error sending notification: {e}")

def setup(bot):
    bot.add_cog(AutoModCog(bot))