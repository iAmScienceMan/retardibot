import disnake
from disnake.ext import commands
import logging
import colorlog
import os
import tomli
import sys
from logging.handlers import RotatingFileHandler
from cogs.common.base_cog import BaseCog

class DevLogger(BaseCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.config_path = "devlogger_config.toml"
        self.logger = None
        self.setup_logger()
        
    def setup_logger(self):
        """Set up the developer logger using configuration from TOML"""
        # Create the root logger for the bot
        logger = logging.getLogger('retardibot')
        logger.setLevel(logging.INFO)  # Default level
        
        # Clear any existing handlers
        if logger.handlers:
            logger.handlers = []
            
        # Load config if it exists
        config = self.load_config()
        
        # Configure console logging
        console_level = self.get_log_level(config.get('console_level', 'INFO'))
        console_format = config.get('console_format', 
            '%(log_color)s%(levelname)-8s%(reset)s | %(asctime)s | %(name)s | %(message)s')
        date_format = config.get('date_format', '%Y-%m-%d %H:%M:%S')
        
        # Set up console handler with colors
        console_handler = colorlog.StreamHandler(stream=sys.stdout)
        console_handler.setLevel(console_level)
        color_formatter = colorlog.ColoredFormatter(
            console_format,
            datefmt=date_format,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(color_formatter)
        logger.addHandler(console_handler)
        
        # Configure file logging if enabled
        if config.get('file_logging', True):
            file_level = self.get_log_level(config.get('file_level', 'DEBUG'))
            file_format = config.get('file_format', 
                '%(levelname)-8s | %(asctime)s | %(name)s | %(message)s')
            log_dir = config.get('log_dir', 'logs')
            log_file = config.get('log_file', 'dev.log')
            max_size = config.get('max_file_size', 5 * 1024 * 1024)  # 5MB default
            backup_count = config.get('backup_count', 5)
            
            # Create the log directory if it doesn't exist
            os.makedirs(log_dir, exist_ok=True)
            
            # Set up file handler with rotation
            file_handler = RotatingFileHandler(
                os.path.join(log_dir, log_file),
                maxBytes=max_size,
                backupCount=backup_count
            )
            file_handler.setLevel(file_level)
            file_formatter = logging.Formatter(file_format, datefmt=date_format)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            
        # Set the global log level
        global_level = self.get_log_level(config.get('level', 'INFO'))
        logger.setLevel(global_level)
        
        # Configure component-specific loggers
        components = config.get('components', {})
        for component, level in components.items():
            component_logger = logger.getChild(component)
            component_logger.setLevel(self.get_log_level(level))
        
        # Store the logger
        self.logger = logger
        self.bot.dev_logger = logger
        
        # Log initialization
        logger.debug("Developer logger initialized")
        logger.info(f"Logging level set to {logging.getLevelName(global_level)}")
        
    def load_config(self):
        """Load configuration from TOML file"""
        try:
            with open(self.config_path, 'rb') as f:
                config = tomli.load(f)
                return config.get('logging', {})
        except Exception as e:
            print(f"Error loading logging config: {e}")
            return {}
            
    def get_log_level(self, level_name):
        """Convert string level name to logging level"""
        levels = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        return levels.get(level_name.upper(), logging.INFO)
    
    @commands.command()
    @commands.is_owner()
    async def loglevel(self, ctx, level: str, component: str = None):
        """Change the logging level for the bot or a specific component"""
        level = level.upper()
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        
        if level not in valid_levels:
            return await ctx.send(f"Invalid log level. Choose from: {', '.join(valid_levels)}")
        
        log_level = self.get_log_level(level)
        
        if component:
            # Set level for a specific component
            component_logger = self.logger.getChild(component)
            component_logger.setLevel(log_level)
            await ctx.send(f"Log level for component '{component}' set to {level}")
        else:
            # Set global level
            self.logger.setLevel(log_level)
            # Also update handlers
            for handler in self.logger.handlers:
                handler.setLevel(log_level)
            await ctx.send(f"Global log level set to {level}")
        
        self.logger.info(f"Log level changed to {level} for {'component ' + component if component else 'global'}")

    @commands.command()
    @commands.is_owner()
    async def logtest(self, ctx):
        """Test logging at different levels"""
        self.logger.info("=== LOG TEST MESSAGES TRIGGERED ===")
        self.logger.debug("This is a DEBUG message")
        self.logger.info("This is an INFO message")
        self.logger.warning("This is a WARNING message")
        self.logger.error("This is an ERROR message")
        self.logger.critical("This is a CRITICAL message")
        
        await ctx.send("Log test messages sent at all levels. Check your console/log file.")

def setup(bot):
    bot.add_cog(DevLogger(bot))