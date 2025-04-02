import disnake
from disnake.ext import commands
import os
import sys
import shutil
import subprocess
import datetime
import platform
import asyncio
from cogs.common.base_cog import BaseCog

class UpdateCog(BaseCog):
    """Cog to handle Git updates of the bot"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.update_in_progress = False
        
    @commands.command(name="git")
    @commands.is_owner()
    async def git_command(self, ctx, action: str = None):
        """Git-related commands
        
        Available actions:
        - update: Updates the bot from GitHub repository
        """
        if not action:
            await ctx.send("Please specify an action: `update`")
            return
            
        if action.lower() == "update":
            if self.update_in_progress:
                await ctx.send("⚠️ An update is already in progress!")
                return
            self.update_in_progress = True
            try:
                await self.update_bot(ctx)
            finally:
                self.update_in_progress = False
        else:
            await ctx.send(f"Unknown action: `{action}`. Available actions: `update`")
    
    async def update_bot(self, ctx):
        """Updates the bot from GitHub"""
        # Check if running on Linux
        if platform.system() != "Linux":
            await ctx.send("❌ This command is only supported on Linux systems.")
            return
        
        # Start the update process
        update_message = await ctx.send("🔄 Starting update process...")
        
        try:
            # Get the correct bot directory
            # Find the actual bot root directory by looking for bot.py
            script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            # Verify we have the correct directory by checking for bot.py
            if not os.path.exists(os.path.join(script_dir, "bot.py")):
                # Try one level up
                script_dir = os.path.dirname(script_dir)
                if not os.path.exists(os.path.join(script_dir, "bot.py")):
                    await update_message.edit(content="❌ Error: Unable to find bot.py in the expected directory structure.")
                    return
            
            current_dir = script_dir
            
            # Log the directories for debugging
            self.logger.info(f"Current bot directory: {current_dir}")
            
            # Safety check to prevent operating on system directories
            risky_dirs = ["/", "/root", "/home", "/etc", "/usr", "/var"]
            if current_dir in risky_dirs:
                await update_message.edit(content=f"❌ Error: Detected critical system directory ({current_dir}). Update aborted for safety.")
                return
            
            home_dir = os.path.expanduser("~")
            temp_dir = os.path.join(home_dir, "downloading")
            backup_dir = os.path.join(home_dir, "old")
            clone_dir = os.path.join(temp_dir, "retardibot")
            
            # Step 1: Clone the repository to a temporary directory
            await self.update_status(update_message, "1️⃣ Cloning repository...")
            
            # Create temporary and backup directories if they don't exist
            os.makedirs(temp_dir, exist_ok=True)
            os.makedirs(backup_dir, exist_ok=True)
            
            # Remove existing temporary clone if it exists
            if os.path.exists(clone_dir):
                shutil.rmtree(clone_dir)
            
            # Clone the repository
            clone_process = await asyncio.create_subprocess_shell(
                f"git clone https://github.com/iAmScienceMan/retardibot.git {clone_dir}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await clone_process.communicate()
            
            if clone_process.returncode != 0:
                error_message = stderr.decode('utf-8')
                await update_message.edit(content=f"❌ Failed to clone repository:\n```\n{error_message}\n```")
                return
            
            # Step 2: Copy important files
            await self.update_status(update_message, "2️⃣ Preserving configuration files...")
            
            # Copy .env file
            if os.path.exists(os.path.join(current_dir, ".env")):
                shutil.copy2(os.path.join(current_dir, ".env"), os.path.join(clone_dir, ".env"))
                self.logger.info("Copied .env file to new installation")
            else:
                self.logger.warning(".env file not found in current installation")
            
            # Copy database files
            db_files = [f for f in os.listdir(current_dir) if f.endswith('.db')]
            for db_file in db_files:
                shutil.copy2(os.path.join(current_dir, db_file), os.path.join(clone_dir, db_file))
                self.logger.info(f"Copied {db_file} to new installation")
            
            # Copy config.toml if it exists
            if os.path.exists(os.path.join(current_dir, "config.toml")):
                shutil.copy2(os.path.join(current_dir, "config.toml"), os.path.join(clone_dir, "config.toml"))
                self.logger.info("Copied config.toml to new installation")
            else:
                self.logger.warning("config.toml file not found in current installation")
            
            # Step 3: Move old installation to backup
            await self.update_status(update_message, "3️⃣ Creating backup of current installation...")
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"retardibot_{timestamp}")
            
            try:
                parent_dir = os.path.dirname(current_dir)
                bot_dir_name = os.path.basename(current_dir)
                
                # Log the move operation details
                self.logger.info(f"Moving {current_dir} to {backup_path}")
                
                # First, create the backup directory
                os.makedirs(backup_path, exist_ok=True)
                
                # Copy files instead of moving to avoid issues
                for item in os.listdir(current_dir):
                    src = os.path.join(current_dir, item)
                    dst = os.path.join(backup_path, item)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
                
                self.logger.info(f"Successfully copied current installation to {backup_path}")
                
                # Remove old directory contents but keep the directory itself
                for item in os.listdir(current_dir):
                    path = os.path.join(current_dir, item)
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                
                self.logger.info("Cleared current installation directory")
                
            except Exception as e:
                self.logger.error(f"Failed to backup current installation: {e}")
                await update_message.edit(content=f"❌ Failed to backup current installation:\n```\n{str(e)}\n```")
                return
            
            # Step 4: Copy new installation to main directory
            await self.update_status(update_message, "4️⃣ Installing new version...")
            
            try:
                # Copy everything from clone_dir to current_dir
                for item in os.listdir(clone_dir):
                    src = os.path.join(clone_dir, item)
                    dst = os.path.join(current_dir, item)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
                
                self.logger.info("Successfully copied new installation to main directory")
                
                # Clean up the clone directory
                shutil.rmtree(clone_dir)
                
            except Exception as e:
                self.logger.error(f"Failed to install new version: {e}")
                await update_message.edit(content=f"❌ Failed to install new version:\n```\n{str(e)}\n```")
                return
            
            # Step 5: Install requirements and restart bot
            await self.update_status(update_message, "5️⃣ Installing dependencies and restarting...")
            
            # Install requirements
            venv_dir = os.path.join(home_dir, "venv")
            if os.path.exists(venv_dir):
                pip_path = os.path.join(venv_dir, "bin", "pip")
                requirements_path = os.path.join(current_dir, "requirements.txt")
                
                if os.path.exists(requirements_path):
                    try:
                        requirements_process = await asyncio.create_subprocess_shell(
                            f"{pip_path} install -r {requirements_path}",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        
                        stdout, stderr = await requirements_process.communicate()
                        
                        if requirements_process.returncode != 0:
                            error_message = stderr.decode('utf-8')
                            self.logger.error(f"Failed to install requirements: {error_message}")
                            # Continue anyway, as the old requirements might still work
                        else:
                            self.logger.info("Requirements installed successfully")
                    except Exception as e:
                        self.logger.error(f"Error installing requirements: {e}")
                        # Continue anyway
                else:
                    self.logger.warning("requirements.txt not found in new installation")
            else:
                self.logger.warning(f"Virtual environment not found at {venv_dir}")
            
            # Final success message
            await update_message.edit(content="✅ Update completed successfully! Restarting bot...")
            
            # Restart the bot
            python = sys.executable
            venv_python = os.path.join(venv_dir, "bin", "python")
            bot_script = os.path.join(current_dir, "bot.py")
            
            if os.path.exists(venv_python) and os.path.isfile(venv_python):
                python = venv_python
            
            self.logger.info(f"Restarting bot using {python} {bot_script}")
            
            # We need to restart in a separate process to allow this one to exit
            subprocess.Popen([python, bot_script])
            
            # Close the current bot instance
            await ctx.send("Bot is restarting. I'll be back in a moment!")
            await self.bot.close()
            
        except Exception as e:
            self.logger.error(f"Update failed: {e}", exc_info=True)
            await update_message.edit(content=f"❌ Update failed:\n```\n{str(e)}\n```")
    
    async def update_status(self, message, status):
        """Updates the status message"""
        await message.edit(content=f"🔄 {status}")
        self.logger.info(status)

def setup(bot):
    bot.add_cog(UpdateCog(bot))