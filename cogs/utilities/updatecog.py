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
            # Step 1: Clone the repository to a temporary directory
            await self.update_status(update_message, "1️⃣ Cloning repository...")
            
            home_dir = os.path.expanduser("~")
            temp_dir = os.path.join(home_dir, "downloading")
            backup_dir = os.path.join(home_dir, "old")
            clone_dir = os.path.join(temp_dir, "retardibot")
            current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
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
                shutil.move(current_dir, backup_path)
                self.logger.info(f"Moved current installation to {backup_path}")
            except Exception as e:
                self.logger.error(f"Failed to move current installation to backup: {e}")
                await update_message.edit(content=f"❌ Failed to backup current installation:\n```\n{str(e)}\n```")
                return
            
            # Step 4: Move new installation to main directory
            await self.update_status(update_message, "4️⃣ Installing new version...")
            
            try:
                shutil.move(clone_dir, os.path.dirname(current_dir))
                self.logger.info("Moved new installation to main directory")
            except Exception as e:
                self.logger.error(f"Failed to move new installation: {e}")
                # Try to restore the old installation
                try:
                    shutil.move(backup_path, current_dir)
                    self.logger.info("Restored previous installation from backup")
                except Exception as restore_error:
                    self.logger.critical(f"Failed to restore previous installation: {restore_error}")
                
                await update_message.edit(content=f"❌ Failed to install new version:\n```\n{str(e)}\n```")
                return
            
            # Step 5: Install requirements and restart bot
            await self.update_status(update_message, "5️⃣ Installing dependencies and restarting...")
            
            # Install requirements
            venv_dir = os.path.join(home_dir, "venv")
            if os.path.exists(venv_dir):
                pip_path = os.path.join(venv_dir, "bin", "pip")
                requirements_path = os.path.join(os.path.dirname(current_dir), "retardibot", "requirements.txt")
                
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
            bot_script = os.path.join(os.path.dirname(current_dir), "retardibot", "bot.py")
            
            if os.path.exists(venv_python):
                python = venv_python
            
            self.logger.info(f"Restarting bot using {python} {bot_script}")
            
            # We need to restart in a separate process to allow this one to exit
            subprocess.Popen([python, bot_script])
            
            # Close the current bot instance
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