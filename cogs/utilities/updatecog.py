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
    
    def find_bot_root(self):
        """Find the bot's root directory by searching for bot.py"""
        # Start with the directory of this file
        current_path = os.path.abspath(__file__)
        
        # Get the current working directory as a fallback
        cwd = os.getcwd()
        
        # Log the starting points
        self.logger.info(f"Starting directory search from: {current_path}")
        self.logger.info(f"Current working directory: {cwd}")
        
        # First check: Is bot.py in the current working directory?
        if os.path.exists(os.path.join(cwd, "bot.py")):
            self.logger.info(f"Found bot.py in current working directory")
            return cwd
        
        # Start from this file's directory and work upwards
        while True:
            # Get the directory containing the current path
            dir_path = os.path.dirname(current_path)
            
            # If we're at the root directory, stop searching
            if dir_path == current_path:
                break
                
            # Check if bot.py exists in this directory
            if os.path.exists(os.path.join(dir_path, "bot.py")):
                self.logger.info(f"Found bot.py in: {dir_path}")
                return dir_path
                
            # Move up one directory
            current_path = dir_path
            
            # Avoid infinite loops by checking if we've reached the filesystem root
            if dir_path == os.path.dirname(dir_path):
                break
        
        # Alternative approach: Search common locations
        possible_paths = [
            os.path.expanduser("~/retardibot"),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        ]
        
        for path in possible_paths:
            if os.path.exists(os.path.join(path, "bot.py")):
                self.logger.info(f"Found bot.py in: {path}")
                return path
        
        # If we get here, we couldn't find the bot directory
        return None
    
    async def update_bot(self, ctx):
        """Updates the bot from GitHub"""
        # Check if running on Linux
        if platform.system() != "Linux":
            await ctx.send("❌ This command is only supported on Linux systems.")
            return
        
        # Start the update process
        update_message = await ctx.send("🔄 Starting update process...")
        
        try:
            # Find the bot root directory
            current_dir = self.find_bot_root()
            
            if not current_dir:
                await update_message.edit(content="❌ Error: Unable to find bot.py. Please run this command from the bot's directory.")
                return
                
            self.logger.info(f"Bot root directory: {current_dir}")
            
            # Print the directory structure for debugging
            self.logger.info("Directory structure:")
            for root, dirs, files in os.walk(current_dir, topdown=True, followlinks=False):
                level = root.replace(current_dir, '').count(os.sep)
                indent = ' ' * 4 * level
                self.logger.info(f"{indent}{os.path.basename(root)}/")
                sub_indent = ' ' * 4 * (level + 1)
                for f in files:
                    self.logger.info(f"{sub_indent}{f}")
            
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
            
            # Step 3: Create backup
            await self.update_status(update_message, "3️⃣ Creating backup of current installation...")
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"retardibot_{timestamp}")
            
            try:
                # Create backup directory
                os.makedirs(backup_path, exist_ok=True)
                
                # Copy all files from current directory to backup
                for item in os.listdir(current_dir):
                    s = os.path.join(current_dir, item)
                    d = os.path.join(backup_path, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)
                
                self.logger.info(f"Created backup at {backup_path}")
                
            except Exception as e:
                self.logger.error(f"Failed to create backup: {e}")
                await update_message.edit(content=f"❌ Failed to create backup:\n```\n{str(e)}\n```")
                return
                
            # Step 4: Remove contents of current directory (except for hidden files)
            await self.update_status(update_message, "4️⃣ Preparing for new version...")
            
            try:
                for item in os.listdir(current_dir):
                    # Skip hidden files/dirs to avoid removing .git
                    if item.startswith('.'):
                        continue
                        
                    path = os.path.join(current_dir, item)
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                        
                self.logger.info("Cleared current directory for update")
                
            except Exception as e:
                self.logger.error(f"Failed to clear current directory: {e}")
                await update_message.edit(content=f"❌ Failed to prepare for new version:\n```\n{str(e)}\n```")
                return
                
            # Step 5: Copy new version to current directory
            await self.update_status(update_message, "5️⃣ Installing new version...")
            
            try:
                for item in os.listdir(clone_dir):
                    s = os.path.join(clone_dir, item)
                    d = os.path.join(current_dir, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)
                        
                self.logger.info("Copied new version to current directory")
                
            except Exception as e:
                self.logger.error(f"Failed to install new version: {e}")
                await update_message.edit(content=f"❌ Failed to install new version:\n```\n{str(e)}\n```")
                return
                
            # Step 6: Clean up and install dependencies
            await self.update_status(update_message, "6️⃣ Installing dependencies...")
            
            # Clean up clone directory
            try:
                shutil.rmtree(clone_dir)
                self.logger.info("Cleaned up temporary files")
            except Exception as e:
                self.logger.warning(f"Failed to clean up temporary files: {e}")
                # Continue anyway
            
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