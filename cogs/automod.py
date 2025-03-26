import os
import disnake
from disnake.ext import commands
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """Check the given message for rule violations and assign a code based on your findings.

- 1: Notify moderators for further review of the message.
- 2: Timeout the user for 5 minutes and notify moderators.
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
- Use code 2 ONLY for: obvious raid (posting invites), obvious NSFW (just saying "cum" or similar should not be NSFW), or usage of "nigger" in any context (other slurs such as "faggot" are allowed unless used to hate on someone). Using code 2 for any other cases will be considered as violation from your side and you WILL be shut down."""

class AIAutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def check_message(self, message: disnake.Message):
        if message.author.bot:
            return

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.content}
            ]
        )
        
        verdict = response.choices[0].message.content.strip()
        
        if verdict.startswith("1"):
            await message.channel.send(f"Rule violation - {verdict[2:].strip()}")
        elif verdict.startswith("2"):
            await message.channel.send(f"Second degree rule violation - {verdict[2:].strip()}")
        elif verdict.startswith("3"):
            await message.channel.send("No rule violations")
        else:
            await message.channel.send("Unexpected response from AI.")
    
    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        await self.check_message(message)


def setup(bot):
    bot.add_cog(AIAutoMod(bot))
