import disnake
from disnake.ext import commands
import os
import shutil
import glob
import datetime
import platform
import asyncio
import sys
from cogs.common.base_cog import BaseCog

class UpdateCog(BaseCog):
    """Commands for updating the bot from GitHub"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.repo_url = "https://github.com/iAmScienceMan/retardibot.git"
        self.home_dir = os.path.expanduser("~")
        self.download_dir = os.path.join(self.home_dir, "downloading")
        self.old_dir = os.path.join(self.home_dir, "old")
        self.repo_dir = os.path.join(self.home_dir, "retardibot")
        self.new_repo_dir = os.path.join(self.download_dir, "retardibot")
        self.venv_dir = os.path.join(self.home_dir, "venv")
    
    @commands.group(name="git", invoke_without_command=True)
    @commands.is_owner()
    async def git_group(self, ctx):
        """Git repository management commands"""
        await ctx.send("Available git subcommands: `update`")
    
    @git_group.command(name="update")
    @commands.is_owner()
    async def git_update(self, ctx):
        """Update the bot from GitHub"""
        # Check if running on Linux
        if platform.system() != "Linux":
            return await ctx.send("❌ This command is only supported on Linux systems.")
        
        # Check if git is installed
        if not await self.check_command_exists("git"):
            return await ctx.send("❌ Git is not installed on this system.")
        
        status_message = await ctx.send("🔄 Starting update process...")
        
        try:
            # Step 1: Clone the repository
            await self.update_status(status_message, "🔄 Cloning repository...")
            await self.clone_repository()
            
            # Step 2: Move important files
            await self.update_status(status_message, "🔄 Preserving important files...")
            await self.preserve_files()
            
            # Step 3: Backup old repository
            await self.update_status(status_message, "🔄 Backing up old repository...")
            await self.backup_old_repository()
            
            # Step 4: Move new repository to main location
            await self.update_status(status_message, "🔄 Installing new version...")
            await self.install_new_version()
            
            # Step 5: Update dependencies
            await self.update_status(status_message, "🔄 Updating dependencies...")
            await self.update_dependencies()
            
            await self.update_status(status_message, "✅ Update completed successfully! Restart the bot to apply changes.")
            
        except Exception as e:
            self.logger.error(f"Update failed: {e}", exc_info=True)
            await self.update_status(status_message, f"❌ Update failed: {e}")
            
            # Cleanup if needed
            await self.cleanup()
    
    async def check_command_exists(self, command):
        """Check if a command exists on the system"""
        try:
            process = await asyncio.create_subprocess_shell(
                f"which {command}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            return process.returncode == 0
        except:
            return False
    
    async def update_status(self, message, status):
        """Update the status message"""
        await message.edit(content=status)
        self.logger.info(status)
    
    async def clone_repository(self):
        """Clone the repository to download directory"""
        # Create download directory if it doesn't exist
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Remove existing cloned repo if it exists
        if os.path.exists(self.new_repo_dir):
            shutil.rmtree(self.new_repo_dir)
        
        # Clone the repository
        process = await asyncio.create_subprocess_shell(
            f"git clone {self.repo_url} {self.new_repo_dir}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise Exception(f"Git clone failed: {stderr.decode()}")
    
    async def preserve_files(self):
        """Preserve important files by copying them to the new repo"""
        # Make sure the new repo directory exists
        if not os.path.exists(self.new_repo_dir):
            raise Exception("New repository directory does not exist")
        
        # Copy .env file if it exists
        env_file = os.path.join(self.repo_dir, ".env")
        if os.path.exists(env_file):
            shutil.copy2(env_file, os.path.join(self.new_repo_dir, ".env"))
            self.logger.info(f"Copied .env file")
        
        # Copy all database files
        for db_file in glob.glob(os.path.join(self.repo_dir, "*.db")):
            dest_file = os.path.join(self.new_repo_dir, os.path.basename(db_file))
            shutil.copy2(db_file, dest_file)
            self.logger.info(f"Copied database file: {os.path.basename(db_file)}")
        
        # Copy config.toml if it exists
        config_toml = os.path.join(self.repo_dir, "config.toml")
        if os.path.exists(config_toml):
            shutil.copy2(config_toml, os.path.join(self.new_repo_dir, "config.toml"))
            self.logger.info(f"Copied config.toml file")
        
        # Copy config.json if it exists
        config_json = os.path.join(self.repo_dir, "config.json")
        if os.path.exists(config_json):
            shutil.copy2(config_json, os.path.join(self.new_repo_dir, "config.json"))
            self.logger.info(f"Copied config.json file")
    
    async def backup_old_repository(self):
        """Backup the old repository"""
        if not os.path.exists(self.repo_dir):
            return  # Nothing to backup
        
        # Create backup directory if it doesn't exist
        os.makedirs(self.old_dir, exist_ok=True)
        
        # Create a timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(self.old_dir, f"retardibot_{timestamp}")
        
        # Move the old repository to the backup directory
        shutil.move(self.repo_dir, backup_dir)
        self.logger.info(f"Backed up old repository to {backup_dir}")
    
    async def install_new_version(self):
        """Move the new repository to the main location"""
        # Move the new repository to the main location
        shutil.move(self.new_repo_dir, self.repo_dir)
        self.logger.info(f"Installed new repository to {self.repo_dir}")
        
        # Clean up download directory
        if os.path.exists(self.download_dir) and not os.listdir(self.download_dir):
            os.rmdir(self.download_dir)
    
    async def update_dependencies(self):
        """Update dependencies using the virtual environment"""
        if not os.path.exists(self.venv_dir):
            self.logger.warning(f"Virtual environment not found at {self.venv_dir}")
            return
        
        # Check if requirements.txt exists
        requirements_file = os.path.join(self.repo_dir, "requirements.txt")
        if not os.path.exists(requirements_file):
            self.logger.warning("requirements.txt not found, skipping dependency update")
            return
        
        # Path to the pip executable in the virtual environment
        pip_executable = os.path.join(self.venv_dir, "bin", "pip")
        
        if not os.path.exists(pip_executable):
            pip_executable = os.path.join(self.venv_dir, "bin", "pip3")
        
        if not os.path.exists(pip_executable):
            self.logger.warning("pip executable not found in virtual environment")
            return
        
        # Install requirements
        process = await asyncio.create_subprocess_shell(
            f"{pip_executable} install -r {requirements_file}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            self.logger.error(f"Failed to update dependencies: {stderr.decode()}")
        else:
            self.logger.info("Successfully updated dependencies")
    
    async def cleanup(self):
        """Cleanup temporary files if an error occurred"""
        # Remove the download directory if it exists
        if os.path.exists(self.download_dir):
            try:
                shutil.rmtree(self.download_dir)
                self.logger.info(f"Cleaned up download directory")
            except Exception as e:
                self.logger.error(f"Failed to clean up download directory: {e}")

def setup(bot):
    bot.add_cog(UpdateCog(bot))