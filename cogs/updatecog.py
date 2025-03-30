import disnake
from disnake.ext import commands
import os
import shutil
import subprocess
import random
import asyncio
import glob
import sys
import platform
import tempfile
from pathlib import Path

class GitUpdateCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.dev_logger.getChild('gitupdate')
        self.repo_url = "https://github.com/iAmScienceMan/retardibot.git"
        self.branch = "main"
        self.files_to_preserve = ['.env', 'config.json'] 
        # DB files will be detected dynamically
        
    @commands.command(name="git")
    @commands.is_owner()
    async def git_command(self, ctx, action=None):
        """Git operations for the bot"""
        if action is None:
            await ctx.send("Please specify an action: `update`")
            return
            
        if action.lower() == "update":
            await self.update_bot(ctx)
        else:
            await ctx.send(f"Unknown git action: `{action}`")
    
    async def update_bot(self, ctx):
        """Update the bot to the latest version from GitHub"""
        # Initialize response message
        msg = await ctx.send("🔄 Initializing bot update...")
        
        # Set up directories
        current_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        home_dir = os.path.expanduser("~")
        random_digits = random.randint(100, 999)
        update_dir = os.path.join(home_dir, f"updated{random_digits}")
        
        # Update status message
        await msg.edit(content=f"🔄 Setting up update directory: `{update_dir}`")
        self.logger.info(f"Update directory: {update_dir}")
        
        try:
            # Create update directory
            os.makedirs(update_dir, exist_ok=True)
            
            # Clone repo to update directory
            await msg.edit(content=f"🔄 Cloning repository from {self.repo_url}...")
            self.logger.info(f"Cloning repository to {update_dir}")
            
            # Run git clone with appropriate shell setting based on platform
            use_shell = platform.system() == "Windows"
            clone_process = subprocess.Popen(
                ["git", "clone", "-b", self.branch, self.repo_url, update_dir],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=use_shell
            )
            
            # Wait for clone to complete
            stdout, stderr = clone_process.communicate()
            
            if clone_process.returncode != 0:
                self.logger.error(f"Git clone failed: {stderr}")
                await msg.edit(content=f"❌ Git clone failed:\n```\n{stderr}\n```")
                # Clean up
                shutil.rmtree(update_dir, ignore_errors=True)
                return
            
            # Find all database files
            db_files = glob.glob(os.path.join(current_dir, "*.db"))
            self.logger.info(f"Found DB files: {db_files}")
            
            # Copy preserved files
            await msg.edit(content="🔄 Copying configuration files...")
            
            # Add DB files to the list of files to preserve
            files_to_copy = self.files_to_preserve + [os.path.basename(db) for db in db_files]
            
            for file in files_to_copy:
                source_path = os.path.join(current_dir, file)
                dest_path = os.path.join(update_dir, file)
                
                if os.path.exists(source_path):
                    self.logger.info(f"Copying {file} to update directory")
                    shutil.copy2(source_path, dest_path)
                else:
                    self.logger.warning(f"File not found: {source_path}")
            
            # Verify update directory has all required files
            await msg.edit(content="🔄 Verifying update...")
            
            # Check for essential files like bot.py
            if not os.path.exists(os.path.join(update_dir, "bot.py")):
                self.logger.error("bot.py not found in update directory")
                await msg.edit(content="❌ Update failed: bot.py not found in the cloned repository")
                # Clean up
                shutil.rmtree(update_dir, ignore_errors=True)
                return
            
            # Execute restart script that will terminate this instance and start from new location
            await msg.edit(content="✅ Update complete! Restarting bot from updated location...")
            
            # Create restart script based on platform
            restart_script_path = self._create_restart_script(update_dir)
            self.logger.info(f"Created restart script: {restart_script_path}")
            
            # Run the restart script
            self.logger.info("Executing restart script")
            if platform.system() == "Windows":
                subprocess.Popen(["powershell", "-File", restart_script_path], 
                                 creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                os.chmod(restart_script_path, 0o755)
                subprocess.Popen([restart_script_path], start_new_session=True)
            
            # Final message before shutdown
            await msg.edit(content="✅ Update successful! Bot is restarting with the new version...")
            
            # Wait a moment before shutting down
            await asyncio.sleep(3)
            
            # Exit the current process
            self.logger.info("Shutting down current bot instance for update")
            await self.bot.close()
            
        except Exception as e:
            self.logger.error(f"Update failed: {str(e)}", exc_info=True)
            await msg.edit(content=f"❌ Update failed: {str(e)}")
            # Clean up
            shutil.rmtree(update_dir, ignore_errors=True)
    
    def _create_restart_script(self, update_dir):
        """Create a script that will restart the bot from the new location"""
        # Get current Python executable
        python_exe = sys.executable
        
        # Determine if we're inside a virtual environment
        in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        venv_path = sys.prefix if in_venv else None
        
        # Create temporary script file with appropriate extension
        is_windows = platform.system() == "Windows"
        script_ext = ".ps1" if is_windows else ".sh"
        fd, script_path = tempfile.mkstemp(suffix=script_ext, prefix="restart_bot_", 
                                          dir=os.path.expanduser("~"))
        os.close(fd)
        
        if is_windows:
            # PowerShell script for Windows
            with open(script_path, 'w') as f:
                f.write("# This script restarts the bot from the updated location\n\n")
                
                # Allow time for the current process to exit
                f.write("Write-Host 'Waiting for current bot process to exit...'\n")
                f.write("Start-Sleep -Seconds 5\n\n")
                
                # Change to the new directory
                f.write(f"Set-Location -Path '{update_dir}'\n\n")
                
                # If we were in a virtual environment, activate it
                if in_venv:
                    venv_activate = os.path.join(venv_path, "Scripts", "Activate.ps1")
                    f.write(f". '{venv_activate}'\n\n")
                
                # Start the bot
                f.write(f"& '{python_exe}' bot.py\n")
                
                # Self-destruct the script
                f.write("\n# Remove this script\n")
                f.write(f"Remove-Item -Path '{script_path}'\n")
        else:
            # Bash script for Unix-like systems
            with open(script_path, 'w') as f:
                f.write("#!/bin/bash\n")
                f.write("# This script restarts the bot from the updated location\n\n")
                
                # Allow time for the current process to exit
                f.write("echo 'Waiting for current bot process to exit...'\n")
                f.write("sleep 5\n\n")
                
                # Change to the new directory
                f.write(f"cd {update_dir}\n\n")
                
                # If we were in a virtual environment, activate it
                if in_venv:
                    venv_activate = os.path.join(venv_path, "bin", "activate")
                    f.write(f"source {venv_activate}\n\n")
                
                # Start the bot
                f.write(f"{python_exe} bot.py\n")
                
                # Self-destruct the script
                f.write("\n# Remove this script\n")
                f.write(f"rm {script_path}\n")
        
        return script_path

def setup(bot):
    bot.add_cog(GitUpdateCog(bot))