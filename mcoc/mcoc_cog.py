import aiohttp

from .cdt_core import CDT
from .cdt_commands import CdtCommands
from .abc import CompositeMetaClass
from redbot.core.bot import Red
from redbot.core.config import Config
from redbot.core import commands
import logging

from .config_structure import config_structure

# log = logging.getLogger('red.CollectorDevTeam.mcoc')



class MCOC(CdtCommands, CDT, commands.Cog, metaclass=CompositeMetaClass):
    """Marvel Contest of Champions"""

    __version__="3.0.0a"

    def __init__(self, bot: Red):
        super().__init__(bot)
        self.config = Config.get_conf(self, identifier=1978198120172018)
        self.config.register_user(**config_structure["default_user"])
        self.config.register_global(**config_structure["mcoc"])
        self.config.register_global(**config_structure["alliance_registry"])
        self.session = aiohttp.ClientSession
        # self.default_user_profile = _config_structure["default_user"]
    
    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())