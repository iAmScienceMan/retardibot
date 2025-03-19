import disnake
from disnake.ext import commands
import openai
import os
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()

class AICog(commands.Cog):
    """A cog that provides AI functionality for the bot"""
    
    def __init__(self, bot):
        self.bot = bot
        openai.api_key = os.getenv("OPENAI_KEY")
        self.user_conversations: Dict[str, List[Dict[str, str]]] = {}
    
    @commands.slash_command(description="Chat with AI")
    async def ai(self, inter: disnake.ApplicationCommandInteraction, prompt: str):
        """Simple AI chat without conversation memory"""
        await inter.response.defer()
        
        try:
            # Call OpenAI API
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )
            
            ai_response = response.choices[0].message.content
            
            # Send response
            await inter.followup.send(ai_response)
        except Exception as e:
            await inter.followup.send(f"Error: {str(e)}")
    
    @commands.slash_command(description="Have a conversation with AI (with memory)")
    async def chat(self, inter: disnake.ApplicationCommandInteraction, message: str):
        """AI chat with conversation memory"""
        await inter.response.defer()
        user_id = str(inter.author.id)
        
        # Initialize or retrieve conversation history
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = [{"role": "system", "content": "You are a helpful assistant."}]
        
        # Add user message to history
        self.user_conversations[user_id].append({"role": "user", "content": message})
        
        try:
            # Call API with conversation history
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=self.user_conversations[user_id],
                max_tokens=500
            )
            
            ai_response = response.choices[0].message.content
            
            # Add AI response to conversation history
            self.user_conversations[user_id].append({"role": "assistant", "content": ai_response})
            
            # Trim history if it gets too long (to manage token limits)
            if len(self.user_conversations[user_id]) > 10:
                # Keep system message and last 9 exchanges
                self.user_conversations[user_id] = [self.user_conversations[user_id][0]] + self.user_conversations[user_id][-9:]
            
            await inter.followup.send(ai_response)
        except Exception as e:
            await inter.followup.send(f"Error: {str(e)}")

    @commands.slash_command(description="Reset your conversation with the AI")
    async def reset_chat(self, inter: disnake.ApplicationCommandInteraction):
        """Reset the conversation history for a user"""
        user_id = str(inter.author.id)
        
        if user_id in self.user_conversations:
            # Keep only the system message
            system_message = self.user_conversations[user_id][0]
            self.user_conversations[user_id] = [system_message]
            await inter.response.send_message("Your conversation history has been reset.")
        else:
            await inter.response.send_message("You don't have any conversation history to reset.")

    @commands.slash_command(description="Analyze sentiment of a message")
    async def analyze_sentiment(self, inter: disnake.ApplicationCommandInteraction, text: str):
        """Analyze the sentiment of a message using AI"""
        await inter.response.defer()
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a sentiment analyzer. Analyze the sentiment of the given text and respond with only one word: 'positive', 'negative', or 'neutral'."},
                    {"role": "user", "content": text}
                ],
                max_tokens=5
            )
            
            sentiment = response.choices[0].message.content.strip().lower()
            
            emoji = "😐"
            if "positive" in sentiment:
                emoji = "😄"
            elif "negative" in sentiment:
                emoji = "😟"
                
            await inter.followup.send(f"Sentiment: {sentiment.capitalize()} {emoji}")
        except Exception as e:
            await inter.followup.send(f"Error: {str(e)}")

def setup(bot):
    bot.add_cog(AICog(bot))