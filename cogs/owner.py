import disnake
from disnake.ext import commands
import asyncio
import os
import sys
import datetime
import json
import platform
import psutil
import subprocess
import inspect
import textwrap
import io
import traceback
from contextlib import redirect_stdout

class OwnerCog(commands.Cog, command_attrs=dict(hidden=True)):
    """Special commands for the bot owner only"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.dev_logger
        self._last_result = None
        self.sessions = {}
        
    @commands.command(name="shutdown", aliases=["die", "sleep"])
    @commands.is_owner()
    async def shutdown(self, ctx):
        """Shuts down the bot"""
        embed = disnake.Embed(
            title="Shutting down...",
            description="Goodbye, cruel world!",
            color=disnake.Color.red()
        )
        await ctx.send(embed=embed)
        self.logger.warning(f"Bot shutdown initiated by {ctx.author}")
        await self.bot.close()
        
    @commands.command(name="restart")
    @commands.is_owner()
    async def restart(self, ctx):
        """Restarts the bot"""
        embed = disnake.Embed(
            title="Restarting...",
            description="Be right back!",
            color=disnake.Color.orange()
        )
        await ctx.send(embed=embed)
        self.logger.warning(f"Bot restart initiated by {ctx.author}")
        
        # Use Python to restart the bot
        python = sys.executable
        os.execl(python, python, *sys.argv)

    @commands.command(name="loadfile")
    @commands.is_owner()
    async def load_file_as_cog(self, ctx):
        """Loads an attached Python file as a cog"""
        if not ctx.message.attachments:
            return await ctx.send("❌ Please attach a Python file to load.")
        
        attachment = ctx.message.attachments[0]
        if not attachment.filename.endswith('.py'):
            return await ctx.send("❌ Please attach a Python (.py) file.")
        
        # Create cogs directory if it doesn't exist
        os.makedirs("cogs", exist_ok=True)
        
        # Download the attachment
        cog_path = f"cogs/{attachment.filename}"
        await attachment.save(cog_path)
        
        # Get the cog name (filename without .py)
        cog_name = f"cogs.{attachment.filename[:-3]}"
        
        try:
            # Check if the load_extension method is a coroutine or not
            if inspect.iscoroutinefunction(self.bot.load_extension):
                await self.bot.load_extension(cog_name)
            else:
                self.bot.load_extension(cog_name)
                
            await ctx.send(f"✅ Successfully loaded `{cog_name}` from attachment.")
            self.logger.info(f"Loaded cog from attachment: {cog_name}")
        except Exception as e:
            await ctx.send(f"❌ Failed to load `{cog_name}`: {type(e).__name__} - {e}")
            self.logger.error(f"Failed to load cog {cog_name} from attachment: {e}", exc_info=True)
        
    @commands.command(name="load")
    @commands.is_owner()
    async def load_cog(self, ctx, *, cog: str):
        """Loads a cog"""
        try:
            if not cog.startswith("cogs."):
                cog = f"cogs.{cog}"
                
            # Check if the load_extension method is a coroutine or not
            if inspect.iscoroutinefunction(self.bot.load_extension):
                await self.bot.load_extension(cog)
            else:
                self.bot.load_extension(cog)
                
            await ctx.send(f"✅ Successfully loaded `{cog}`")
            self.logger.info(f"Loaded cog: {cog}")
        except Exception as e:
            await ctx.send(f"❌ Failed to load `{cog}`: {type(e).__name__} - {e}")
            self.logger.error(f"Failed to load cog {cog}: {e}", exc_info=True)
            
    @commands.command(name="unload")
    @commands.is_owner()
    async def unload_cog(self, ctx, *, cog: str):
        """Unloads a cog"""
        try:
            if not cog.startswith("cogs."):
                cog = f"cogs.{cog}"
                
            # Check if the unload_extension method is a coroutine or not
            if inspect.iscoroutinefunction(self.bot.unload_extension):
                await self.bot.unload_extension(cog)
            else:
                self.bot.unload_extension(cog)
                
            await ctx.send(f"✅ Successfully unloaded `{cog}`")
            self.logger.info(f"Unloaded cog: {cog}")
        except Exception as e:
            await ctx.send(f"❌ Failed to unload `{cog}`: {type(e).__name__} - {e}")
            self.logger.error(f"Failed to unload cog {cog}: {e}", exc_info=True)
            
    @commands.command(name="reload")
    @commands.is_owner()
    async def reload_cog(self, ctx, *, cog: str):
        """Reloads a cog"""
        try:
            if not cog.startswith("cogs."):
                cog = f"cogs.{cog}"
                
            # Check if the reload_extension method is a coroutine or not
            if inspect.iscoroutinefunction(self.bot.reload_extension):
                await self.bot.reload_extension(cog)
            else:
                self.bot.reload_extension(cog)
                
            await ctx.send(f"✅ Successfully reloaded `{cog}`")
            self.logger.info(f"Reloaded cog: {cog}")
        except Exception as e:
            await ctx.send(f"❌ Failed to reload `{cog}`: {type(e).__name__} - {e}")
            self.logger.error(f"Failed to reload cog {cog}: {e}", exc_info=True)

    @commands.command(name="reloadall")
    @commands.is_owner()
    async def reload_all_cogs(self, ctx):
        """Reloads all cogs"""
        msg = await ctx.send("Reloading all cogs...")
        
        success = []
        failed = {}
        
        for extension in list(self.bot.extensions):
            try:
                # Check if the reload_extension method is a coroutine or not
                if inspect.iscoroutinefunction(self.bot.reload_extension):
                    await self.bot.reload_extension(extension)
                else:
                    self.bot.reload_extension(extension)
                    
                success.append(extension)
            except Exception as e:
                failed[extension] = f"{type(e).__name__}: {e}"
                
        result = "**Reload complete**\n"
        if success:
            result += f"✅ **Successfully reloaded:** {len(success)}/{len(success) + len(failed)}\n"
        if failed:
            result += f"❌ **Failed to reload:** {len(failed)}/{len(success) + len(failed)}\n"
            for ext, error in failed.items():
                result += f"> `{ext}`: {error}\n"
                
        await msg.edit(content=result)
        self.logger.info(f"Reloaded {len(success)} cogs, {len(failed)} failed")
        
    @commands.command(name="eval")
    @commands.is_owner()
    async def eval_cmd(self, ctx, *, code: str):
        """Evaluates Python code"""
        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            'self': self,
            '_': self._last_result
        }

        env.update(globals())

        # Remove code blocks if present
        if code.startswith('```') and code.endswith('```'):
            code = '\n'.join(code.split('\n')[1:-1])
        
        # Add return for expressions
        code = textwrap.indent(code, '    ')
        body = f'async def func():\n{code}'
        
        try:
            exec(body, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')
        
        func = env['func']
        stdout = io.StringIO()
        
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            
            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                self._last_result = ret
                await ctx.send(f'```py\n{value}{ret}\n```')
    
    @commands.command(name="say")
    @commands.is_owner()
    async def say(self, ctx, channel: disnake.TextChannel, *, message: str):
        """Makes the bot say something in a specific channel"""
        try:
            await channel.send(message)
            await ctx.message.add_reaction("✅")
        except Exception as e:
            await ctx.send(f"Error: {e}")
    
    @commands.command(name="dm")
    @commands.is_owner()
    async def dm_user(self, ctx, user: disnake.User, *, message: str):
        """Send a direct message to a user"""
        try:
            await user.send(message)
            await ctx.message.add_reaction("✅")
        except Exception as e:
            await ctx.send(f"Failed to DM user: {e}")
            
    @commands.command(name="status")
    @commands.is_owner()
    async def set_status(self, ctx, status_type: str, *, text: str = None):
        """Sets the bot's status
        Types: playing, watching, listening, streaming, competing, reset"""
        activity = None
        
        if status_type.lower() == "playing":
            activity = disnake.Game(name=text)
        elif status_type.lower() == "watching":
            activity = disnake.Activity(type=disnake.ActivityType.watching, name=text)
        elif status_type.lower() == "listening":
            activity = disnake.Activity(type=disnake.ActivityType.listening, name=text)
        elif status_type.lower() == "streaming":
            activity = disnake.Streaming(name=text, url="https://www.twitch.tv/directory")
        elif status_type.lower() == "competing":
            activity = disnake.Activity(type=disnake.ActivityType.competing, name=text)
        elif status_type.lower() == "reset":
            activity = None
        else:
            return await ctx.send("Invalid status type. Choose from: playing, watching, listening, streaming, competing, reset")
            
        await self.bot.change_presence(activity=activity)
        await ctx.send(f"Status updated to: {status_type.title()} {text}" if text else "Status reset")
        
    @commands.command(name="maintenance")
    @commands.is_owner()
    async def maintenance_mode(self, ctx, state: bool = None):
        """Toggles maintenance mode"""
        # This would need to be implemented based on your bot's specific needs
        # Here's a basic example that changes the bot's status
        
        if state is None:
            # Toggle current state
            current_state = getattr(self.bot, "maintenance_mode", False)
            state = not current_state
            
        self.bot.maintenance_mode = state
        
        if state:
            await self.bot.change_presence(
                activity=disnake.Activity(type=disnake.ActivityType.playing, name="🔧 Maintenance"),
                status=disnake.Status.dnd
            )
            await ctx.send("Maintenance mode **enabled**")
        else:
            await self.bot.change_presence(
                activity=disnake.Activity(type=disnake.ActivityType.watching, name="you"),
                status=disnake.Status.online
            )
            await ctx.send("Maintenance mode **disabled**")
            
    @commands.command(name="sudo")
    @commands.is_owner()
    async def sudo(self, ctx, user: disnake.Member, *, command_string: str):
        """Run a command as another user"""
        msg = ctx.message
        msg.author = user
        msg.content = ctx.prefix + command_string
        
        await self.bot.process_commands(msg)
        await ctx.message.add_reaction("✅")
        
    @commands.command(name="sysinfo")
    @commands.is_owner()
    async def system_info(self, ctx):
        """Shows system information"""
        embed = disnake.Embed(
            title="System Information",
            color=disnake.Color.blue(),
            timestamp=datetime.datetime.utcnow()
        )
        
        # System info
        embed.add_field(name="OS", value=platform.system(), inline=True)
        embed.add_field(name="Python", value=platform.python_version(), inline=True)
        embed.add_field(name="Disnake", value=disnake.__version__, inline=True)
        
        # CPU usage
        cpu_usage = psutil.cpu_percent()
        embed.add_field(name="CPU Usage", value=f"{cpu_usage}%", inline=True)
        
        # Memory usage
        memory = psutil.virtual_memory()
        embed.add_field(
            name="Memory Usage",
            value=f"{memory.percent}% ({memory.used // 1024 // 1024} MB / {memory.total // 1024 // 1024} MB)",
            inline=True
        )
        
        # Disk usage
        disk = psutil.disk_usage('/')
        embed.add_field(
            name="Disk Usage",
            value=f"{disk.percent}% ({disk.used // 1024 // 1024 // 1024} GB / {disk.total // 1024 // 1024 // 1024} GB)",
            inline=True
        )
        
        # Bot stats
        uptime = datetime.datetime.utcnow() - datetime.datetime.fromtimestamp(psutil.Process().create_time())
        days, remainder = divmod(uptime.total_seconds(), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(name="Guilds", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Users", value=str(len(set(self.bot.get_all_members()))), inline=True)
        
        await ctx.send(embed=embed)
        
    @commands.command(name="backup")
    @commands.is_owner()
    async def backup_db(self, ctx):
        """Creates backups of database files"""
        backup_time = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_dir = "backups"
        
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        db_files = [f for f in os.listdir('.') if f.endswith('.db')]
        
        if not db_files:
            return await ctx.send("No database files found to backup.")
            
        for db_file in db_files:
            source = db_file
            destination = f"{backup_dir}/{db_file.replace('.db', '')}_{backup_time}.db"
            
            try:
                import shutil
                shutil.copy2(source, destination)
            except Exception as e:
                await ctx.send(f"Error backing up {db_file}: {e}")
                continue
        
        await ctx.send(f"✅ Successfully backed up {len(db_files)} database files to `{backup_dir}/`")
        
    @commands.command(name="shell", aliases=["sh"])
    @commands.is_owner()
    async def shell_command(self, ctx, *, command: str):
        """Executes a shell command"""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if stdout:
                stdout = stdout.decode('utf-8')
                if len(stdout) > 1990:
                    stdout = stdout[:1990] + "..."
                await ctx.send(f"```\n{stdout}\n```")
            
            if stderr:
                stderr = stderr.decode('utf-8')
                if len(stderr) > 1990:
                    stderr = stderr[:1990] + "..."
                await ctx.send(f"```\n{stderr}\n```")
                
            if not stdout and not stderr:
                await ctx.send("Command executed with no output.")
                
        except Exception as e:
            await ctx.send(f"Error: {e}")
            
    @commands.command(name="secret")
    @commands.is_owner()
    async def secret_command(self, ctx, *, text: str):
        """Sends a message and then deletes your command"""
        await ctx.message.delete()
        await ctx.send(text)
    
    @commands.group(name="blacklist", invoke_without_command=True)
    @commands.is_owner()
    async def blacklist(self, ctx):
        """Manage the bot's blacklist"""
        await ctx.send("Please use a subcommand: `add`, `remove`, `list`")
        
    @blacklist.command(name="add")
    @commands.is_owner()
    async def blacklist_add(self, ctx, user: disnake.User, *, reason: str = "No reason provided"):
        """Add a user to the blacklist"""
        # This would need to be implemented based on your bot's specific needs
        # Here's a basic example using a config file
        
        config = getattr(self.bot, 'config', {})
        
        if "blacklist" not in config:
            config["blacklist"] = {}
            
        config["blacklist"][str(user.id)] = {
            "reason": reason,
            "added_by": ctx.author.id,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        
        # Save to file
        try:
            with open("config.json", 'w') as f:
                json.dump(config, f, indent=4)
                
            # Update bot's config
            self.bot.config = config
            
            await ctx.send(f"✅ Added {user.mention} to the blacklist. Reason: {reason}")
            self.logger.warning(f"User {user} ({user.id}) blacklisted by {ctx.author}. Reason: {reason}")
        except Exception as e:
            await ctx.send(f"Error saving blacklist: {e}")
            
    @blacklist.command(name="remove")
    @commands.is_owner()
    async def blacklist_remove(self, ctx, user: disnake.User):
        """Remove a user from the blacklist"""
        config = getattr(self.bot, 'config', {})
        
        if "blacklist" not in config or str(user.id) not in config["blacklist"]:
            return await ctx.send(f"{user.mention} is not blacklisted.")
            
        del config["blacklist"][str(user.id)]
        
        # Save to file
        try:
            with open("config.json", 'w') as f:
                json.dump(config, f, indent=4)
                
            # Update bot's config
            self.bot.config = config
            
            await ctx.send(f"✅ Removed {user.mention} from the blacklist.")
            self.logger.info(f"User {user} ({user.id}) removed from blacklist by {ctx.author}")
        except Exception as e:
            await ctx.send(f"Error saving blacklist: {e}")
            
    @blacklist.command(name="list")
    @commands.is_owner()
    async def blacklist_list(self, ctx):
        """List all blacklisted users"""
        config = getattr(self.bot, 'config', {})
        blacklist = config.get("blacklist", {})
        
        if not blacklist:
            return await ctx.send("No users are blacklisted.")
            
        embed = disnake.Embed(
            title="Blacklisted Users",
            color=disnake.Color.red(),
            description=f"Total: {len(blacklist)} users",
            timestamp=datetime.datetime.utcnow()
        )
        
        for user_id, data in blacklist.items():
            user = self.bot.get_user(int(user_id))
            user_name = user.mention if user else f"Unknown User ({user_id})"
            
            reason = data.get("reason", "No reason provided")
            added_by_id = data.get("added_by")
            added_by = self.bot.get_user(added_by_id) if added_by_id else None
            added_by_name = added_by.mention if added_by else "Unknown"
            
            timestamp = data.get("timestamp")
            time_str = ""
            if timestamp:
                try:
                    dt = datetime.datetime.fromisoformat(timestamp)
                    time_str = f" on <t:{int(dt.timestamp())}:F>"
                except:
                    pass
                    
            embed.add_field(
                name=f"User: {user_name}",
                value=f"**Reason:** {reason}\n**Added by:** {added_by_name}{time_str}",
                inline=False
            )
            
        await ctx.send(embed=embed)
        
    # Global error handler for the cog
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # Only handle errors for commands in this cog
        if ctx.command and ctx.command.cog_name == self.__class__.__name__:
            if isinstance(error, commands.CheckFailure):
                # Don't respond to non-owners to avoid revealing these commands exist
                pass
            elif isinstance(error, commands.MissingRequiredArgument):
                await ctx.send(f"Missing required argument: {error.param.name}")
            elif isinstance(error, commands.BadArgument):
                await ctx.send(f"Bad argument: {error}")
            else:
                await ctx.send(f"Error: {error}")
                self.logger.error(f"Error in owner command {ctx.command}: {error}", exc_info=error)

def setup(bot):
    bot.add_cog(OwnerCog(bot))