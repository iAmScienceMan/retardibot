import disnake
from disnake.ext import commands
import os
import subprocess
import random
import asyncio
import platform
import tempfile
import datetime
import shutil
from pathlib import Path
from cogs.common.base_cog import BaseCog

class GitUpdateCog(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.repo_url = "https://github.com/iAmScienceMan/retardibot.git"
        self.branch = "main"
        
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
        # Windows check - fail early with clear message
        if platform.system() == "Windows":
            await ctx.send("⚠️ This update script is designed for Linux systems. Windows is not supported.")
            return
        
        # Initialize response message
        msg = await ctx.send("🔄 Initializing bot update...")
        
        # Set up directories
        home_dir = os.path.expanduser("~")
        current_dir = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.logger.info(f"Current directory: {current_dir}")
        
        # Create a unique backup directory
        backup_dir = os.path.join(home_dir, "retardibot_backups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"backup_{timestamp}")
        
        # Create a unique temp directory for cloning
        temp_dir = os.path.join(home_dir, f"retardibot_update_{timestamp}")
        
        try:
            # Step 1: Create complete backup
            await msg.edit(content="🔄 Creating complete backup...")
            self.logger.info(f"Creating backup at {backup_path}")
            
            # Create backup script and run it
            backup_script = self._create_backup_script(current_dir, backup_path)
            await self._run_script(backup_script)
            
            # Verify backup was created
            if not os.path.exists(backup_path):
                raise Exception(f"Backup directory was not created at {backup_path}")
            
            await msg.edit(content=f"✅ Backup created at {backup_path}")
            
            # Step 2: Clone the repository to temp directory
            await msg.edit(content=f"🔄 Cloning repository from {self.repo_url}...")
            self.logger.info(f"Cloning to {temp_dir}")
            
            # Run git clone
            clone_cmd = f"git clone -b {self.branch} {self.repo_url} {temp_dir}"
            process = await asyncio.create_subprocess_shell(
                clone_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                raise Exception(f"Git clone failed: {error_msg}")
            
            # Step 3: Preserve config files & databases
            await msg.edit(content=f"🔄 Preserving configuration files and databases...")
            self.logger.info("Copying config files and databases")
            
            # Find all .env, .db files and config.toml
            preserve_files = []
            for root, dirs, files in os.walk(current_dir):
                for file in files:
                    if file.endswith(('.env', '.db')) or file == 'config.toml':
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, current_dir)
                        preserve_files.append(rel_path)
            
            # Copy these files to the temp directory
            for rel_path in preserve_files:
                source = os.path.join(current_dir, rel_path)
                dest_dir = os.path.join(temp_dir, os.path.dirname(rel_path))
                os.makedirs(dest_dir, exist_ok=True)
                dest = os.path.join(temp_dir, rel_path)
                shutil.copy2(source, dest)
                self.logger.info(f"Preserved file: {rel_path}")
            
            # Step 4: Create update script
            await msg.edit(content=f"🔄 Preparing to apply update...")
            update_script = self._create_update_script(temp_dir, current_dir)
            
            # Step 5: Execute the update script
            await msg.edit(content=f"🔄 Applying update... Bot will restart shortly.")
            self.logger.info("Executing update script")
            
            # Run the script asynchronously and detached
            subprocess.Popen(
                ["/bin/bash", update_script],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait briefly then shut down
            await asyncio.sleep(3)
            await self.bot.close()
            
        except Exception as e:
            self.logger.error(f"Update failed: {str(e)}", exc_info=True)
            await msg.edit(content=f"❌ Update failed: {str(e)}\n\nYour backup is at: {backup_path}")
    
    def _create_backup_script(self, source_dir, backup_dir):
        """Create a script to make a full backup"""
        fd, script_path = tempfile.mkstemp(suffix=".sh", prefix="retardibot_backup_")
        os.close(fd)
        
        with open(script_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Script to create a full backup of the bot\n\n")
            
            f.write(f"echo 'Creating backup directory {backup_dir}'\n")
            f.write(f"mkdir -p '{backup_dir}'\n\n")
            
            f.write(f"echo 'Creating full backup from {source_dir}'\n")
            # Use rsync for efficient copying with exclusions
            f.write(f"rsync -av --exclude '.git' --exclude '__pycache__' --exclude 'venv' '{source_dir}/' '{backup_dir}/'\n")
            
            f.write(f"echo 'Backup complete at {backup_dir}'\n")
        
        # Make the script executable
        os.chmod(script_path, 0o755)
        return script_path
    
    def _create_update_script(self, update_dir, target_dir):
        """Create a script that will apply the update and restart the bot"""
        fd, script_path = tempfile.mkstemp(suffix=".sh", prefix="retardibot_update_")
        os.close(fd)
        
        with open(script_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("# Script to apply bot updates and restart\n\n")
            
            # Wait for the bot to shut down
            f.write("echo 'Waiting for bot to shut down...'\n")
            f.write("sleep 5\n\n")
            
            # Clean target directory while preserving important folders
            f.write(f"echo 'Cleaning target directory {target_dir}'\n")
            f.write(f"find '{target_dir}' -mindepth 1 -maxdepth 1 ! -name '.git' ! -name 'venv' ! -name '__pycache__' -exec rm -rf {{}} \\;\n\n")
            
            # Copy files from update directory to target directory
            f.write(f"echo 'Copying updated files to {target_dir}'\n")
            f.write(f"cp -a '{update_dir}/'* '{target_dir}/'\n")
            # Copy hidden files too (except .git)
            f.write(f"find '{update_dir}/' -name '.*' -not -name '.git' -maxdepth 1 -exec cp -a {{}} '{target_dir}/' \\; 2>/dev/null || true\n\n")
            
            # Clean up the update directory
            f.write(f"echo 'Cleaning up temporary directory {update_dir}'\n")
            f.write(f"rm -rf '{update_dir}'\n\n")
            
            # Clean up the script itself
            f.write("echo 'Cleaning up update script'\n")
            f.write(f"rm -f '{script_path}'\n\n")
            
            # Start the bot in the background
            f.write(f"echo 'Starting bot from {target_dir}'\n")
            f.write(f"cd '{target_dir}' && python3 bot.py &\n")
            
            f.write("echo 'Update complete!'\n")
        
        # Make the script executable
        os.chmod(script_path, 0o755)
        return script_path
    
    async def _run_script(self, script_path):
        """Run a shell script and wait for it to complete"""
        process = await asyncio.create_subprocess_shell(
            f"bash {script_path}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error = stderr.decode().strip()
            self.logger.error(f"Script execution failed: {error}")
            raise Exception(f"Script execution failed: {error}")
        
        # Clean up the script
        try:
            os.remove(script_path)
        except:
            pass
        
        return stdout.decode().strip()

def setup(bot):
    bot.add_cog(GitUpdateCog(bot))