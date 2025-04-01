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
import datetime
from pathlib import Path
from cogs.common.base_cog import BaseCog

class GitUpdateCog(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.repo_url = "https://github.com/iAmScienceMan/retardibot.git"
        self.branch = "main"
        self.files_to_preserve = ['.env', 'config.toml']
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
        
        # Create old versions directory if it doesn't exist
        old_versions_dir = os.path.join(home_dir, "old")
        os.makedirs(old_versions_dir, exist_ok=True)
        
        # Generate timestamp for old version
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        old_version_dir = os.path.join(old_versions_dir, f"retardibot_{timestamp}")
        
        # Set up new update directory
        random_digits = random.randint(100, 999)
        update_dir = os.path.join(home_dir, f"updated{random_digits}")
        
        # Update status message
        await msg.edit(content=f"🔄 Setting up update directories...")
        self.logger.info(f"Update directory: {update_dir}")
        self.logger.info(f"Old version directory: {old_version_dir}")
        
        try:
            # Create update directory
            os.makedirs(update_dir, exist_ok=True)
            
            # Save current version to old_version_dir
            await msg.edit(content=f"🔄 Backing up current version to {old_version_dir}...")
            self.logger.info(f"Backing up current version to {old_version_dir}")
            
            # Create the old version directory
            os.makedirs(old_version_dir, exist_ok=True)
            
            # Copy current installation to old_version_dir (excluding large dirs like venv)
            backup_successful = True
            for item in os.listdir(current_dir):
                if item not in ['.git', '__pycache__', 'venv']:
                    src_path = os.path.join(current_dir, item)
                    dst_path = os.path.join(old_version_dir, item)
                    
                    try:
                        if os.path.isdir(src_path):
                            self.logger.info(f"Copying directory {item} to backup")
                            shutil.copytree(src_path, dst_path)
                        else:
                            self.logger.info(f"Copying file {item} to backup")
                            shutil.copy2(src_path, dst_path)
                    except Exception as e:
                        self.logger.error(f"Error backing up {item}: {str(e)}")
                        backup_successful = False
            
            if not backup_successful:
                self.logger.warning("Some errors occurred during backup, but continuing with update")
            
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
            await msg.edit(content="🔄 Copying configuration files and databases...")
            
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
                
            # Create restart script based on platform
            restart_script_path = self._create_restart_script(update_dir, current_dir)
            self.logger.info(f"Created restart script: {restart_script_path}")
            
            # Execute restart script that will terminate this instance and start from new location
            await msg.edit(content="✅ Update complete! Restarting bot from updated location...")
            
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
            # Clean up but leave the backup
            shutil.rmtree(update_dir, ignore_errors=True)
    
    def _create_restart_script(self, update_dir, current_dir):
        """Create a script that will restart the bot from the new location"""
        # Set path to the venv in home directory
        home_dir = os.path.expanduser("~")
        venv_dir = os.path.join(home_dir, "venv")
        
        # Generate timestamp for old version (same format as in update_bot)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        old_versions_dir = os.path.join(home_dir, "old")
        old_version_dir = os.path.join(old_versions_dir, f"retardibot_{timestamp}")
        
        # Determine Python executable path based on platform
        if platform.system() == "Windows":
            python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
        else:
            python_exe = os.path.join(venv_dir, "bin", "python")
        
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
                
                # Create old version directory if it doesn't exist yet
                f.write(f"if (-not (Test-Path '{old_versions_dir}')) {{\n")
                f.write(f"    New-Item -Path '{old_versions_dir}' -ItemType Directory -Force\n")
                f.write(f"}}\n\n")
                
                # Ensure the specific backup dir doesn't exist
                f.write(f"if (Test-Path '{old_version_dir}') {{\n")
                f.write(f"    $i = 1\n")
                f.write(f"    while (Test-Path '{old_version_dir}_$i') {{\n")
                f.write(f"        $i++\n")
                f.write(f"    }}\n")
                f.write(f"    $old_version_dir = '{old_version_dir}_' + $i\n")
                f.write(f"}} else {{\n")
                f.write(f"    $old_version_dir = '{old_version_dir}'\n")
                f.write(f"}}\n\n")
                
                # Move the old installation to backup folder
                f.write(f"Write-Host 'Moving old bot installation to $old_version_dir...'\n")
                f.write(f"if (Test-Path '{current_dir}') {{\n")
                f.write(f"    try {{\n")
                f.write(f"        # Create target directory\n")
                f.write(f"        New-Item -Path $old_version_dir -ItemType Directory -Force\n")
                f.write(f"        # Move content instead of deleting\n") 
                f.write(f"        Get-ChildItem -Path '{current_dir}' -Exclude '.git','__pycache__','venv' | Move-Item -Destination $old_version_dir -Force\n")
                f.write(f"        Write-Host 'Old installation moved to backup successfully'\n")
                f.write(f"    }} catch {{\n")
                f.write(f"        Write-Host 'Warning: Could not move old installation: $_'\n")
                f.write(f"    }}\n")
                f.write(f"}}\n\n")
                
                # Move files from update_dir to current_dir
                f.write(f"Write-Host 'Moving updated files to original location...'\n")
                f.write(f"Get-ChildItem -Path '{update_dir}' -Force | Move-Item -Destination '{current_dir}' -Force\n\n")
                
                # Remove the temporary update directory
                f.write(f"Write-Host 'Cleaning up temporary directories...'\n")
                f.write(f"if (Test-Path '{update_dir}') {{\n")
                f.write(f"    Remove-Item -Path '{update_dir}' -Recurse -Force\n")
                f.write(f"}}\n\n")
                
                # Change to the original directory
                f.write(f"Set-Location -Path '{current_dir}'\n\n")
                
                # Check if venv exists
                f.write(f"if (Test-Path '{venv_dir}') {{\n")
                # Activate venv and run bot
                f.write(f"    Write-Host 'Using virtual environment at {venv_dir}'\n")
                f.write(f"    & '{python_exe}' bot.py\n")
                f.write("} else {\n")
                # Fallback to system Python
                f.write(f"    Write-Host 'Virtual environment not found at {venv_dir}, using system Python'\n")
                f.write(f"    python bot.py\n")
                f.write("}\n\n")
                
                # Self-destruct the script
                f.write("# Remove this script\n")
                f.write(f"Remove-Item -Path '{script_path}'\n")
        else:
            # Bash script for Unix-like systems
            with open(script_path, 'w') as f:
                f.write("#!/bin/bash\n")
                f.write("# This script restarts the bot from the updated location\n\n")
                
                # Allow time for the current process to exit
                f.write("echo 'Waiting for current bot process to exit...'\n")
                f.write("sleep 5\n\n")
                
                # Create old versions directory if it doesn't exist
                f.write(f"mkdir -p \"{old_versions_dir}\"\n\n")
                
                # Handle case where backup dir already exists
                f.write(f"old_version_dir=\"{old_version_dir}\"\n")
                f.write("i=1\n")
                f.write("while [ -d \"$old_version_dir\" ]; do\n")
                f.write("    old_version_dir=\"{old_version_dir}_$i\"\n")
                f.write("    i=$((i+1))\n")
                f.write("done\n\n")
                
                # Move old repository directory to backup
                f.write(f"echo 'Moving old bot installation to $old_version_dir...'\n")
                f.write(f"if [ -d \"{current_dir}\" ]; then\n")
                f.write(f"    mkdir -p \"$old_version_dir\"\n")
                f.write(f"    # Move all files except .git, __pycache__, venv to backup\n")
                f.write(f"    find \"{current_dir}\" -maxdepth 1 -not -name '.git' -not -name '__pycache__' -not -name 'venv' -not -path \"{current_dir}\" -exec mv {{}} \"$old_version_dir/\" \\;\n")
                f.write(f"    echo 'Old installation moved to backup successfully'\n")
                f.write(f"fi\n\n")
                
                # Move files from update_dir to current_dir
                f.write(f"echo 'Moving updated files to original location...'\n")
                f.write(f"cp -a {update_dir}/* {update_dir}/.* {current_dir}/ 2>/dev/null || :\n\n")
                
                # Remove the temporary update directory
                f.write(f"echo 'Cleaning up temporary directories...'\n")
                f.write(f"if [ -d \"{update_dir}\" ]; then\n")
                f.write(f"    rm -rf \"{update_dir}\"\n")
                f.write(f"fi\n\n")
                
                # Change to the original directory
                f.write(f"cd {current_dir}\n\n")
                
                # Check if venv exists
                f.write(f"if [ -d \"{venv_dir}\" ]; then\n")
                # Activate venv and run bot
                f.write(f"    echo 'Using virtual environment at {venv_dir}'\n")
                f.write(f"    {python_exe} bot.py\n")
                f.write("else\n")
                # Fallback to system Python
                f.write(f"    echo 'Virtual environment not found at {venv_dir}, using system Python'\n")
                f.write(f"    python3 bot.py\n")
                f.write("fi\n\n")
                
                # Self-destruct the script
                f.write("# Remove this script\n")
                f.write(f"rm {script_path}\n")
        
        return script_path

def setup(bot):
    bot.add_cog(GitUpdateCog(bot))